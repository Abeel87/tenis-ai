import math
from pathlib import Path

from backend.neuro_shadow_state import (
    CANDIDATE_CAPTURE_GAP_MARKETS,
    CANDIDATE_CAPTURE_READY_MARKETS,
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    build_shadow_outcomes,
    set_reach_probability,
    shadow_probability,
)

ROOT = Path(__file__).resolve().parents[1]


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
    assert all(isinstance(o["set1_tiebreak"], bool) for o in outcomes)
    assert all(isinstance(o["any_set_to_nil"], bool) for o in outcomes)
    assert all("all_set_scores" not in o for o in outcomes)


def test_set3_probabilities_are_conditional_on_third_set_being_played():
    reach = set_reach_probability(_match(), 3)
    assert reach is not None
    assert 0.0 < reach < 1.0

    p1 = shadow_probability(_match(), "set3_winner", side=1)
    p2 = shadow_probability(_match(), "set3_winner", side=2)
    assert p1 is not None and p2 is not None
    assert math.isclose(p1 + p2, 1.0, rel_tol=0, abs_tol=1e-9)

    over = shadow_probability(_match(), "set3_total", line=9.5, pick="over")
    under = shadow_probability(_match(), "set3_total", line=9.5, pick="under")
    assert over is not None and under is not None
    assert math.isclose(over + under, 1.0, rel_tol=0, abs_tol=1e-9)


def test_set2_exact_score_is_conditional_on_set_being_played():
    outcomes = build_shadow_outcomes(_match())
    score_mass = {}
    for row in outcomes:
        score = row["set2"]
        key = f"{score[0]}:{score[1]}"
        score_mass[key] = score_mass.get(key, 0.0) + row["prob"]
    assert score_mass
    total = sum(shadow_probability(_match(), "set2_exact_score", pick=score) or 0.0 for score in score_mass)
    assert math.isclose(total, 1.0, rel_tol=0, abs_tol=1e-8)


def test_integer_total_lines_condition_on_non_void_outcomes():
    for market, line in (("set2_total", 9.0), ("set3_total", 9.0)):
        over = shadow_probability(_match(), market, line=line, pick="over")
        under = shadow_probability(_match(), market, line=line, pick="under")
        assert over is not None and under is not None
        assert math.isclose(over + under, 1.0, rel_tol=0, abs_tol=1e-9)

    for side in (1, 2):
        over = shadow_probability(_match(), "player_total_games", side=side, line=12.0, pick="over")
        under = shadow_probability(_match(), "player_total_games", side=side, line=12.0, pick="under")
        assert over is not None and under is not None
        assert math.isclose(over + under, 1.0, rel_tol=0, abs_tol=1e-9)


def test_integer_handicap_push_mass_is_removed_from_calibration_probability():
    p1 = shadow_probability(_match(), "match_game_handicap", side=1, line=0.0)
    p2 = shadow_probability(_match(), "match_game_handicap", side=2, line=0.0)
    assert p1 is not None and p2 is not None
    assert math.isclose(p1 + p2, 1.0, rel_tol=0, abs_tol=1e-9)


def test_set_outcome_yes_no_probabilities_are_complements():
    for market in (
        "set1_tiebreak",
        "p1_exactly_1_set",
        "p1_exactly_2_sets",
        "p2_exactly_1_set",
        "p2_exactly_2_sets",
        "p1_wins_a_set",
        "p2_wins_a_set",
    ):
        yes = shadow_probability(_match(), market, pick="yes")
        no = shadow_probability(_match(), market, pick="no")
        assert yes is not None and no is not None
        assert math.isclose(yes + no, 1.0, rel_tol=0, abs_tol=1e-9)


def test_any_set_to_nil_is_exact_complement_for_bo3_and_bo5():
    for best_of in (3, 5):
        yes = shadow_probability(_match(best_of), "any_set_to_nil", pick="yes")
        no = shadow_probability(_match(best_of), "any_set_to_nil", pick="no")
        assert yes is not None and no is not None
        assert 0.0 <= yes <= 1.0
        assert 0.0 <= no <= 1.0
        assert math.isclose(yes + no, 1.0, rel_tol=0, abs_tol=1e-9)


def test_exact_sets_distribution_sums_to_one():
    best3 = sum(shadow_probability(_match(), "exact_sets", pick=str(n)) or 0.0 for n in (2, 3))
    assert math.isclose(best3, 1.0, rel_tol=0, abs_tol=1e-9)

    best5 = sum(shadow_probability(_match(5), "exact_sets", pick=str(n)) or 0.0 for n in (3, 4, 5))
    assert math.isclose(best5, 1.0, rel_tol=0, abs_tol=1e-9)


def test_new_shadow_marginals_are_real_probabilities():
    for market, kwargs in (
        ("set2_winner", {"side": 1}),
        ("set3_winner", {"side": 2}),
        ("set2_exact_score", {"pick": "6:4"}),
        ("set2_total", {"line": 9.5, "pick": "over"}),
        ("set3_total", {"line": 9.5, "pick": "under"}),
        ("player_total_games", {"side": 1, "line": 12.5, "pick": "over"}),
        ("match_game_handicap", {"side": 1, "line": -1.5}),
        ("exact_sets", {"pick": "2"}),
        ("p1_wins_a_set", {"pick": "yes"}),
        ("set1_tiebreak", {"pick": "no"}),
    ):
        p = shadow_probability(_match(), market, **kwargs)
        assert p is not None
        assert 0.0 <= p <= 1.0


def test_bo5_keeps_bounded_state_but_preserves_nil_and_game_totals():
    outcomes = build_shadow_outcomes(_match(best_of=5))
    assert outcomes
    assert all(o["set2"] is not None and o["set3"] is not None for o in outcomes)
    assert all("all_set_scores" not in o for o in outcomes)
    assert all(isinstance(o["any_set_to_nil"], bool) for o in outcomes)
    assert all(o["p1_total_games"] + o["p2_total_games"] == o["total_games"] for o in outcomes)
    assert math.isclose(sum(o["prob"] for o in outcomes), 1.0, rel_tol=0, abs_tol=1e-9)


def test_capture_readiness_includes_existing_state_markets_without_prod_promotion():
    assert {
        "set1_tiebreak",
        "set2_winner",
        "set3_winner",
        "set2_exact_score",
        "set2_total",
        "set3_total",
        "player_total_games",
        "match_game_handicap",
        "exact_sets",
        "p1_exactly_1_set",
        "p1_exactly_2_sets",
        "p2_exactly_1_set",
        "p2_exactly_2_sets",
        "p1_wins_a_set",
        "p2_wins_a_set",
        "any_set_to_nil",
    } <= CANDIDATE_CAPTURE_READY_MARKETS
    assert CANDIDATE_CAPTURE_GAP_MARKETS == frozenset()


def test_production_runtime_does_not_import_neuro_shadow_state():
    production_files = (
        ROOT / "backend" / "symphony2_engine.py",
        ROOT / "backend" / "superbet_playable.py",
        ROOT / "backend" / "update.py",
    )
    for path in production_files:
        assert "neuro_shadow_state" not in path.read_text(encoding="utf-8")


def test_unknown_or_invalid_market_never_gets_fabricated_probability():
    assert shadow_probability(_match(), "future_unknown", side=1, line=1.5) is None
    assert shadow_probability(_match(), "exact_sets", pick="banana") is None
    assert shadow_probability(_match(), "p1_wins_a_set", pick="maybe") is None
