# Follow the money. Receipts & no peace.

$19.75 billion committed to the Board of Peace. $1.25 billion moved out of disaster relief and peacekeeping accounts. Zero congressional votes. Zero independent audits. Zero dollars confirmed reaching Gaza.

This is the only public ledger.  



## What this is

An automated financial tracker for every pledge, transfer, and reallocation flowing through Trump's Board of Peace for Gaza. Three Python collectors scrape primary sources every 6 hours, extract dollar amounts, categorize events, and push updates to a static site on GitHub Pages. No manual entry. No editorial filtering. Just the money.

## What it tracks

**U.S. taxpayer money:** The $10B pledge (no congressional approval, no funding source identified). The $1.25B State Dept reallocation ($1B from international disaster assistance, $200M from peacekeeping, $50M from international orgs). All of it moved without a vote.

**Country membership pledges:** $1B buys a permanent seat. UAE ($2.7B), Saudi Arabia ($1B), Qatar ($1B), Kuwait ($1B). Five more countries lumped into a $7B total with no individual breakdowns. Azerbaijan disputed being included.

**Fund structure:** The World Bank's GRAD Fund operates as a "limited trustee" with no fiduciary responsibility after disbursement. JPMorgan is in talks to bank for the BoP while Trump simultaneously sues them for $5B. The Carnegie Endowment warns the whole thing "will likely devolve into Trump's private enterprise" when the UN mandate expires.

**Governance:** Executive orders, charter signatories, the 16 countries that walked away, Senate oversight letters that went unanswered, and legislative responses.

**International:** FIFA's $75M stadium deal. OCHA's $2B fundraising target. Japan's donor conference with no date and no target.

## Sources

Collectors pull from 8 monitored sources across 3 collection methods:

| Method | Source | What it watches |
|--------|--------|----------------|
| RSS | Google News | 5 query rotations: "Board of Peace" + financial keywords |
| API | Wikipedia: Board of Peace | Revision diffs for financial content changes |
| API | Wikipedia: Gaza peace plan | Same diff tracking for the broader article |
| Direct | Carnegie Endowment | New BoP analyses and policy briefs |
| Direct | Semafor | Investigative reporting on BoP financial flows |
| Direct | World Bank GRAD Fund | Content-hash change detection |
| Direct | Sen. Cortez Masto | Press releases (BoP, Gaza, LIHEAP, foreign aid) |
| Direct | Sen. Markey | Press releases (BoP, Gaza, oversight) |

Trusted sources (Reuters, AP, PBS, NPR, Semafor, Carnegie, Senate.gov, World Bank) auto-add when financial data is detected. Everything else goes to `candidates.json` for review.

## Architecture

```
bop-tracker/
├── docs/                    # GitHub Pages serves from this directory
│   ├── index.html          # Tracker (seed data embedded, fetches data.json for updates)
│   └── data.json            # Auto-updated by collectors
├── data/
│   ├── bop_finances.json    # Primary data store (21 events at launch)
│   ├── candidates.json      # Pending events for review
│   └── last_run.json        # Collection run log
├── collectors/
│   ├── run_all.py           # Orchestrator
│   ├── news_collector.py    # Google News RSS
│   ├── wikipedia_collector.py   # MediaWiki API
│   ├── source_collector.py      # Direct page monitoring
│   └── bop_collector_utils.py   # Amount extraction, categorization, dedup
└── .github/workflows/
    └── collect-and-deploy.yml   # Runs every 6 hours, commits data, deploys site
```

## Setup

1. Create repo on GitHub
2. Push this directory
3. Settings → Pages → Source: **GitHub Actions**
4. Done. Runs itself.

Manual trigger: Actions → "BoP Financial Tracker" → Run workflow

Local testing:
```bash
cd collectors
python run_all.py
```

## Data format

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

Categories: `us_taxpayer`, `gulf_pledge`, `international`, `governance`, `fund_structure`

Status: `transferred`, `pledged`, `target`, `operational`, or `null`

## License

Public accountability project. Use it, fork it, build on it.

— CJ / [das_DEMARC:/](https://dasdemarc.substack.com)
