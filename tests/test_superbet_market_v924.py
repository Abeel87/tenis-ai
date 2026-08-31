from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import superbet_market_context_v924 as ctx


def test_all_families_found_by_v923_audit_now_have_canonical_mapping():
    expected = {
        "Any Set To Nil": "any_set_to_nil",
        "Correct Score Second Set": "set2_exact_score",
        "Correct Score Second Set After Four Games": "set2_game_state",
        "Correct Score Second Set After Six Games": "set2_game_state",
        "Exact Sets": "exact_sets",
        "Odd Even Games": "match_games_parity",
        "Odd Even Games First Set": "set1_games_parity",
        "Odd Even Games Second Set": "set2_games_parity",
        "Participant 1 To Exactly Win One Set": "p1_exactly_1_set",
        "Participant 1 To Exactly Win Two Sets": "p1_exactly_2_sets",
        "Participant 1 To Win a Set": "p1_wins_a_set",
        "Participant 2 To Exactly Win One Set": "p2_exactly_1_set",
        "Participant 2 To Exactly Win Two Sets": "p2_exactly_2_sets",
        "Participant 2 To Win a Set": "p2_wins_a_set",
        "Set Handicap": "set_handicap",
    }
    for name, market in expected.items():
        canonical, checkpoint, _ = ctx.canonical_market(name)
        assert canonical == market, name
        if "After Four" in name:
            assert checkpoint == 4
        if "After Six" in name:
            assert checkpoint == 6


def test_new_outcome_parsers_keep_semantics_explicit():
    assert ctx.selection_pick("set2_exact_score", "6:4", None, "A", "B") == "6:4"
    assert ctx.selection_pick("set2_game_state", "2-2", None, "A", "B") == "2:2"
    assert ctx.selection_pick("match_games_parity", "Odd", None, "A", "B") == "odd"
    assert ctx.selection_pick("set1_games_parity", "Even", None, "A", "B") == "even"
    assert ctx.selection_pick("exact_sets", "3 Sets", None, "A", "B") == "3"
    assert ctx.selection_pick("any_set_to_nil", "Yes", None, "A", "B") == "yes"
    assert ctx.selection_pick("p1_wins_a_set", "No", None, "A", "B") == "no"
    assert ctx.selection_pick("set_handicap", "2", None, "A", "B") == "B"


def test_set_handicap_uses_catalogue_line_and_flips_participant_two_sign():
    with ctx._patched_runtime():
        p1, source1 = ctx.v913._market_line(
            "set_handicap", {"handicap": -1.5}, "1", None, pick="A", p1="A", p2="B"
        )
        p2, source2 = ctx.v913._market_line(
            "set_handicap", {"handicap": -1.5}, "2", None, pick="B", p1="A", p2="B"
        )
    assert p1 == -1.5
    assert p2 == 1.5
    assert source1 == source2 == "oddspapi_market_handicap"


def test_wrapper_has_zero_extra_request_contract_and_no_network_client():
    source = (BACKEND / "superbet_market_context_v924.py").read_text(encoding="utf-8").lower()
    assert '"additional_external_requests"] = 0' in source
    for token in ("urlopen", "requests.get", "httpx", "aiohttp"):
        assert token not in source


def _total_meta(catalogue_line=15.5):
    return {
        "13000": {
            "marketName": "Total Games Over Under",
            "marketType": "total-games",
            "handicap": catalogue_line,
            "outcomes": {
                "13000": {"outcomeName": "Over"},
                "13001": {"outcomeName": "Under"},
            },
        }
    }


def _total_row(bookmaker_market_id="fixture-total-18.5", over_id="sb-over-18.5", under_id="sb-under-18.5"):
    return {
        "fixtureId": "fixture-1",
        "participant1Name": "Alpha",
        "participant2Name": "Beta",
        "startTime": "2026-08-30T18:00:00Z",
        "bookmakerOdds": {
            "superbet.pl": {
                "bookmakerIsActive": True,
                "suspended": False,
                "markets": {
                    "13000": {
                        "bookmakerMarketId": bookmaker_market_id,
                        "marketActive": True,
                        "outcomes": {
                            "13000": {"players": {"0": {"active": True, "bookmakerOutcomeId": over_id, "mainLine": True}}},
                            "13001": {"players": {"0": {"active": True, "bookmakerOutcomeId": under_id, "mainLine": True}}},
                        },
                    }
                },
            }
        },
    }


def test_current_fixture_line_overrides_catalogue_metadata():
    out = ctx.mapped_sanitize(_total_row(), _total_meta(15.5))
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["pick"], x["line"]) for x in selections} == {("over", 18.5), ("under", 18.5)}
    assert {x["operator_line_source"] for x in selections} == {"oddspapi_fixture_text_line"}
    assert all(x["fixture_line_verified"] is True for x in selections)


def test_active_fixture_market_id_uses_its_own_catalogue_handicap_when_ids_are_opaque():
    out = ctx.mapped_sanitize(
        _total_row(bookmaker_market_id="opaque", over_id="opaque-over", under_id="opaque-under"),
        _total_meta(22.5),
    )
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["pick"], x["line"]) for x in selections} == {("over", 22.5), ("under", 22.5)}
    assert {x["operator_line_source"] for x in selections} == {"oddspapi_active_fixture_market_id_handicap"}
    assert all(x["fixture_line_verified"] is True for x in selections)
    assert out["suppressed_line_selections_without_fixture_evidence"] == 0


def test_direct_outcome_carriers_keep_real_active_total_lines():
    row = _total_row(bookmaker_market_id="opaque")
    market = row["bookmakerOdds"]["superbet.pl"]["markets"]["13000"]
    market["outcomes"] = {
        "13000": {"active": True, "bookmakerOutcomeId": "over", "mainLine": True},
        "13001": {"active": True, "bookmakerOutcomeId": "under", "mainLine": True},
    }
    out = ctx.mapped_sanitize(row, _total_meta(23.5))
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["pick"], x["line"]) for x in selections} == {("over", 23.5), ("under", 23.5)}
    assert {x["operator_line_source"] for x in selections} == {"oddspapi_active_fixture_market_id_handicap"}
    assert all(x["fixture_line_verified"] is True for x in selections)


def test_unreferenced_catalogue_market_cannot_create_a_selection():
    row = _total_row(bookmaker_market_id="opaque", over_id="opaque-over", under_id="opaque-under")
    row["bookmakerOdds"]["superbet.pl"]["markets"] = {}
    out = ctx.mapped_sanitize(row, _total_meta(22.5))
    assert out is not None
    assert out["canonical_selections"] == []


def test_structured_current_fixture_line_is_authoritative():
    row = _total_row(bookmaker_market_id="fixture-total-18.5")
    row["bookmakerOdds"]["superbet.pl"]["markets"]["13000"]["line"] = 20.5
    out = ctx.mapped_sanitize(row, _total_meta(15.5))
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["pick"], x["line"]) for x in selections} == {("over", 20.5), ("under", 20.5)}
    assert {x["operator_line_source"] for x in selections} == {"oddspapi_fixture_market_line"}


def test_strict_contract_forbids_non_fixture_fallbacks():
    source = (BACKEND / "superbet_market_context_v924.py").read_text(encoding="utf-8")
    assert '"current_fixture_evidence_required": True' in source
    assert '"active_fixture_market_id_metadata_allowed": True' in source
    assert '"catalogue_fallback_allowed": False' in source
    assert '"model_line_fallback_allowed": False' in source
    assert '"nearest_line_fallback_allowed": False' in source
