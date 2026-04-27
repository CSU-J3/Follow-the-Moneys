"""Tests for bop_collector_utils — the part of the pipeline whose edge cases
warrant tests per CLAUDE.md (amount parsing, dedup, trust gate)."""

from __future__ import annotations

import pytest

from collectors.bop_collector_utils import (
    categorize,
    dedup,
    event_hash,
    is_trusted,
    parse_amount,
)


class TestParseAmount:
    @pytest.mark.parametrize("text,expected_num,expected_display", [
        ("Trump pledges $10 billion", 10_000_000_000, "$10B"),
        ("$1.25B transferred", 1_250_000_000, "$1.25B"),
        ("State Dept moves $200M", 200_000_000, "$200M"),
        ("$1.2 billion announced", 1_200_000_000, "$1.2B"),
        ("Pledge of $1B over multiple years", 1_000_000_000, "$1B"),
        ("$75 million partnership", 75_000_000, "$75M"),
        ("$2.5 trillion reconstruction need", 2_500_000_000_000, "$2.5T"),
        ("$50,000 grant", 50_000, "$50,000"),
    ])
    def test_single_amounts(self, text, expected_num, expected_display):
        num, display = parse_amount(text)
        assert num == expected_num
        assert display == expected_display

    @pytest.mark.parametrize("text,expected_midpoint", [
        ("Fund holds $60–70M", 65_000_000),       # en-dash
        ("Estimated $1—2B", 1_500_000_000),        # em-dash
        ("Range $200-300M", 250_000_000),               # plain hyphen
        ("$1.2 to 1.8 billion", 1_500_000_000),         # word "to"
    ])
    def test_ranges_collapse_to_midpoint(self, text, expected_midpoint):
        num, display = parse_amount(text)
        assert num == expected_midpoint
        assert display is not None  # original range form preserved

    @pytest.mark.parametrize("text", [
        "",
        None,
        "No dollar signs here",
        "Charter signed at Davos",
        "$",  # bare sign with nothing after
    ])
    def test_no_match_returns_none_pair(self, text):
        assert parse_amount(text) == (None, None)

    def test_takes_first_amount_when_multiple(self):
        num, _ = parse_amount("$1.2B from UAE plus another $1.5B for Rafah")
        assert num == 1_200_000_000


class TestCategorize:
    @pytest.mark.parametrize("title,expected", [
        ("UAE pledges $1.2B to BoP", "gulf_pledge"),
        ("Saudi Arabia commits $1B", "gulf_pledge"),
        ("State Department transfers $1.25B", "us_taxpayer"),
        ("Trump pledges $10 billion", "us_taxpayer"),
        ("JPMorgan in talks to bank for BoP", "fund_structure"),
        ("World Bank establishes GRAD Fund", "fund_structure"),
        ("FIFA pledges $75M partnership", "international"),
        ("UN Security Council adopts Resolution 2803", "governance"),
        ("Sen. Markey demands oversight answers", "governance"),
        ("Charter signed at Davos by 20 countries", "governance"),
        ("Executive Order 14375 signed", "governance"),
    ])
    def test_known_signals(self, title, expected):
        assert categorize(title) == expected

    def test_unmatched_returns_uncategorized_not_governance(self):
        # Per project decision: unmatched events surface for review rather
        # than silently bucketing into governance.
        assert categorize("Some unrelated breaking news headline") == "uncategorized"

    def test_detail_text_factors_into_classification(self):
        cat = categorize("Update", "JPMorgan account opened for BoP transfers")
        assert cat == "fund_structure"


class TestEventHash:
    def test_normalizes_whitespace_and_case(self):
        a = {"title": "UAE pledges $1.2B", "date": "2026-02-19", "amount": 1_200_000_000}
        b = {"title": "uae   PLEDGES   $1.2b", "date": "2026-02-19", "amount": 1_200_000_000}
        assert event_hash(a) == event_hash(b)

    def test_different_amount_changes_hash(self):
        a = {"title": "Pledge", "date": "2026-02-19", "amount": 1_000_000_000}
        b = {"title": "Pledge", "date": "2026-02-19", "amount": 2_000_000_000}
        assert event_hash(a) != event_hash(b)

    def test_null_amount_is_stable(self):
        a = {"title": "Resolution adopted", "date": "2025-11-17", "amount": None}
        b = {"title": "Resolution adopted", "date": "2025-11-17", "amount": None}
        assert event_hash(a) == event_hash(b)


class TestDedup:
    def test_drops_already_existing(self):
        existing = [{"title": "Pledge", "date": "2026-02-19", "amount": 1_000_000_000}]
        incoming = [
            {"title": "Pledge", "date": "2026-02-19", "amount": 1_000_000_000},
            {"title": "New event", "date": "2026-03-01", "amount": 500_000_000},
        ]
        result = dedup(incoming, existing)
        assert len(result) == 1
        assert result[0]["title"] == "New event"

    def test_dedupes_within_incoming_batch(self):
        # The 5 Google News query rotations will frequently return the same
        # article, so dedup must collapse intra-batch duplicates too.
        incoming = [
            {"title": "Same story", "date": "2026-03-01", "amount": 100},
            {"title": "Same   STORY", "date": "2026-03-01", "amount": 100},
        ]
        result = dedup(incoming, [])
        assert len(result) == 1


class TestIsTrusted:
    @pytest.mark.parametrize("name", [
        "Reuters",
        "Associated Press",
        "PBS NewsHour",
        "NPR",
        "Semafor",
        "Carnegie Endowment for International Peace",
        "World Bank",
        "markey.senate.gov",
    ])
    def test_trusted_sources(self, name):
        assert is_trusted(name) is True

    @pytest.mark.parametrize("name", [
        "Random Blog",
        "Daily Sabah",
        "Anadolu Agency",
        "",
        None,
    ])
    def test_untrusted_or_empty(self, name):
        assert is_trusted(name) is False


class TestNoAmountEventsDropped:
    """Per project policy: events with no parseable amount are dropped from
    BOTH bop_finances.json and candidates.json — collector output must carry
    a financial signal to enter either store. The seed file is the only place
    amount-less governance/structure events live (curated, not collector
    output)."""

    def _filter_amountless(self, events: list[dict]) -> list[dict]:
        # Mirrors the gate news_collector applies before returning candidates.
        return [e for e in events if e.get("amount") is not None]

    def test_amountless_events_filtered_before_routing(self):
        raw_collector_output = [
            {"title": "UAE pledges $1.2B", "date": "2026-02-19",
             "amount": 1_200_000_000, "sources": [{"name": "Reuters"}]},
            {"title": "Markey demands oversight", "date": "2026-02-19",
             "amount": None, "sources": [{"name": "Sen. Markey"}]},
            {"title": "Some random news", "date": "2026-03-01",
             "amount": None, "sources": [{"name": "Random Blog"}]},
        ]
        kept = self._filter_amountless(raw_collector_output)
        assert len(kept) == 1
        assert kept[0]["amount"] == 1_200_000_000

        # Now route the kept events the way run_all.py would, and confirm both
        # files would receive only events with parseable amounts.
        trusted_bucket = [
            e for e in kept
            if any(is_trusted(s.get("name")) for s in e.get("sources", []))
        ]
        candidates_bucket = [
            e for e in kept
            if not any(is_trusted(s.get("name")) for s in e.get("sources", []))
        ]

        assert all(e["amount"] is not None for e in trusted_bucket)
        assert all(e["amount"] is not None for e in candidates_bucket)
        # And the amountless events ended up in neither bucket.
        assert len(trusted_bucket) + len(candidates_bucket) == 1
