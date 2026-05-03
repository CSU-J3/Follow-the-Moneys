"""Orchestrator. Runs every collector, splits results by source trust, dedups
against the existing store, persists data files, and publishes the rendered
payload that the static site fetches.

Run from the repo root:
    python -m collectors.run_all
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from collectors import news_collector
from collectors.bop_collector_utils import dedup, event_hash, is_trusted

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

BOP_FINANCES = DATA_DIR / "bop_finances.json"
CANDIDATES = DATA_DIR / "candidates.json"
LAST_RUN = DATA_DIR / "last_run.json"
SITE_DATA = DOCS_DIR / "data.json"

logger = logging.getLogger(__name__)


# Collector registry. Each entry is (name, callable returning list[dict]).
# Phases 4-5 add wikipedia_collector and source_collector here.
COLLECTORS: tuple[tuple[str, Callable[[], list[dict]]], ...] = (
    ("news", news_collector.collect),
)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _next_event_id(existing_events: list[dict]) -> Callable[[], str]:
    used = {e.get("id") for e in existing_events if e.get("id")}
    counter = max(
        (int(eid.split("-")[1]) for eid in used if isinstance(eid, str) and eid.startswith("ev-")),
        default=0,
    )

    def assign() -> str:
        nonlocal counter
        counter += 1
        return f"ev-{counter:03d}"

    return assign


def _route(events: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split collector output into (trusted, candidate) buckets by source."""
    trusted, candidates = [], []
    for ev in events:
        sources = ev.get("sources") or []
        if any(is_trusted(s.get("name")) for s in sources):
            trusted.append(ev)
        else:
            candidates.append(ev)
    return trusted, candidates


def _counts_toward_total(event: dict) -> bool:
    """Apply the methodology filter: pledged or transferred, not flagged out."""
    if event.get("status") not in ("pledged", "transferred"):
        return False
    if event.get("superseded_by"):
        return False
    if event.get("excluded_from_total"):
        return False
    return True


def _compute_summary(base_summary: dict, events: list[dict]) -> dict:
    """Re-derive total_committed and total_transferred from events.

    Non-derivable fields (congressional_votes, reconstruction_need_*, etc.)
    are passed through from bop_finances.json so they can't drift.
    """
    total_committed = sum(
        e.get("amount") or 0 for e in events if _counts_toward_total(e)
    )
    total_transferred = sum(
        e.get("amount") or 0
        for e in events
        if _counts_toward_total(e) and e.get("status") == "transferred"
    )
    return {
        **base_summary,
        "total_committed": total_committed,
        "total_transferred": total_transferred,
    }


def publish_to_site(finances: dict) -> None:
    """Write docs/data.json — the payload index.html fetches at page load.

    docs/index.html (line ~720) does `fetch("data.json?...")` relative to
    itself. This function is the bridge from the curated data store to the
    rendered shape the page expects: {last_updated, summary, events}.
    """
    summary = _compute_summary(finances.get("summary", {}), finances.get("events", []))
    payload = {
        "last_updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summary,
        "events": finances.get("events", []),
    }
    _write_json(SITE_DATA, payload)
    logger.info("published %d events to %s", len(payload["events"]), SITE_DATA)


def run() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    finances = _read_json(BOP_FINANCES, {"summary": {}, "events": []})
    candidates = _read_json(CANDIDATES, [])
    run_log: dict[str, dict] = {}

    assign_id = _next_event_id(finances["events"] + candidates)

    for name, fn in COLLECTORS:
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            raw = fn()
        except Exception as e:
            logger.exception("collector %r crashed", name)
            run_log[name] = {"started": started, "ok": False, "error": str(e)}
            continue

        trusted, untrusted = _route(raw)
        new_trusted = dedup(trusted, finances["events"])
        new_candidates = dedup(untrusted, candidates + finances["events"])

        for e in new_trusted:
            e["id"] = assign_id()
        for e in new_candidates:
            e["id"] = assign_id()

        finances["events"].extend(new_trusted)
        candidates.extend(new_candidates)

        run_log[name] = {
            "started": started,
            "ok": True,
            "raw_count": len(raw),
            "added_to_finances": len(new_trusted),
            "added_to_candidates": len(new_candidates),
        }

    _write_json(BOP_FINANCES, finances)
    _write_json(CANDIDATES, candidates)
    _write_json(LAST_RUN, run_log)
    publish_to_site(finances)
    return 0


if __name__ == "__main__":
    sys.exit(run())
