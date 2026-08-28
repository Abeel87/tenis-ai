from __future__ import annotations

from backend import superbet_market_context_v913 as v913
from backend.superbet_market_context_v923 import (
    VERSION,
    _raw_families,
    _sanitize_with_audit,
    build_audit,
)


def _fixture():
    return {
        "fixtureId": "f-audit",
        "participant1Name": "Alpha",
        "participant2Name": "Beta",
        "startTime": "2026-08-28T18:00:00Z",
        "bookmakerOdds": {
            "superbet.pl": {
                "bookmakerIsActive": True,
                "suspended": False,
                "markets": {
                    "121": {
                        "marketActive": True,
                        "outcomes": {
                            "121": {"players": {"0": {"active": True, "bookmakerOutcomeId": "opaque-1"}}},
                            "122": {"players": {"0": {"active": True, "bookmakerOutcomeId": "opaque-2"}}},
                        },
                    },
                    "9001": {"marketActive": True, "outcomes": {}},
                    "9002": {"marketActive": True, "outcomes": {}},
                    "9999": {"marketActive": False, "outcomes": {}},
                },
            }
        },
    }


def _meta():
    return {
        "121": {
            "marketName": "Winner",
            "marketType": "moneyline",
            "period": "result",
            "playerProp": False,
            "handicap": 0.0,
            "outcomes": {"121": {"outcomeName": "1"}, "122": {"outcomeName": "2"}},
        },
        "9001": {
            "marketName": "Race To Three Games First Set",
            "marketType": "race-games",
            "period": "set1",
            "playerProp": False,
            "handicap": 2.5,
            "outcomes": {},
        },
        "9002": {
            "marketName": "Race To Three Games First Set",
            "marketType": "race-games",
            "period": "set1",
            "playerProp": False,
            "handicap": 3.5,
            "outcomes": {},
        },
        "9999": {
            "marketName": "Inactive Example",
            "marketType": "example",
            "period": "result",
            "playerProp": False,
            "outcomes": {},
        },
    }


def test_raw_family_audit_collapses_line_variants_without_storing_prices():
    families = _raw_families(_fixture(), _meta())
    assert len(families) == 2
    winner = next(row for row in families if row["market_name"] == "Winner")
    unknown = next(row for row in families if row["market_name"] == "Race To Three Games First Set")
    assert winner["recognized"] is True
    assert winner["canonical"] == "match_winner"
    assert unknown["recognized"] is False
    assert unknown["active_market_variants"] == 2
    assert unknown["handicaps"] == [2.5, 3.5]
    assert unknown["sample_market_ids"] == ["9001", "9002"]
    serialized = repr(families).casefold()
    assert "price" not in serialized
    assert "bookmakeroutcomeid" not in serialized


def test_existing_sanitizer_output_is_preserved_and_only_compact_audit_is_added():
    out = _sanitize_with_audit(_fixture(), _meta(), v913._sanitize_fixture)
    assert out is not None
    assert {(row["market"], row["pick"]) for row in out["canonical_selections"]} == {
        ("match_winner", "Alpha"),
        ("match_winner", "Beta"),
    }
    assert out["raw_market_family_count"] == 2
    assert out["unrecognized_market_family_count"] == 1
    assert out["raw_family_audit_version"] == VERSION
    assert out["unrecognized_market_families"][0]["market_name"] == "Race To Three Games First Set"


def test_global_audit_aggregates_same_unknown_family_across_fixtures():
    one = _sanitize_with_audit(_fixture(), _meta(), v913._sanitize_fixture)
    two = dict(one)
    two["fixture_id"] = "f-audit-2"
    report = build_audit([one, two])
    assert report["version"] == VERSION
    assert report["fixtures_with_family_audit"] == 2
    assert report["unique_raw_market_families"] == 2
    assert report["unique_unrecognized_market_families"] == 1
    unknown = report["unrecognized_families"][0]
    assert unknown["market_name"] == "Race To Three Games First Set"
    assert unknown["fixture_count"] == 2
    assert unknown["active_market_variants"] == 4
    assert report["additional_external_requests"] == 0
    assert report["prices_used"] is False
    assert report["contract"]["does_not_request_extra_tennis_data"] is True


def test_audit_module_has_no_network_client_or_direct_request_call():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "backend" / "superbet_market_context_v923.py").read_text(encoding="utf-8").casefold()
    for token in ("urlopen", "requests.get", "httpx", "aiohttp", "urllib.request"):
        assert token not in source
    assert "additional_external_requests\": 0" in source
