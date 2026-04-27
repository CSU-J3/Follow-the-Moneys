"""Google News RSS collector.

Five query rotations matching the searches advertised in docs/index.html:
"Board of Peace" + {pledge, transfer, billion, fund, allocate}.

Returns event dicts with the data shape from CLAUDE.md. Items without a
parseable dollar amount are dropped — the tracker tracks money, and a
no-amount BoP article is noise the manual review queue shouldn't have to
filter out by hand.

Known limitation — Phase 4 paragraph parsing:
  parse_amount() reads only headline + RSS summary. An article that
  mentions "Board of Peace" alongside an unrelated dollar figure (e.g. a
  Trump-admin policy roundup that lists both BoP and a separate $625M
  coal-mining allocation) will produce a spurious event. The fix is to
  fetch the article body and require paragraph-level co-occurrence of
  "Board of Peace" and the dollar figure before promoting an item. Tracked
  for Phase 4 once the direct-source collectors land.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

import feedparser

from collectors.bop_collector_utils import categorize, parse_amount

logger = logging.getLogger(__name__)

QUERIES: tuple[str, ...] = (
    '"Board of Peace" pledge',
    '"Board of Peace" transfer',
    '"Board of Peace" billion',
    '"Board of Peace" fund',
    '"Board of Peace" allocate',
)

_FEED_URL = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
_USER_AGENT = "FollowTheMoneys/0.1 (+https://github.com/CSU-J3/Follow-the-Moneys)"
_HTTP_TIMEOUT = 20


def _fetch_feed(query: str) -> feedparser.FeedParserDict | None:
    url = _FEED_URL.format(q=quote(query))
    try:
        req = Request(url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            body = resp.read()
    except Exception as e:
        logger.warning("fetch failed for query %r: %s", query, e)
        return None
    return feedparser.parse(body)


def _entry_to_event(entry, query: str) -> dict | None:
    title = (entry.get("title") or "").strip()
    if not title:
        return None

    summary = (entry.get("summary") or "").strip()
    amount, amount_display = parse_amount(f"{title} {summary}")
    if amount is None:
        return None

    # Google News RSS exposes the originating outlet under entry.source.title;
    # fall back to a generic label so dedup and trust-gating still have
    # something to key on.
    source_name = "Google News"
    source = entry.get("source")
    if source and source.get("title"):
        source_name = source["title"]

    pub_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub_struct:
        date = datetime(*pub_struct[:6], tzinfo=timezone.utc).date().isoformat()
    else:
        date = datetime.now(timezone.utc).date().isoformat()

    return {
        "id": None,  # assigned by orchestrator after dedup
        "date": date,
        "title": title,
        "amount": amount,
        "amount_display": amount_display,
        "category": categorize(title, summary),
        "status": None,
        "detail": summary,
        "sources": [{"name": source_name, "url": entry.get("link", "")}],
        "_collector": "news",
        "_query": query,
    }


def collect() -> list[dict]:
    """Run all query rotations. Returns deduped candidate events; never raises."""
    out: list[dict] = []
    for query in QUERIES:
        feed = _fetch_feed(query)
        if feed is None:
            continue
        for entry in feed.entries:
            try:
                event = _entry_to_event(entry, query)
            except Exception as e:
                logger.warning("malformed entry under %r: %s", query, e)
                continue
            if event is not None:
                out.append(event)
    logger.info("news_collector produced %d candidate events", len(out))
    return out
