import math

from backend.neuro_shadow_market_adapter_v935 import adapt_canonical_selection
from backend.signal_settlement import settle_signal_live
from backend.superbet_market_context import _orient_line


def _match():
    return {
        "p1": "Alpha",
        "p2": "Beta",
        "best_of": 3,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.72},
        "first_set_win": {"Alpha": 0.58, "Beta": 0.42},
        "second_set_win": {"Alpha": 0.55, "Beta": 0.45},
        "third_set_win": {"Alpha": 0.53, "Beta": 0.47},
    }


def _selection(pick, line, outcome_id):
    return {
        "market": "match_game_handicap",
        "pick": pick,
        "line": line,
        "player": None,
        "market_id": "handicap-market",
        "outcome_id": outcome_id,
        "operator_available": True,
        "operator_line_verified": True,
        "fixture_line_verified": True,
    }


def test_market_context_orients_same_catalogue_handicap_to_selected_side_once():
    raw_p1_line = -2.5
    p1 = _orient_line(
        "match_game_handicap", raw_p1_line, "1", "1", "Alpha", "Alpha", "Beta"
    )
    p2 = _orient_line(
        "match_game_handicap", raw_p1_line, "2", "2", "Beta", "Alpha", "Beta"
    )
    assert p1 == -2.5
    assert p2 == 2.5


def test_neuro_shadow_uses_oriented_p2_line_without_flipping_it_again():
    match = _match()
    p1_row = adapt_canonical_selection(match, _selection("Alpha", -2.5, "1"))
    p2_row = adapt_canonical_selection(match, _selection("Beta", 2.5, "2"))
    assert p1_row is not None and p2_row is not None
    assert math.isclose(
        p1_row["probability"] + p2_row["probability"], 1.0, rel_tol=0, abs_tol=1e-9
    )


def test_shared_settlement_matches_same_selected_side_line_contract():
    final = {
        "status": "completed",
        "p1": "Alpha",
        "p2": "Beta",
        "sets": [[6, 4], [6, 4]],
    }
    p1 = settle_signal_live(
        {"market": "match_game_handicap", "pick": "Alpha", "line": -2.5}, final
    )
    p2 = settle_signal_live(
        {"market": "match_game_handicap", "pick": "Beta", "line": 2.5}, final
    )
    assert p1 == "hit"
    assert p2 == "miss"
