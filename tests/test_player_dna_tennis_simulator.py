import math

from backend.player_dna_tennis_simulator import (
    early_equal_score_probability,
    hold_probability,
    match_outcomes,
    neutral_tiebreak_win_probability,
    set_outcomes,
    simulate_current_report,
    simulate_match,
)


def test_hold_probability_is_exact_at_half_and_monotonic():
    assert math.isclose(hold_probability(0.5), 0.5, abs_tol=1e-12)
    assert hold_probability(0.62) > hold_probability(0.58)


def test_neutral_tiebreak_is_symmetric_for_equal_players():
    p = neutral_tiebreak_win_probability(0.62, 0.62)
    assert math.isclose(p, 0.5, abs_tol=1e-12)


def test_set_probability_mass_is_one_for_each_start_server():
    for server in (1, 2):
        rows = set_outcomes(0.63, 0.59, server)
        assert math.isclose(sum(r["probability"] for r in rows), 1.0, abs_tol=1e-10)
        assert all(6 <= r["games"] <= 13 for r in rows)


def test_early_equal_score_is_valid_probability():
    for games in (2, 4, 6):
        p = early_equal_score_probability(0.63, 0.59, games, 1)
        assert 0.0 <= p <= 1.0


def test_symmetric_match_is_half_after_neutral_server_average():
    sim = simulate_match(0.6, 0.6, best_of=3)
    assert math.isclose(sim["match"]["p1_win"], 0.5, abs_tol=1e-10)
    assert math.isclose(sum(sim["match"]["exact_score"].values()), 1.0, abs_tol=1e-10)
    assert math.isclose(sum(sim["first_set"]["exact_score"].values()), 1.0, abs_tol=1e-10)


def test_stronger_serve_profile_moves_match_probability_up():
    strong = simulate_match(0.66, 0.57, best_of=3)
    assert strong["match"]["p1_win"] > 0.5
    assert strong["hold_probabilities"]["p1_hold"] > strong["hold_probabilities"]["p2_hold"]


def test_match_outcome_mass_is_one_for_bo5():
    for server in (1, 2):
        exact = match_outcomes(0.64, 0.61, 5, server)
        assert math.isclose(sum(exact.values()), 1.0, abs_tol=1e-9)
        assert set(exact).issubset({"3:0", "3:1", "3:2", "0:3", "1:3", "2:3"})


def test_current_report_only_simulates_shadow_scored_rows_and_stays_isolated():
    current = {
        "version": "player-dna-current-shadow-v1",
        "matches": [
            {
                "match_id": 1,
                "status": "SHADOW_SCORED",
                "p1": "A",
                "p2": "B",
                "p1_serve_point_win_probability": 0.63,
                "p2_serve_point_win_probability": 0.59,
                "model_fingerprint_sha256": "abc",
            },
            {
                "match_id": 2,
                "status": "COLLECTING_HISTORY",
            },
        ],
    }
    report = simulate_current_report(current)
    assert report["source_scored_matches"] == 1
    assert report["simulated_matches"] == 1
    assert report["production_influence"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False
    assert report["match_level_validation_required"] is True
    assert report["matches"][0]["validation_status"] == "UNVALIDATED_MATCH_LEVEL"
