from backend.symphony2_state import (
    _match_game_outcomes,
    _set2_outcomes,
    build_outcomes,
    joint_probability,
    marginal_probability,
)


def _match(best_of=3):
    return {
        "p1": "Alpha",
        "p2": "Beta",
        "best_of": best_of,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.74},
        "first_set_win": {"Alpha": 0.58, "Beta": 0.42},
        "second_set_win": {"Alpha": 0.56, "Beta": 0.44},
        "third_set_win": {"Alpha": 0.54, "Beta": 0.46},
        "fourth_set_win": {"Alpha": 0.54, "Beta": 0.46},
        "fifth_set_win": {"Alpha": 0.53, "Beta": 0.47},
    }


def _p(match, outcomes, market, pick, **extra):
    return marginal_probability(match, {"market": market, "pick": pick, **extra}, outcomes)


def test_legacy_shared_state_stays_available_and_new_states_are_separate():
    match = _match()
    assert build_outcomes(match)
    assert _set2_outcomes(match)
    match_states = _match_game_outcomes(match)
    assert match_states
    assert all(o["p1_games"] + o["p2_games"] == o["total_games"] for o in match_states)


def test_bo5_match_family_state_is_bounded_to_sufficient_statistics():
    outcomes = _match_game_outcomes(_match(best_of=5))
    assert outcomes
    assert all(o["set_count"] in {3, 4, 5} for o in outcomes)
    assert len(outcomes) < 50000


def test_set2_winner_and_total_are_true_complements_on_half_lines():
    match = _match()
    outcomes = build_outcomes(match)
    a = _p(match, outcomes, "set2_winner", "Alpha")
    b = _p(match, outcomes, "set2_winner", "Beta")
    over = _p(match, outcomes, "set2_total", "over", line=9.5)
    under = _p(match, outcomes, "set2_total", "under", line=9.5)
    assert a is not None and b is not None and abs(a + b - 1.0) < 1e-9
    assert over is not None and under is not None and abs(over + under - 1.0) < 1e-9


def test_set2_exact_score_and_exact_sets_have_real_state_probability():
    match = _match()
    outcomes = build_outcomes(match)
    exact = _p(match, outcomes, "set2_exact_score", "6:4")
    two = _p(match, outcomes, "exact_sets", "2")
    three = _p(match, outcomes, "exact_sets", "3")
    assert exact is not None and 0.0 <= exact <= 1.0
    assert two is not None and three is not None and abs(two + three - 1.0) < 1e-9


def test_game_handicap_and_player_total_use_same_match_family_state():
    match = _match()
    outcomes = build_outcomes(match)
    h1 = _p(match, outcomes, "match_game_handicap", "Alpha", line=-2.5)
    h2 = _p(match, outcomes, "match_game_handicap", "Beta", line=2.5)
    over = _p(match, outcomes, "player_total_games", "over", player="Alpha", line=9.5)
    under = _p(match, outcomes, "player_total_games", "under", player="Alpha", line=9.5)
    assert h1 is not None and h2 is not None and abs(h1 + h2 - 1.0) < 1e-9
    assert over is not None and under is not None and abs(over + under - 1.0) < 1e-9


def test_parity_and_set_props_are_derived_without_fake_scores():
    match = _match()
    outcomes = build_outcomes(match)
    odd = _p(match, outcomes, "match_games_parity", "odd")
    even = _p(match, outcomes, "match_games_parity", "even")
    yes = _p(match, outcomes, "p1_wins_a_set", "yes")
    no = _p(match, outcomes, "p1_wins_a_set", "no")
    bagel_yes = _p(match, outcomes, "any_set_to_nil", "yes")
    bagel_no = _p(match, outcomes, "any_set_to_nil", "no")
    assert odd is not None and even is not None and abs(odd + even - 1.0) < 1e-9
    assert yes is not None and no is not None and abs(yes + no - 1.0) < 1e-9
    assert bagel_yes is not None and bagel_no is not None and abs(bagel_yes + bagel_no - 1.0) < 1e-9


def test_same_family_joint_is_exact_but_cross_family_joint_is_not_faked():
    match = _match()
    same, count = joint_probability(match, [
        {"market": "set2_total", "pick": "over", "line": 8.5},
        {"market": "set2_winner", "pick": "Alpha"},
    ])
    assert same is not None and 0 <= same <= 1 and count == 2

    mixed, supported = joint_probability(match, [
        {"market": "set2_total", "pick": "over", "line": 8.5},
        {"market": "match_game_handicap", "pick": "Alpha", "line": -2.5},
    ])
    assert mixed is None
    assert supported == 2


def test_ace_market_remains_unsupported_without_serve_prop_state():
    match = _match()
    outcomes = build_outcomes(match)
    assert _p(match, outcomes, "match_total_aces", "over", line=19.5) is None
