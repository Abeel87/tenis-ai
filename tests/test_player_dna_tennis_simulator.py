import copy
import gzip
import json
import math

import pytest
from backend import player_dna_tennis_simulator as simulator

from backend.player_dna_tennis_simulator import (
    calibrated_hold_probability,
    compare_exact_dp_to_monte_carlo,
    dynamic_hold_probability,
    dynamic_match_outcomes,
    dynamic_match_outcomes_from_sets,
    dynamic_score_distribution_after_games,
    dynamic_set_outcomes,
    evaluate_phase6_gate,
    early_equal_score_probability,
    hold_probability,
    inverse_hold_probability,
    match_outcomes,
    monte_carlo_match_distribution,
    neutral_tiebreak_win_probability,
    score_distribution_after_games,
    set_outcomes,
    shared_match_state_outcomes,
    set_shape_family,
    simulate_current_report,
    simulate_match,
    simulate_match_with_hold_calibration,
    trajectory_simulator_contract,
    trajectory_simulator_contract_fingerprint,
    trajectory_summary,
)

HOLD_CALIBRATION_TEST_CONTRACT_ID = "test-hold-calibration-strict-atomic"
HOLD_CALIBRATION_TEST_CONTRACT_FP = "d" * 64


def test_hold_probability_is_exact_at_half_and_monotonic():
    assert math.isclose(hold_probability(0.5), 0.5, abs_tol=1e-12)
    assert hold_probability(0.62) > hold_probability(0.58)


@pytest.mark.parametrize("best_of", [3, 5])
def test_publication_preserves_full_research_and_all_consumed_fields(tmp_path, monkeypatch, best_of):
    simulation = simulate_match(0.63, 0.59, best_of)
    report = {"matches": [{"simulation": simulation, "hold_calibrated_candidate": copy.deepcopy(simulation)},
                          {"simulation": simulation, "hold_calibrated_candidate": None}]}
    original = copy.deepcopy(report)
    monkeypatch.setattr(simulator, "FULL_REPORT", tmp_path / "full.json.gz")
    monkeypatch.setattr(simulator, "OUT", tmp_path / "published.json")
    simulator._write_reports(report)
    assert report == original
    with gzip.open(simulator.FULL_REPORT, "rt", encoding="utf-8") as handle:
        assert json.load(handle) == original
    published = json.loads(simulator.OUT.read_text(encoding="utf-8"))
    assert published.pop("publication")["probabilities_modified"] is False
    for before, after in zip(original["matches"], published["matches"]):
        for name in ("simulation", "hold_calibrated_candidate"):
            if before[name] is None:
                assert after[name] is None
                continue
            for server, branch in before[name]["trajectory"]["serve_order_conditioned"].items():
                public_branch = after[name]["trajectory"]["serve_order_conditioned"][server]
                assert "set_shape_trajectories" not in public_branch
                public_branch["set_shape_trajectories"] = branch["set_shape_trajectories"]
    assert published == original
    assert simulator.OUT.stat().st_size < len(json.dumps(original).encode("utf-8")) / 2


def test_neutral_tiebreak_is_symmetric_for_equal_players():
    p = neutral_tiebreak_win_probability(0.62, 0.62)
    assert math.isclose(p, 0.5, abs_tol=1e-12)


def test_dynamic_hold_callback_sees_pre_point_pressure_states_only():
    seen = []

    def callback(state):
        seen.append(dict(state))
        return 0.62

    probability = dynamic_hold_probability(
        callback,
        server=2,
        sets=(1, 1),
        games=(4, 5),
        best_of=3,
    )
    assert 0.0 < probability < 1.0
    assert math.isclose(probability, hold_probability(0.62), abs_tol=1e-12)
    assert any(
        row["server_points"] == "40" and row["receiver_points"] == "40"
        for row in seen
    )
    assert any(
        row["server_points"] == "A" and row["receiver_points"] == "40"
        for row in seen
    )
    assert any(
        row["server_points"] == "40" and row["receiver_points"] == "A"
        for row in seen
    )
    assert all(row["server"] == 2 and row["receiver"] == 1 for row in seen)
    assert all(row["sets"] == [1, 1] and row["games"] == [4, 5] for row in seen)
    assert all(row["is_tiebreak"] is False for row in seen)


@pytest.mark.parametrize("games", [2, 4, 6])
@pytest.mark.parametrize("start_server", [1, 2])
def test_dynamic_checkpoints_reduce_exactly_to_legacy_iid(games, start_server):
    p1_serve = 0.63
    p2_serve = 0.59

    def point_callback(state):
        return p1_serve if state["server"] == 1 else p2_serve

    dynamic = dynamic_score_distribution_after_games(
        point_callback,
        games=games,
        start_server=start_server,
        sets_before=(0, 0),
        best_of=3,
    )
    legacy = score_distribution_after_games(
        p1_serve,
        p2_serve,
        games,
        start_server,
    )
    assert set(dynamic) == set(legacy)
    for score in legacy:
        assert math.isclose(dynamic[score], legacy[score], abs_tol=1e-12)


@pytest.mark.parametrize("best_of", [3, 5])
@pytest.mark.parametrize("start_server", [1, 2])
def test_dynamic_match_dp_reduces_exactly_to_legacy_iid(best_of, start_server):
    p1_serve = 0.63
    p2_serve = 0.59
    p1_tiebreak = neutral_tiebreak_win_probability(p1_serve, p2_serve)

    def point_callback(state):
        return p1_serve if state["server"] == 1 else p2_serve

    def tiebreak_callback(_state):
        return p1_tiebreak

    dynamic = dynamic_match_outcomes(
        point_callback,
        tiebreak_callback,
        best_of=best_of,
        start_server=start_server,
    )
    legacy = match_outcomes(p1_serve, p2_serve, best_of, start_server)

    assert set(dynamic) == set(legacy)
    assert math.isclose(sum(dynamic.values()), 1.0, abs_tol=1e-9)
    for score in legacy:
        assert math.isclose(dynamic[score], legacy[score], abs_tol=1e-12)


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



def test_set_shape_family_taxonomy_is_coarse_and_complete_for_legal_set_scores():
    assert set_shape_family("6:0") == "DOMINANT"
    assert set_shape_family("2:6") == "DOMINANT"
    assert set_shape_family("6:3") == "NORMAL"
    assert set_shape_family("4:6") == "CLOSE"
    assert set_shape_family("7:5") == "EXTENDED_7_5"
    assert set_shape_family("6:7") == "TIEBREAK"
    assert set_shape_family("5:5") is None


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
        storylines = conditioned["match_storylines"]
        first_set_shapes = conditioned["first_set_shape_families"]
        set_shape_trajectories = conditioned["set_shape_trajectories"]
        set_index_shape_marginals = conditioned["set_index_shape_marginals"]
        set_winner_trajectories = conditioned["set_winner_trajectories"]
        full_match_paths = conditioned["full_match_top_game_paths"]
        assert 1 <= len(first_set) <= 8
        assert 1 <= len(match_paths) <= 12
        assert len(storylines) == 4
        assert len(first_set_shapes) == 5
        assert set(row["shape"] for row in first_set_shapes) == {"DOMINANT", "NORMAL", "CLOSE", "EXTENDED_7_5", "TIEBREAK"}
        assert math.isclose(sum(row["probability"] for row in first_set_shapes), 1.0, abs_tol=1e-9)
        assert set_shape_trajectories
        assert math.isclose(sum(row["probability"] for row in set_shape_trajectories), 1.0, abs_tol=1e-9)
        by_shape_score = {}
        for row in set_shape_trajectories:
            by_shape_score.setdefault(row["match_score"], []).append(row)
        for rows in by_shape_score.values():
            assert math.isclose(sum(row["conditional_probability_within_match_score"] for row in rows), 1.0, abs_tol=1e-9)
        assert set(set_index_shape_marginals) == {"2:0", "2:1", "0:2", "1:2"}
        for match_score, per_set in set_index_shape_marginals.items():
            expected_sets = sum(int(x) for x in match_score.split(":"))
            assert set(per_set) == {f"set_{i}" for i in range(1, expected_sets + 1)}
            for rows in per_set.values():
                assert rows == sorted(rows, key=lambda row: row["probability"], reverse=True)
                assert math.isclose(sum(row["probability"] for row in rows), 1.0, abs_tol=1e-9)
                assert all(row["probability_scope"] == "SET_INDEX_SHAPE_WITHIN_MATCH_SCORE" for row in rows)
        assert len(set_winner_trajectories) == 6
        assert 1 <= len(full_match_paths) <= 4
        assert first_set == sorted(first_set, key=lambda row: row["probability"], reverse=True)
        assert match_paths == sorted(match_paths, key=lambda row: row["probability"], reverse=True)
        assert storylines == sorted(storylines, key=lambda row: row["probability"], reverse=True)
        assert math.isclose(sum(row["probability"] for row in storylines), 1.0, abs_tol=1e-9)
        assert set_winner_trajectories == sorted(set_winner_trajectories, key=lambda row: row["probability"], reverse=True)
        assert math.isclose(sum(row["probability"] for row in set_winner_trajectories), 1.0, abs_tol=1e-9)
        assert full_match_paths == sorted(full_match_paths, key=lambda row: row["probability"], reverse=True)
        assert all(row["progression"][-1] == row["final_score"] for row in first_set)
        assert all(row["probability_scope"] == "MATCH_SCORE_FAMILY" for row in storylines)
        assert all(row["representative_only"] is True for row in storylines)
        assert all(row["probability_scope"] == "SET_WINNER_SEQUENCE" for row in set_winner_trajectories)
        assert all(row["representative_only"] is True for row in set_winner_trajectories)
        by_match_score = {}
        for row in set_winner_trajectories:
            by_match_score.setdefault(row["match_score"], []).append(row)
        for rows in by_match_score.values():
            assert math.isclose(
                sum(row["conditional_probability_within_match_score"] for row in rows),
                1.0,
                abs_tol=1e-9,
            )
        for trajectory_row in set_winner_trajectories:
            p1_sets = trajectory_row["set_winners"].count(1)
            p2_sets = trajectory_row["set_winners"].count(2)
            assert trajectory_row["match_score"] == f"{p1_sets}:{p2_sets}"
            assert trajectory_row["set_scores"] == [row["score"] for row in trajectory_row["sets"]]
            assert trajectory_row["representative_set_score_sequence_probability"] <= trajectory_row["probability"] + 1e-12
            assert trajectory_row["representative_exact_game_path_probability"] <= trajectory_row["representative_set_score_sequence_probability"] + 1e-12
            assert all(row["progression"][-1] == row["score"] for row in trajectory_row["sets"])
        for storyline in storylines:
            assert storyline["sets"]
            assert storyline["set_scores"] == [row["score"] for row in storyline["sets"]]
            assert storyline["total_games"] == sum(row["games"] for row in storyline["sets"])
            assert storyline["representative_set_sequence_probability"] <= storyline["probability"] + 1e-12
            assert storyline["representative_exact_game_path_probability"] <= storyline["representative_set_sequence_probability"] + 1e-12
            for set_row in storyline["sets"]:
                assert set_row["representative_only"] is True
                assert set_row["progression"][-1] == set_row["score"]
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
    assert contract["primary_storyline_probability_scope"] == "MATCH_SCORE_FAMILY"
    assert contract["storyline_game_progressions_are_representative"] is True
    assert contract["set_shape_taxonomy"] == ["DOMINANT", "NORMAL", "CLOSE", "EXTENDED_7_5", "TIEBREAK"]
    assert contract["set_shape_probability_scope"] == "MATCH_SCORE_SET_SHAPE_SEQUENCE"
    assert contract["set_shape_conditional_scope"] == "WITHIN_MATCH_SCORE_FAMILY"
    assert contract["set_index_shape_probability_scope"] == "SET_INDEX_SHAPE_WITHIN_MATCH_SCORE"
    assert contract["set_winner_trajectory_probability_scope"] == "SET_WINNER_SEQUENCE"
    assert contract["set_winner_trajectory_conditional_scope"] == "WITHIN_MATCH_SCORE_FAMILY"
    assert contract["set_winner_trajectory_game_progressions_are_representative"] is True
    assert contract["exact_full_match_game_paths_are_diagnostic_only"] is True
    for key in ("p1_serves_first", "p2_serves_first"):
        branch = trajectory["serve_order_conditioned"][key]
        storylines = branch["match_storylines"]
        set_winner_trajectories = branch["set_winner_trajectories"]
        assert len(storylines) == 6
        assert math.isclose(sum(row["probability"] for row in storylines), 1.0, abs_tol=1e-9)
        assert len(set_winner_trajectories) == 20
        assert math.isclose(sum(row["probability"] for row in set_winner_trajectories), 1.0, abs_tol=1e-9)
        paths = branch["full_match_top_game_paths"]
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
        "hold_calibration_contract_id": HOLD_CALIBRATION_TEST_CONTRACT_ID,
        "hold_calibration_contract_fingerprint_sha256": HOLD_CALIBRATION_TEST_CONTRACT_FP,
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
    assert (
        row["hold_calibrated_candidate"]["hold_calibration_contract_id"]
        == HOLD_CALIBRATION_TEST_CONTRACT_ID
    )
    assert (
        row["hold_calibrated_candidate"]["hold_calibration_contract_fingerprint_sha256"]
        == HOLD_CALIBRATION_TEST_CONTRACT_FP
    )
    source = calibrated["hold_calibration_source"]
    assert source["hold_calibration_contract_id"] == HOLD_CALIBRATION_TEST_CONTRACT_ID
    assert (
        source["hold_calibration_contract_fingerprint_sha256"]
        == HOLD_CALIBRATION_TEST_CONTRACT_FP
    )
    assert source["semantic_contract_required_for_candidate"] is True
    assert calibrated["market_policy"]["winner_markets"] == "NO_AUTOMATIC_SWITCH"


def test_promising_calibration_without_semantic_provenance_cannot_enable_candidate():
    report = _promising_calibration()
    report.pop("hold_calibration_contract_id")
    report.pop("hold_calibration_contract_fingerprint_sha256")
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




def test_trajectory_semantic_contract_is_stable_and_captures_path_policy():
    contract = trajectory_simulator_contract()
    fingerprint = trajectory_simulator_contract_fingerprint()

    assert contract["contract_id"] == "player-dna-trajectory-dp-v1"
    assert contract["engine"] == "EXACT_TENNIS_DP_FROM_SERVE_POINT_PROBABILITIES"
    assert contract["serve_order_pre_match"] == "NEUTRAL_50_50"
    assert contract["checkpoint_games"] == [2, 4, 6]
    assert contract["first_set_top_game_paths_limit"] == 8
    assert contract["match_top_set_paths_limit"] == 12
    assert contract["full_match_top_game_paths_limit"] == 4
    assert contract["exact_full_match_game_paths_are_diagnostic_only"] is True
    assert isinstance(fingerprint, str)
    assert len(fingerprint) == 64
    assert fingerprint == trajectory_simulator_contract_fingerprint()


def test_trajectory_summary_publishes_same_semantic_contract_identity():
    trajectory = trajectory_summary(0.63, 0.59, 3)

    assert trajectory["semantic_contract_id"] == "player-dna-trajectory-dp-v1"
    assert (
        trajectory["semantic_contract_fingerprint_sha256"]
        == trajectory_simulator_contract_fingerprint()
    )
    assert trajectory["contract"]["contract_id"] == trajectory["semantic_contract_id"]



def _neutral_match_win_probability(p1_serve_point, p2_serve_point, best_of=3):
    needed = best_of // 2 + 1
    probability = 0.0
    for start_server in (1, 2):
        exact = match_outcomes(
            p1_serve_point,
            p2_serve_point,
            best_of,
            start_server,
        )
        probability += 0.5 * sum(
            mass
            for score, mass in exact.items()
            if int(score.split(":")[0]) == needed
        )
    return probability


def _neutral_first_set_shape_metrics(p1_serve_point, p2_serve_point):
    tiebreak = 0.0
    over_10_5 = 0.0
    for start_server in (1, 2):
        for row in set_outcomes(
            p1_serve_point,
            p2_serve_point,
            start_server,
        ):
            mass = 0.5 * float(row["probability"])
            if row["tiebreak"]:
                tiebreak += mass
            if int(row["games"]) > 10.5:
                over_10_5 += mass
    return tiebreak, over_10_5


def test_master_plan_similar_strong_servers_raise_tiebreak_and_long_set_shape():
    low_tiebreak, low_long = _neutral_first_set_shape_metrics(0.58, 0.58)
    high_tiebreak, high_long = _neutral_first_set_shape_metrics(0.68, 0.68)

    assert high_tiebreak > low_tiebreak
    assert high_long > low_long

    low_three_all = 0.5 * (
        early_equal_score_probability(0.58, 0.58, 6, 1)
        + early_equal_score_probability(0.58, 0.58, 6, 2)
    )
    high_three_all = 0.5 * (
        early_equal_score_probability(0.68, 0.68, 6, 1)
        + early_equal_score_probability(0.68, 0.68, 6, 2)
    )
    assert high_three_all > low_three_all


def test_match_win_probability_moves_monotonically_with_p1_serve_strength():
    weak = _neutral_match_win_probability(0.60, 0.57)
    medium = _neutral_match_win_probability(0.63, 0.57)
    strong = _neutral_match_win_probability(0.66, 0.57)

    assert 0.0 < weak < medium < strong < 1.0



def _p1_match_win_from_exact_scores(exact, needed):
    return sum(
        probability
        for score, probability in exact.items()
        if int(score.split(":")[0]) == needed
    )


def test_master_plan_favorite_can_have_high_first_set_win_but_weak_comeback_profile():
    def point_callback(state):
        sets = tuple(state["sets"])
        if sets == (0, 0):
            return 0.70 if state["server"] == 1 else 0.56
        if sets[0] < sets[1]:
            return 0.50 if state["server"] == 1 else 0.68
        return 0.62 if state["server"] == 1 else 0.60

    def tiebreak_callback(state):
        sets = tuple(state["sets"])
        if sets == (0, 0):
            return 0.80
        if sets[0] < sets[1]:
            return 0.20
        return 0.55

    first_set_rows = []
    for start_server in (1, 2):
        for row in dynamic_set_outcomes(
            point_callback,
            tiebreak_callback,
            start_server=start_server,
            sets_before=(0, 0),
            best_of=3,
        ):
            first_set_rows.append((0.5 * float(row["probability"]), row))

    p1_first_set_win = sum(
        mass for mass, row in first_set_rows if int(row["winner"]) == 1
    )
    p1_first_set_loss = 1.0 - p1_first_set_win
    assert p1_first_set_win > 0.5
    assert p1_first_set_loss > 0.0

    comeback = 0.0
    for mass, row in first_set_rows:
        if int(row["winner"]) != 2:
            continue
        continuation = dynamic_match_outcomes_from_sets(
            point_callback,
            tiebreak_callback,
            best_of=3,
            start_server=int(row["next_set_server"]),
            sets_before=(0, 1),
        )
        conditional_weight = mass / p1_first_set_loss
        comeback += conditional_weight * _p1_match_win_from_exact_scores(
            continuation,
            needed=2,
        )

    assert comeback < 0.5
    assert p1_first_set_win > comeback


def test_master_plan_bo5_stamina_advantage_changes_late_match_distribution():
    def baseline_point(state):
        return 0.62

    def baseline_tiebreak(_state):
        return 0.5

    def stamina_point(state):
        sets_completed = sum(state["sets"])
        if sets_completed < 2:
            return 0.62
        return 0.68 if state["server"] == 1 else 0.56

    def stamina_tiebreak(state):
        return 0.5 if sum(state["sets"]) < 2 else 0.75

    baseline_p1 = 0.0
    stamina_p1 = 0.0
    for start_server in (1, 2):
        baseline = dynamic_match_outcomes(
            baseline_point,
            baseline_tiebreak,
            best_of=5,
            start_server=start_server,
        )
        stamina = dynamic_match_outcomes(
            stamina_point,
            stamina_tiebreak,
            best_of=5,
            start_server=start_server,
        )
        baseline_p1 += 0.5 * _p1_match_win_from_exact_scores(
            baseline,
            needed=3,
        )
        stamina_p1 += 0.5 * _p1_match_win_from_exact_scores(
            stamina,
            needed=3,
        )

    assert math.isclose(baseline_p1, 0.5, abs_tol=1e-9)
    assert stamina_p1 > baseline_p1


def test_dynamic_match_continuation_rejects_illegal_set_scores_and_preserves_terminal_mass():
    def point_callback(_state):
        return 0.62

    def tiebreak_callback(_state):
        return 0.5

    assert dynamic_match_outcomes_from_sets(
        point_callback,
        tiebreak_callback,
        best_of=3,
        start_server=1,
        sets_before=(2, 0),
    ) == {"2:0": 1.0}

    with pytest.raises(ValueError):
        dynamic_match_outcomes_from_sets(
            point_callback,
            tiebreak_callback,
            best_of=3,
            start_server=1,
            sets_before=(2, 2),
        )



def test_phase6_monte_carlo_is_seed_deterministic_and_probability_conserving():
    first = monte_carlo_match_distribution(
        0.63,
        0.59,
        best_of=3,
        simulations=2_000,
        seed=606,
    )
    second = monte_carlo_match_distribution(
        0.63,
        0.59,
        best_of=3,
        simulations=2_000,
        seed=606,
    )

    assert first == second
    assert first["mode"] == "SHADOW_MONTE_CARLO_CROSSCHECK_ONLY"
    assert first["production_influence"] is False
    assert first["symphony2_influence"] is False
    assert first["superbet_playable_influence"] is False
    assert first["auto_promote"] is False
    assert math.isclose(
        sum(first["first_set"]["exact_score"].values()),
        1.0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        sum(first["match"]["exact_score"].values()),
        1.0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        sum(first["match"]["total_sets"].values()),
        1.0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        sum(first["match"]["total_games"].values()),
        1.0,
        abs_tol=1e-12,
    )


@pytest.mark.parametrize(
    ("p1s", "p2s", "best_of", "seed"),
    [
        (0.62, 0.62, 3, 260907),
        (0.66, 0.59, 3, 260908),
        (0.59, 0.66, 3, 260909),
        (0.64, 0.61, 5, 260910),
    ],
)
def test_phase6_exact_dp_and_10k_monte_carlo_agree_on_fixed_probabilities(
    p1s,
    p2s,
    best_of,
    seed,
):
    comparison = compare_exact_dp_to_monte_carlo(
        p1s,
        p2s,
        best_of=best_of,
        simulations=10_000,
        seed=seed,
        tolerance_abs=0.03,
    )

    assert comparison["passed"] is True
    assert comparison["max_abs_error"] <= 0.03
    assert all(comparison["probability_mass_checks"].values())


def test_phase6_gate_closes_after_phase5_without_runtime_promotion():
    report = evaluate_phase6_gate({
        "phase5_complete": True,
        "phase6_ready": True,
    })

    assert report["mode"] == "SHADOW_PHASE6_EXACT_DP_MONTE_CARLO"
    assert report["phase6_complete"] is True
    assert report["phase7_ready"] is True
    assert report["deterministic_seed_replay"] is True
    assert report["test_simulations_per_scenario"] == 10_000
    assert report["shadow_simulations_target"] == 50_000
    assert report["target_simulations_when_cost_allows"] == 100_000
    assert report["production_influence"] is False
    assert report["runtime_switch_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False
    assert len(report["comparisons"]) == 4
    assert all(row["passed"] is True for row in report["comparisons"])
    contract = report["contract"]
    assert contract["canonical_simulator_module_reused"] is True
    assert contract["exact_dp_preferred_for_static_probabilities"] is True
    assert contract["monte_carlo_is_crosscheck_not_replacement"] is True
    assert contract["same_phase5_legality_predicates"] is True
    assert contract["fixed_probability_dp_mc_agreement_required"] is True
    assert contract["phase6_completion_does_not_promote_runtime_or_prod"] is True


@pytest.mark.parametrize("best_of", [3, 5])
def test_phase9_shared_match_state_is_normalized_and_legal(best_of):
    rows = shared_match_state_outcomes(0.63, 0.59, best_of=best_of)

    assert rows
    assert math.isclose(
        sum(float(row["prob"]) for row in rows),
        1.0,
        abs_tol=1e-9,
    )
    needed = best_of // 2 + 1
    for row in rows:
        s1, s2 = row["sets"]
        assert (s1 == needed) ^ (s2 == needed)
        assert row["winner"] == (1 if s1 > s2 else 2)
        assert row["set_count"] == s1 + s2
        assert row["total_games"] == row["p1_games"] + row["p2_games"]
        assert isinstance(row["set1"], tuple)
        assert isinstance(row["set2"], tuple)
        assert sum(row["set1"]) >= 6
        assert sum(row["set2"]) >= 6


def test_phase9_neutral_start_server_is_exact_half_mixture():
    neutral = shared_match_state_outcomes(0.63, 0.59, best_of=3)
    p1_first = shared_match_state_outcomes(
        0.63, 0.59, best_of=3, start_server=1
    )
    p2_first = shared_match_state_outcomes(
        0.63, 0.59, best_of=3, start_server=2
    )

    def aggregate(rows):
        out = {}
        for row in rows:
            key = (
                row["sets"],
                row["set1"],
                row["set2"],
                row["p1_games"],
                row["p2_games"],
                row["any_set_to_nil"],
            )
            out[key] = out.get(key, 0.0) + float(row["prob"])
        return out

    n = aggregate(neutral)
    a = aggregate(p1_first)
    b = aggregate(p2_first)
    assert set(n) == set(a) | set(b)
    for key in n:
        expected = 0.5 * a.get(key, 0.0) + 0.5 * b.get(key, 0.0)
        assert math.isclose(n[key], expected, abs_tol=1e-12)
