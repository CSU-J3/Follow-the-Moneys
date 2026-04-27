"""Pure utilities shared by all collectors.

Amount extraction, category classification, dedup hashing, source trust check.
No I/O here — collectors and the orchestrator handle disk and network.
"""

from __future__ import annotations

import re
from hashlib import sha256

_UNIT_MULT: dict[str, int] = {
    "b": 1_000_000_000, "billion": 1_000_000_000,
    "m": 1_000_000, "million": 1_000_000,
    "t": 1_000_000_000_000, "trillion": 1_000_000_000_000,
    "k": 1_000, "thousand": 1_000,
}

_RANGE_RE = re.compile(
    r"\$\s*([0-9][0-9,.]*)\s*(?:[-–—]|to)\s*([0-9][0-9,.]*)\s*"
    r"(billion|million|trillion|thousand|[bmtk])\b",
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(
    r"\$\s*([0-9][0-9,.]*)\s*(billion|million|trillion|thousand|[bmtk])\b",
    re.IGNORECASE,
)
_PLAIN_RE = re.compile(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?!\.\d)\b")


def _to_int(num_str: str, unit_str: str) -> int:
    n = float(num_str.replace(",", ""))
    return int(round(n * _UNIT_MULT[unit_str.lower()]))


def _format_display(value: int) -> str:
    if value >= 1_000_000_000_000:
        s = f"{value / 1e12:.1f}".rstrip("0").rstrip(".")
        return f"${s}T"
    if value >= 1_000_000_000:
        s = f"{value / 1e9:.2f}".rstrip("0").rstrip(".")
        return f"${s}B"
    if value >= 1_000_000:
        return f"${round(value / 1e6)}M"
    return f"${value:,}"


def parse_amount(text: str | None) -> tuple[int | None, str | None]:
    """Extract the first dollar amount in `text`.

    Returns (numeric, display) or (None, None) if nothing parseable is found.
    Ranges (e.g. "$60–70M") collapse to their midpoint.
    """
    if not text:
        return (None, None)

    m = _RANGE_RE.search(text)
    if m:
        low = _to_int(m.group(1), m.group(3))
        high = _to_int(m.group(2), m.group(3))
        return ((low + high) // 2, m.group(0).strip())

    m = _SINGLE_RE.search(text)
    if m:
        v = _to_int(m.group(1), m.group(2))
        return (v, _format_display(v))

    m = _PLAIN_RE.search(text)
    if m:
        v = int(m.group(1).replace(",", ""))
        return (v, f"${v:,}")

    return (None, None)


# Category keyword rules. Order matters — first match wins, so most specific
# signals (banking/structure, country attribution) are checked before broad
# governance language. Unmatched events get "uncategorized" so they're visibly
# flagged for review rather than silently bucketed into governance.
_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("fund_structure", (
        "jpmorgan", "world bank", "grad fund", "trustee",
        "intermediary fund", "banking for",
    )),
    ("gulf_pledge", (
        "uae", "saudi", "qatar", "kuwait", "bahrain",
        "oman", "emirates", "gulf",
    )),
    ("us_taxpayer", (
        "state department", "state dept", "treasury",
        "appropriation", "appropriated", "taxpayer",
        "u.s. taxpayer", "trump pledges $", "trump announces $",
        "international disaster assistance",
    )),
    ("international", (
        "fifa", "united nations", " u.n.", "ocha", "european union",
    )),
    ("governance", (
        "charter", "mandate", "executive order", "resolution",
        "oversight", "declined", "immunity", "lawsuit",
        "sen.", "senator", "congressional", "congress",
    )),
)


def categorize(title: str, detail: str = "") -> str:
    """Best-effort classifier. Returns 'uncategorized' on no match."""
    text = f"{title} {detail}".lower()
    for category, keywords in _CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            return category
    return "uncategorized"


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


def event_hash(event: dict) -> str:
    """Stable hash over normalized title + date + amount for dedup."""
    title = _normalize_title(event.get("title", ""))
    date = event.get("date", "")
    amount = event.get("amount")
    amount_str = str(amount) if amount is not None else "null"
    return sha256(f"{title}|{date}|{amount_str}".encode("utf-8")).hexdigest()


def dedup(new_events: list[dict], existing: list[dict]) -> list[dict]:
    """Return events from `new_events` not already present in `existing`.

    Also dedupes within `new_events` itself (same query rotation can return the
    same article twice).
    """
    seen = {event_hash(e) for e in existing}
    out: list[dict] = []
    for e in new_events:
        h = event_hash(e)
        if h not in seen:
            seen.add(h)
            out.append(e)
    return out


_TRUSTED_SUBSTRINGS: tuple[str, ...] = (
    "reuters", "associated press", "pbs", "npr", "semafor",
    "carnegie", "world bank", "senate.gov",
)


def is_trusted(source_name: str | None) -> bool:
    """Source-level trust gate per CLAUDE.md.

    Trusted sources auto-promote to bop_finances.json; everything else queues
    in candidates.json for manual review.
    """
    if not source_name:
        return False
    name = source_name.lower().strip()
    return any(s in name for s in _TRUSTED_SUBSTRINGS)
