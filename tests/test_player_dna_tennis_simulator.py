import math

from backend.player_dna_tennis_simulator import (
    calibrated_hold_probability,
    early_equal_score_probability,
    hold_probability,
    inverse_hold_probability,
    match_outcomes,
    neutral_tiebreak_win_probability,
    score_distribution_after_games,
    set_outcomes,
    simulate_current_report,
    simulate_match,
    simulate_match_with_hold_calibration,
    trajectory_summary,
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


def test_checkpoint_score_distributions_cover_all_mass():
    for games in (2, 4, 6):
        for server in (1, 2):
            dist = score_distribution_after_games(0.63, 0.59, games, server)
            assert math.isclose(sum(dist.values()), 1.0, abs_tol=1e-12)
            assert all(sum(int(x) for x in score.split(":")) == games for score in dist)


def test_trajectory_contains_ranked_game_and_set_paths_without_claiming_certainty():
    trajectory = trajectory_summary(0.63, 0.59, best_of=3)
    assert trajectory["status"] == "SHADOW_TRAJECTORY_FOUNDATION"
    assert trajectory["validation_status"] == "UNVALIDATED_MATCH_LEVEL"
    contract = trajectory["contract"]
    assert contract["not_a_single_certain_script"] is True
    assert contract["ranked_paths_are_exact_within_known_start_server_condition"] is True
    assert contract["production_influence"] is False
    assert contract["symphony2_influence"] is False
    assert contract["superbet_playable_influence"] is False

    for checkpoint in ("after_2_games", "after_4_games", "after_6_games"):
        rows = trajectory["checkpoints_neutral_start_server"][checkpoint]
        assert rows
        assert math.isclose(sum(row["probability"] for row in rows), 1.0, abs_tol=1e-12)
        assert rows == sorted(rows, key=lambda row: row["probability"], reverse=True)

    for key in ("p1_serves_first", "p2_serves_first"):
        conditioned = trajectory["serve_order_conditioned"][key]
        first_set = conditioned["first_set_top_game_paths"]
        match_paths = conditioned["match_top_set_paths"]
        full_match_paths = conditioned["full_match_top_game_paths"]
        assert 1 <= len(first_set) <= 8
        assert 1 <= len(match_paths) <= 12
        assert 1 <= len(full_match_paths) <= 4
        assert first_set == sorted(first_set, key=lambda row: row["probability"], reverse=True)
        assert match_paths == sorted(match_paths, key=lambda row: row["probability"], reverse=True)
        assert full_match_paths == sorted(full_match_paths, key=lambda row: row["probability"], reverse=True)
        assert all(row["progression"][-1] == row["final_score"] for row in first_set)
        assert all(row["sets_played"] in (2, 3) for row in match_paths)
        assert all(row["match_score"] in {"2:0", "2:1", "0:2", "1:2"} for row in match_paths)
        for path in full_match_paths:
            assert path["sets_played"] in (2, 3)
            assert path["match_score"] in {"2:0", "2:1", "0:2", "1:2"}
            assert path["probability"] > 0.0
            assert path["total_games"] == sum(len(row["progression"]) for row in path["sets"])
            for set_row in path["sets"]:
                a, b = (int(x) for x in set_row["score"].split(":"))
                expected_games = 13 if set_row["tiebreak"] else a + b
                assert len(set_row["progression"]) == expected_games
                assert set_row["progression"][-1] == set_row["score"]
                if set_row["tiebreak"]:
                    assert set_row["progression"].count("6:6") == 1


def test_full_match_game_paths_support_bo5_without_collapsing_to_single_script():
    trajectory = trajectory_summary(0.66, 0.57, best_of=5)
    contract = trajectory["contract"]
    assert contract["full_match_game_progression_is_ranked_not_guaranteed"] is True
    assert contract["full_match_game_paths_are_exact_for_known_start_server"] is True
    for key in ("p1_serves_first", "p2_serves_first"):
        paths = trajectory["serve_order_conditioned"][key]["full_match_top_game_paths"]
        assert paths
        assert all(row["sets_played"] in (3, 4, 5) for row in paths)
        assert all(row["match_score"] in {"3:0", "3:1", "3:2", "0:3", "1:3", "2:3"} for row in paths)


def test_simulate_match_embeds_trajectory_additively():
    sim = simulate_match(0.63, 0.59, best_of=3)
    trajectory = sim["trajectory"]
    assert trajectory["status"] == "SHADOW_TRAJECTORY_FOUNDATION"
    assert sim["validation_status"] == "UNVALIDATED_MATCH_LEVEL"
    assert sim["production_influence"] is False


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


def _promising_calibration():
    return {
        "version": "player-dna-hold-calibration-audit-v1",
        "mode": "SHADOW_CALIBRATION_AUDIT_ONLY",
        "status": "CALIBRATION_EXPERIMENT_COMPLETE_NO_INTEGRATION",
        "signal": "HOLD_CALIBRATION_PROMISING_SHADOW",
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_integrate": False,
        "hold_calibrator": {
            "intercept": 0.42,
            "slope": 0.53,
            "l2": 0.01,
            "converged": True,
        },
    }


def test_hold_calibration_math_round_trip_and_candidate():
    raw_point = 0.63
    iid_hold = hold_probability(raw_point)
    calibrated = calibrated_hold_probability(iid_hold, _promising_calibration()["hold_calibrator"])
    equivalent = inverse_hold_probability(calibrated)
    assert 0.0 < calibrated < 1.0
    assert math.isclose(hold_probability(equivalent), calibrated, abs_tol=1e-9)

    candidate = simulate_match_with_hold_calibration(
        0.63,
        0.59,
        _promising_calibration()["hold_calibrator"],
        best_of=3,
    )
    assert candidate["mode"] == "SHADOW_HOLD_CALIBRATED_CANDIDATE"
    assert candidate["validation_status"] == "BACKTESTED_HOLD_CALIBRATION_CANDIDATE"
    assert candidate["production_influence"] is False
    assert candidate["auto_promote"] is False


def test_hold_calibration_candidate_is_additive_and_does_not_replace_raw():
    current = {
        "version": "player-dna-current-shadow-v1",
        "matches": [{
            "match_id": 1,
            "status": "SHADOW_SCORED",
            "p1": "A",
            "p2": "B",
            "p1_serve_point_win_probability": 0.63,
            "p2_serve_point_win_probability": 0.59,
            "model_fingerprint_sha256": "abc",
        }],
    }
    raw_only = simulate_current_report(current)
    calibrated = simulate_current_report(current, calibration_report=_promising_calibration())
    assert raw_only["matches"][0]["simulation"] == calibrated["matches"][0]["simulation"]
    assert raw_only["hold_calibration_candidate_enabled"] is False
    assert calibrated["hold_calibration_candidate_enabled"] is True
    assert calibrated["calibrated_candidate_matches"] == 1
    row = calibrated["matches"][0]
    assert row["validation_status"] == "UNVALIDATED_MATCH_LEVEL"
    assert row["hold_calibrated_candidate"]["validation_status"] == "BACKTESTED_HOLD_CALIBRATION_CANDIDATE"
    assert calibrated["market_policy"]["winner_markets"] == "NO_AUTOMATIC_SWITCH"


def test_non_promising_calibration_cannot_enable_candidate():
    report = _promising_calibration()
    report["signal"] = "HOLD_CALIBRATION_NOT_YET_PROVEN"
    current = {
        "matches": [{
            "match_id": 1,
            "status": "SHADOW_SCORED",
            "p1_serve_point_win_probability": 0.63,
            "p2_serve_point_win_probability": 0.59,
        }]
    }
    result = simulate_current_report(current, calibration_report=report)
    assert result["hold_calibration_candidate_enabled"] is False
    assert result["matches"][0]["hold_calibrated_candidate"] is None

def test_calibration_with_any_external_influence_cannot_enable_candidate():
    current = {
        "matches": [{
            "match_id": 1,
            "status": "SHADOW_SCORED",
            "p1_serve_point_win_probability": 0.63,
            "p2_serve_point_win_probability": 0.59,
        }]
    }
    for field in ("production_influence", "symphony2_influence", "superbet_playable_influence"):
        report = _promising_calibration()
        report[field] = True
        result = simulate_current_report(current, calibration_report=report)
        assert result["hold_calibration_candidate_enabled"] is False
        assert result["matches"][0]["hold_calibrated_candidate"] is None

