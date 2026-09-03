import math

from backend.neuro_shadow_market_adapter import adapt_canonical_selection
from backend.neuro_shadow_state import CANDIDATE_CAPTURE_READY_MARKETS, shadow_probability


def _match(best_of=3):
    return {
        "p1": "Alpha",
        "p2": "Beta",
        "best_of": best_of,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.72},
        "first_set_win": {"Alpha": 0.58, "Beta": 0.42},
        "second_set_win": {"Alpha": 0.55, "Beta": 0.45},
        "third_set_win": {"Alpha": 0.53, "Beta": 0.47},
        "fourth_set_win": {"Alpha": 0.52, "Beta": 0.48},
        "fifth_set_win": {"Alpha": 0.51, "Beta": 0.49},
    }


def _selection(market, pick, *, line=None, verified=True):
    return {
        "market": market,
        "pick": pick,
        "line": line,
        "market_id": f"m-{market}",
        "outcome_id": f"o-{pick}",
        "operator_available": True,
        "operator_line_verified": verified,
    }


def test_large_state_batch_is_capture_ready():
    expected = {
        "set1_game_handicap",
        "set2_game_handicap",
        "set_handicap",
        "match_games_parity",
        "set1_games_parity",
        "set2_games_parity",
        "any_set_to_nil",
    }
    assert expected <= CANDIDATE_CAPTURE_READY_MARKETS


def test_handicap_opposite_sides_are_complementary_on_half_lines():
    cases = (
        ("match_game_handicap", -1.5, 1.5),
        ("set1_game_handicap", -1.5, 1.5),
        ("set2_game_handicap", -1.5, 1.5),
        ("set_handicap", -1.5, 1.5),
    )
    for market, p1_line, p2_line in cases:
        p1 = shadow_probability(_match(), market, side=1, line=p1_line)
        p2 = shadow_probability(_match(), market, side=2, line=p2_line)
        assert p1 is not None and p2 is not None
        assert math.isclose(p1 + p2, 1.0, rel_tol=0, abs_tol=1e-9)


def test_parity_pairs_sum_to_one():
    for market in ("match_games_parity", "set1_games_parity", "set2_games_parity"):
        odd = shadow_probability(_match(), market, pick="odd")
        even = shadow_probability(_match(), market, pick="even")
        assert odd is not None and even is not None
        assert math.isclose(odd + even, 1.0, rel_tol=0, abs_tol=1e-9)


def test_any_set_to_nil_is_exact_for_bo3_and_bo5():
    for best_of in (3, 5):
        yes = shadow_probability(_match(best_of), "any_set_to_nil", pick="yes")
        no = shadow_probability(_match(best_of), "any_set_to_nil", pick="no")
        assert yes is not None and no is not None
        assert 0.0 <= yes <= 1.0
        assert 0.0 <= no <= 1.0
        assert math.isclose(yes + no, 1.0, rel_tol=0, abs_tol=1e-9)


def test_adapter_accepts_new_exact_canonical_state_markets():
    cases = (
        _selection("set1_game_handicap", "Alpha", line=-1.5),
        _selection("set2_game_handicap", "Beta", line=1.5),
        _selection("set_handicap", "Alpha", line=-1.5),
        _selection("match_games_parity", "odd"),
        _selection("set1_games_parity", "even"),
        _selection("set2_games_parity", "odd"),
        _selection("any_set_to_nil", "yes"),
    )
    for selection in cases:
        row = adapt_canonical_selection(_match(), selection)
        assert row is not None
        assert 0.0 <= row["probability"] <= 1.0
        assert row["operator_playable"] is False
        assert row["production_influence"] is False
        assert row["source_model"] == "state_distribution"


def test_adapter_refuses_unverified_handicap_line():
    assert adapt_canonical_selection(
        _match(), _selection("set_handicap", "Alpha", line=-1.5, verified=False)
    ) is None
