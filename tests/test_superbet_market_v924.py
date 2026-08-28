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
