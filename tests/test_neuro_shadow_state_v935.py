import math
from pathlib import Path

from backend.neuro_shadow_state_v935 import (
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


def test_new_shadow_marginals_are_real_probabilities():
    for market, kwargs in (
        ("set2_winner", {"side": 1}),
        ("set3_winner", {"side": 2}),
        ("set2_total", {"line": 9.5, "pick": "over"}),
        ("set3_total", {"line": 9.5, "pick": "under"}),
        ("player_total_games", {"side": 1, "line": 12.5, "pick": "over"}),
        ("match_game_handicap", {"side": 1, "line": -1.5}),
    ):
        p = shadow_probability(_match(), market, **kwargs)
        assert p is not None
        assert 0.0 <= p <= 1.0


def test_bo5_keeps_only_needed_set_scores_but_preserves_game_totals():
    outcomes = build_shadow_outcomes(_match(best_of=5))
    assert outcomes
    assert all(o["set2"] is not None and o["set3"] is not None for o in outcomes)
    assert all("all_set_scores" not in o for o in outcomes)
    assert all(o["p1_total_games"] + o["p2_total_games"] == o["total_games"] for o in outcomes)
    assert math.isclose(sum(o["prob"] for o in outcomes), 1.0, rel_tol=0, abs_tol=1e-9)


def test_capture_readiness_closes_later_set_gaps_without_prod_promotion():
    assert {
        "set2_winner",
        "set3_winner",
        "set2_total",
        "set3_total",
        "player_total_games",
        "match_game_handicap",
    } <= CANDIDATE_CAPTURE_READY_MARKETS
    assert CANDIDATE_CAPTURE_GAP_MARKETS == frozenset()


def test_production_runtime_does_not_import_neuro_shadow_state():
    production_files = (
        ROOT / "backend" / "symphony2_engine.py",
        ROOT / "backend" / "superbet_playable_v912.py",
        ROOT / "backend" / "update.py",
    )
    for path in production_files:
        assert "neuro_shadow_state_v935" not in path.read_text(encoding="utf-8")


def test_unknown_market_never_gets_a_fabricated_probability():
    assert shadow_probability(_match(), "future_unknown", side=1, line=1.5) is None