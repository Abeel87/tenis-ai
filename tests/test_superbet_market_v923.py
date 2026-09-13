from __future__ import annotations

from backend import superbet_market_mapping as mapping
from backend.superbet_market_audit import (
    VERSION,
    _raw_families,
    sanitize_with_audit,
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
    out = sanitize_with_audit(_fixture(), _meta(), mapping._sanitize_fixture)
    assert out is not None
    assert {(row["market"], row["pick"]) for row in out["canonical_selections"]} == {
        ("match_winner", "Alpha"),
        ("match_winner", "Beta"),
    }
    assert out["raw_market_family_count"] == 2
    assert out["unrecognized_market_family_count"] == 1
    assert out["raw_family_audit_version"] == VERSION
    assert out["unrecognized_market_families"][0]["market_name"] == "Race To Three Games First Set"


def test_winner_pick_canonicalizes_feed_middle_name_expansion():
    assert mapping._winner_pick(
        "Jay Dylan Hara Friend",
        "opaque-2",
        "Maks Kasnikowski",
        "Jay Friend",
    ) == "Jay Friend"
    assert mapping._winner_pick(
        "Friend, Jay Dylan Hara",
        "opaque-2",
        "Maks Kasnikowski",
        "Jay Friend",
    ) == "Jay Friend"


def test_winner_pick_does_not_guess_when_expanded_name_matches_both_players():
    assert mapping._winner_pick(
        "Jay Dylan Hara Friend",
        "opaque",
        "Jay Friend",
        "Jay Hara",
    ) == "Jay Dylan Hara Friend"


def test_partial_match_winner_variant_is_suppressed_fail_closed():
    fixture = {
        "p1": "Malygina, Elena",
        "p2": "Pereira de Aguiar, Giulia",
        "canonical_selections": [
            {
                "market": "match_winner",
                "market_id": "121",
                "pick": "Pereira de Aguiar, Giulia",
                "operator_available": True,
            },
            {
                "market": "set1_total",
                "market_id": "555",
                "pick": "over",
                "line": 8.5,
                "operator_available": True,
            },
        ],
    }
    cleaned, suppressed = mapping._suppress_incomplete_match_winner_groups(fixture)
    assert suppressed == 1
    assert all(row["market"] != "match_winner" for row in cleaned["canonical_selections"])
    assert cleaned["canonical_selections"][0]["market"] == "set1_total"
    assert cleaned["suppressed_incomplete_match_winner_markets"] == 1


def test_complete_match_winner_variant_is_preserved():
    fixture = {
        "p1": "Malygina, Elena",
        "p2": "Pereira de Aguiar, Giulia",
        "canonical_selections": [
            {"market": "match_winner", "market_id": "121", "pick": "Malygina, Elena"},
            {"market": "match_winner", "market_id": "121", "pick": "Pereira de Aguiar, Giulia"},
        ],
    }
    cleaned, suppressed = mapping._suppress_incomplete_match_winner_groups(fixture)
    assert suppressed == 0
    assert cleaned == fixture


def test_global_audit_aggregates_same_unknown_family_across_fixtures():
    one = sanitize_with_audit(_fixture(), _meta(), mapping._sanitize_fixture)
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

    source = (Path(__file__).resolve().parents[1] / "backend" / "superbet_market_audit.py").read_text(encoding="utf-8").casefold()
    for token in ("urlopen", "requests.get", "httpx", "aiohttp", "urllib.request"):
        assert token not in source
    assert '"additional_external_requests": 0' in source
