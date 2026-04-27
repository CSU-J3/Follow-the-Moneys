# CLAUDE.md

Context for Claude Code sessions on this repository.

## What this project is

This is a fork of `mehidk69/Follow-the-Moneys`, an automated financial tracker for the Trump administration's Board of Peace for Gaza. It's a public accountability project: scrape primary sources, extract financial events, publish a static site as a public ledger.

The fork lives at `CSU-J3/Follow-the-Moneys`. The live site is on GitHub Pages.

## Important: the README is aspirational

The upstream README describes a full architecture (Python collectors, data files, GitHub Actions workflow). **None of it actually exists.** When this repo was forked, only `README.md` and `index.html` were present. The 21 events shown on the live site are hardcoded into the HTML.

The job is to build the architecture the README describes.

## Who I am and why this project matters

I'm an MPPA student at Colorado State University. This project supports a public-facing research portfolio (Substack + LinkedIn) on financial governance and accountability in post-conflict reconstruction. The tracker is the empirical foundation for a comparative analysis of the BoP against prior reconstruction vehicles (CPA Iraq, ARTF Afghanistan, PA donor coordination, Lebanon).

Audience for the eventual writing: oversight professionals, policy researchers at think tanks, congressional staff, accountability journalists.

This means the tracker needs to be defensible as a research instrument, not just a working scraper. Provenance, reproducibility, and clear editorial standards matter.

## Architecture target

```
Follow-the-Moneys/
├── README.md
├── CLAUDE.md
├── requirements.txt
├── site/
│   ├── index.html          # Existing landing page; fetches data.json on load
│   └── data.json           # Auto-generated copy of bop_finances.json
├── data/
│   ├── bop_finances.json   # Verified events (primary data store)
│   ├── candidates.json     # Pending events for manual review
│   └── last_run.json       # Per-collector run log
├── collectors/
│   ├── run_all.py                  # Orchestrator
│   ├── news_collector.py           # Google News RSS
│   ├── wikipedia_collector.py      # MediaWiki API revision diffs
│   ├── source_collector.py         # Direct page monitoring (hash-based)
│   └── bop_collector_utils.py      # Amount extraction, categorization, dedup
└── .github/workflows/
    └── collect-and-deploy.yml      # 6-hour cron, commits data, deploys site
```

## Build plan (5 phases)

Build in order. Ship after Phase 1 (narrow but working) and again after Phase 3 (real automation, the credible "ship" point for portfolio publishing).

1. **Phase 0 — Scaffolding.** Directory structure, move `index.html` into `site/`, empty `requirements.txt`.
2. **Phase 1 — Data layer + one collector.** Extract the 21 hardcoded events into `bop_finances.json`. Build `bop_collector_utils.py` (amount extraction, categorization, dedup) and `news_collector.py` (Google News RSS). Wire up `run_all.py`. Goal: running locally produces new entries in `candidates.json`.
3. **Phase 2 — Static site wiring.** `index.html` fetches `site/data.json`; `run_all.py` writes that file as the last step.
4. **Phase 3 — GitHub Actions.** `collect-and-deploy.yml` with 6-hour cron, manual trigger, `contents: write` permission. Commits use `[skip ci]` to prevent loops. **First credible ship point.**
5. **Phase 4 — Wikipedia + direct source collectors.** MediaWiki API for revision diffs. Content-hash monitoring for Carnegie, Semafor, Senate.gov, World Bank GRAD Fund.
6. **Phase 5 — Candidates review system.** A way to review and promote pending events. Lightweight v1: a `review.html` that generates copy-paste JSON for a PR. Out of scope for now: a full Flask/FastAPI review app.

## Data format (per the README)

```json
{
  "id": "ev-020",
  "date": "2026-03-26",
  "title": "State Dept transfers $1.25B to BoP",
  "amount": 1250000000,
  "amount_display": "$1.25B",
  "category": "us_taxpayer",
  "status": "transferred",
  "detail": "$1B from International Disaster Assistance, $200M from Peacekeeping...",
  "sources": [{"name": "Semafor", "url": "https://..."}]
}
```

Categories: `us_taxpayer`, `gulf_pledge`, `international`, `governance`, `fund_structure`.
Statuses: `transferred`, `pledged`, `target`, `operational`, or `null`.

## Sources to monitor

| Method | Source | What to watch |
|--------|--------|---------------|
| RSS | Google News | "Board of Peace" + financial keywords |
| API | Wikipedia: Board of Peace | Revision diffs for financial content |
| API | Wikipedia: Gaza peace plan | Same |
| Direct | Carnegie Endowment | New BoP analyses and policy briefs |
| Direct | Semafor | Investigative reporting on BoP financial flows |
| Direct | World Bank GRAD Fund | Content-hash change detection |
| Direct | Sen. Cortez Masto | Press releases (BoP, Gaza, LIHEAP, foreign aid) |
| Direct | Sen. Markey | Press releases (BoP, Gaza, oversight) |

Trusted sources (auto-add to `bop_finances.json`): Reuters, AP, PBS, NPR, Semafor, Carnegie, Senate.gov, World Bank.
Everything else goes to `candidates.json` for manual review.

## Constraints

- **Python 3.11+.** Must run in GitHub Actions (`ubuntu-latest` default).
- **No paid APIs.** All sources accessible without keys or with free tiers only.
- **No new dependencies without asking me first.** When adding to `requirements.txt`, surface it for review.
- **Fail gracefully.** One source going down should never break the full run. Each collector wraps its work in try/except and logs to `last_run.json`.
- **Idempotent.** Running the orchestrator twice in a row should not create duplicates. Dedup is keyed on a hash of normalized title + date + amount.
- **No editorial filtering in code.** Trust/distrust is at the source level (which sources auto-promote vs. queue). Do not filter individual events based on content.
- **Don't touch `site/index.html`'s visual design.** The existing landing page is intentionally polished. Add data-fetching JS, but don't rewrite the CSS, change colors, or restructure the layout.

## House style for code

- Type hints on function signatures. Plain dicts/lists for data, not dataclasses unless complexity demands it.
- Logging via the standard `logging` module, not `print()`.
- Pure functions where possible. The collectors should return event lists; orchestration writes to disk.
- Tests where they pay for themselves: definitely on `bop_collector_utils.py` (amount parsing has edge cases). Skip tests for orchestration scaffolding.
- Comments explain *why*, not *what*.

## What's out of scope

- Redesigning the frontend
- Adding authentication, accounts, or user-specific features
- Replacing GitHub Pages with a different host
- Building a real-time interface (6-hour cron is fine)
- Writing the Substack/LinkedIn pieces themselves — that work happens in a separate Claude.ai project
- Any analysis or commentary on the underlying Israel-Palestine conflict, humanitarian conditions, or military strategy

## Working norms

- Propose a plan before executing multi-file changes. I want to approve the approach.
- Show diffs for review before committing. Don't push to `main` without me confirming.
- When debugging, run the actual code and report what happened. Don't speculate about what might be wrong without testing.
- If a phase's scope grows beyond what's described here, stop and surface it rather than expanding silently.
- Commit messages: short, present tense, prefixed with phase number (e.g., "P1: extract seed events into bop_finances.json").
