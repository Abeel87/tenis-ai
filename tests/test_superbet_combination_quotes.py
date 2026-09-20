import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import superbet_direct as d


def payload(rows):
    return {"data": [{"eventId": 15000001, "matchName": "A·B", "odds": rows}]}


def combo(uuid="combo-1", price=2.75, status="active", tag="superbets", comps=None):
    comps = comps or [
        {"UUID": "leg-a", "universalMarketID": 521, "universalOutcomeID": 1329},
        {"UUID": "leg-b", "universalMarketID": 1002, "universalOutcomeID": 4263},
    ]
    return {"uuid": uuid, "marketId": d.COMBINATION_MARKET_ID, "outcomeId": 16603,
            "price": price, "status": status, "marketName": "A; B", "name": "A; B",
            "extra": {"tag": tag}, "oddComponents": comps}


def test_extracts_active_prepriced_superbets_with_exact_component_ids():
    out = d.parse_event_combination_quotes(payload([combo()]), event_id="15000001",
                                           observed_at="2026-09-20T21:30:00+00:00")
    assert out["status"] == "OK"
    assert out["quotes_count"] == 1
    q = out["quotes"][0]
    assert q["quote_kind"] == "SUPERBETS_PREPRICED_COMBINATION"
    assert q["combined_odds"] == 2.75
    assert q["component_selection_ids"] == ["leg-a", "leg-b"]
    assert q["operator_verified"] is True
    assert q["observed_at"] == "2026-09-20T21:30:00+00:00"


def test_parser_rejects_inactive_wrong_tag_and_missing_component_identity():
    bad = [
        combo(uuid="inactive", status="inactive"),
        combo(uuid="wrong-tag", tag="other"),
        combo(uuid="missing-id", comps=[{"UUID": "leg-a"}, {"UUID": ""}]),
    ]
    out = d.parse_event_combination_quotes(payload(bad), event_id="15000001",
                                           observed_at="2026-09-20T21:30:00+00:00")
    assert out["quotes"] == []
    assert out["quotes_count"] == 0


def test_exact_component_set_match_is_order_independent_but_not_subset_match():
    quotes = [
        {"operator": "superbet.pl", "quote_kind": "SUPERBETS_PREPRICED_COMBINATION",
         "component_selection_ids": ["leg-b", "leg-a"], "combined_odds": 2.75,
         "operator_verified": True, "freshness_verified": True,
         "source_event_id": "15000001", "odds_timestamp": "2026-09-20T21:30:00+00:00",
         "source": d.EVENT_JSON_SOURCE},
        {"operator": "superbet.pl", "quote_kind": "SUPERBETS_PREPRICED_COMBINATION",
         "component_selection_ids": ["leg-a", "leg-b", "leg-c"], "combined_odds": 4.1,
         "operator_verified": True, "freshness_verified": True,
         "source_event_id": "15000001", "odds_timestamp": "2026-09-20T21:30:00+00:00",
         "source": d.EVENT_JSON_SOURCE},
    ]
    hit = d.exact_combination_quote(quotes, ["leg-a", "leg-b"], event_id="15000001")
    assert hit is not None and hit["combined_odds"] == 2.75
    assert d.exact_combination_quote(quotes, ["leg-a"], event_id="15000001") is None


def test_exact_match_rejects_duplicate_or_wrong_provenance_quotes():
    base = {"operator": "superbet.pl", "quote_kind": "SUPERBETS_PREPRICED_COMBINATION",
            "component_selection_ids": ["leg-a", "leg-b"], "combined_odds": 2.75,
            "operator_verified": True, "freshness_verified": True,
            "source_event_id": "15000001", "odds_timestamp": "2026-09-20T21:30:00+00:00",
            "source": d.EVENT_JSON_SOURCE}
    assert d.exact_combination_quote([base, dict(base)], ["leg-a", "leg-b"], event_id="15000001") is None
    wrong = dict(base, quote_kind="OTHER")
    assert d.exact_combination_quote([wrong], ["leg-a", "leg-b"], event_id="15000001") is None
    wrong_operator = dict(base, operator="other")
    assert d.exact_combination_quote([wrong_operator], ["leg-a", "leg-b"], event_id="15000001") is None
    stale = dict(base, freshness_verified=False)
    assert d.exact_combination_quote([stale], ["leg-a", "leg-b"], event_id="15000001") is None
