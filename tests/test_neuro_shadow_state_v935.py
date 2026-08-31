import math

from backend.neuro_shadow_state_v935 import (
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    build_shadow_outcomes,
    shadow_probability,
)


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


def test_shadow_state_is_explicitly_non_production():
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False


def test_shadow_outcomes_retain_later_sets_and_player_game_totals():
    outcomes = build_shadow_outcomes(_match())
    assert outcomes
    assert math.isclose(sum(o["prob"] for o in outcomes), 1.0, rel_tol=0, abs_tol=1e-9)
    assert all(o["set2"] is not None for o in outcomes)
    assert all(o["p1_total_games"] + o["p2_total_games"] == o["total_games"] for o in outcomes)
    assert any(o["set3"] is not None for o in outcomes)
    assert all(o["set2_winner"] in {1, 2} for o in outcomes)


def test_new_shadow_marginals_are_real_probabilities():
    for market, kwargs in (
        ("set2_winner", {"side": 1}),
        ("set2_total", {"line": 9.5, "pick": "over"}),
        ("set3_total", {"line": 9.5, "pick": "under"}),
        ("player_total_games", {"side": 1, "line": 12.5, "pick": "over"}),
        ("match_game_handicap", {"side": 1, "line": -1.5}),
    ):
        p = shadow_probability(_match(), market, **kwargs)
        assert p is not None
        assert 0.0 <= p <= 1.0


def test_unknown_market_never_gets_a_fabricated_probability():
    assert shadow_probability(_match(), "future_unknown", side=1, line=1.5) is None
