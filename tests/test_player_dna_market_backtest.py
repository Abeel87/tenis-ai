from backend.player_dna_market_backtest import (
    _trajectory_validation,
    binary_metrics,
    reconstruct_match_label,
)


def _row(idx, sets, games, server=None):
    return {
        "event_index": idx,
        "match_format": "BO3",
        "server": server,
        "score_after": {
            "sets": list(sets),
            "games": [list(games[0]), list(games[1])],
            "points": ["0", "0"],
        },
    }


def test_reconstruct_complete_bo3_and_early_equal_states():
    rows = [
        _row(0, (0, 0), ([0], [1])),
        _row(1, (0, 0), ([1], [1])),
        _row(2, (0, 0), ([2], [1])),
        _row(3, (0, 0), ([2], [2])),
        _row(4, (0, 0), ([3], [2])),
        _row(5, (0, 0), ([3], [3])),
        _row(6, (1, 0), ([7], [6])),
        _row(7, (1, 0), ([7, 4], [6, 6])),
        _row(8, (2, 1), ([7, 4, 6], [6, 6, 3])),
    ]
    label = reconstruct_match_label(rows)
    assert label is not None
    assert label["match_p1_win"] is True
    assert label["match_exact_score"] == "2:1"
    assert label["total_sets"] == "3"
    assert label["first_set_exact_score"] == "7:6"
    assert label["first_set_tiebreak"] is True
    assert label["first_set_over_12.5"] is True
    assert label["early_1:1"] is True
    assert label["early_2:2"] is True
    assert label["early_3:3"] is True


def test_incomplete_match_is_not_labeled_as_settled():
    rows = [
        _row(0, (0, 0), ([3], [2])),
        _row(1, (1, 0), ([6], [4])),
        _row(2, (1, 0), ([6, 2], [4, 1])),
    ]
    assert reconstruct_match_label(rows) is None


def test_binary_metrics_rewards_calibrated_predictions_over_train_rate():
    records = [
        (0.90, 1),
        (0.85, 1),
        (0.15, 0),
        (0.10, 0),
        (0.70, 1),
        (0.30, 0),
    ]
    metrics = binary_metrics(records, [0, 1, 0, 1, 0, 1])
    assert metrics["n"] == 6
    assert metrics["brier_gain_vs_train_rate"] > 0
    assert metrics["log_loss_gain_vs_train_rate"] > 0
    assert 0 <= metrics["ece_10_bin"] <= 1


def test_reconstruct_complete_game_progression_for_trajectory_validation():
    rows = []
    idx = 0
    first_set = [(1, 0), (1, 1), (2, 1), (2, 2), (3, 2), (3, 3), (4, 3), (4, 4), (5, 4), (6, 4)]
    for a, b in first_set:
        rows.append(_row(idx, (0, 0) if (a, b) != (6, 4) else (1, 0), ([a], [b]), server=1))
        idx += 1
    second_set = [(1, 0), (2, 0), (2, 1), (3, 1), (4, 1), (4, 2), (5, 2), (5, 3), (6, 3)]
    for a, b in second_set:
        rows.append(_row(idx, (1, 0) if (a, b) != (6, 3) else (2, 0), ([6, a], [4, b]), server=2))
        idx += 1

    label = reconstruct_match_label(rows)
    actual = label["trajectory_actual"]
    assert actual["first_server"] == 1
    assert actual["first_set_progression"] == [f"{a}:{b}" for a, b in first_set]
    assert actual["checkpoint_scores"] == {"2": "1:1", "4": "2:2", "6": "3:3"}
    assert actual["set_score_sequence"] == ["6:4", "6:3"]
    assert actual["full_match_progression_complete"] is True
    assert actual["set_progression_complete"] == [True, True]


def test_trajectory_validation_reports_rank_hits_without_promotion_claim():
    actual_first = ["1:0", "1:1", "2:1", "2:2", "3:2", "3:3", "4:3", "4:4", "5:4", "6:4"]
    actual_second = ["1:0", "2:0", "2:1", "3:1", "4:1", "4:2", "5:2", "5:3", "6:3"]
    labels = {
        "1": {
            "match_exact_score": "2:0",
            "trajectory_actual": {
                "first_server": 1,
                "checkpoint_scores": {"2": "1:1", "4": "2:2", "6": "3:3"},
                "first_set_progression": actual_first,
                "set_progressions": [actual_first, actual_second],
                "set_score_sequence": ["6:4", "6:3"],
                "full_match_progression_complete": True,
            }
        }
    }
    predictions = {
        "1": {
            "simulation": {
                "trajectory": {
                    "checkpoints_neutral_start_server": {
                        "after_2_games": [{"score": "1:1"}, {"score": "2:0"}, {"score": "0:2"}],
                        "after_4_games": [{"score": "3:1"}, {"score": "2:2"}, {"score": "1:3"}],
                        "after_6_games": [{"score": "4:2"}, {"score": "3:3"}, {"score": "2:4"}],
                    },
                    "serve_order_conditioned": {
                        "p1_serves_first": {
                            "first_set_top_game_paths": [
                                {"progression": ["1:0", "2:0", "3:0", "4:0", "5:0", "6:0"]},
                                {"progression": actual_first},
                            ],
                            "match_top_set_paths": [
                                {"set_scores": ["6:4", "6:3"]},
                                {"set_scores": ["6:4", "4:6", "6:3"]},
                            ],
                            "match_storylines": [
                                {"match_score": "2:1"},
                                {"match_score": "2:0"},
                                {"match_score": "0:2"},
                            ],
                            "set_winner_trajectories": [
                                {"set_winners": [1, 2, 1]},
                                {"set_winners": [1, 1]},
                                {"set_winners": [2, 1, 1]},
                            ],
                            "full_match_top_game_paths": [
                                {
                                    "sets": [
                                        {"progression": ["1:0", "2:0", "3:0", "4:0", "5:0", "6:0"]},
                                        {"progression": ["0:1", "0:2", "0:3", "0:4", "0:5", "0:6"]},
                                    ]
                                },
                                {
                                    "sets": [
                                        {"progression": actual_first},
                                        {"progression": actual_second},
                                    ]
                                },
                            ],
                        }
                    },
                }
            }
        }
    }

    metrics = _trajectory_validation(predictions, labels)
    assert metrics["status"] == "TRAJECTORY_HISTORICAL_DIAGNOSTIC"
    assert metrics["promotion_gate"] is False
    assert metrics["checkpoint_neutral_start_server"]["after_2_games"]["top1_accuracy"] == 1.0
    assert metrics["checkpoint_neutral_start_server"]["after_4_games"]["top1_accuracy"] == 0.0
    assert metrics["checkpoint_neutral_start_server"]["after_4_games"]["top3_accuracy"] == 1.0
    first = metrics["first_set_conditioned_on_observed_first_server"]
    assert first["n"] == 1
    assert first["hit_at_1"] == 0.0
    assert first["hit_at_3"] == 1.0
    assert first["hit_at_8"] == 1.0
    storyline = metrics["primary_storyline_match_score_conditioned_on_observed_first_server"]
    assert storyline["n"] == 1
    assert storyline["hit_at_1"] == 0.0
    assert storyline["hit_at_2"] == 1.0
    assert storyline["hit_at_3"] == 1.0
    set_winners = metrics["set_winner_sequence_conditioned_on_observed_first_server"]
    assert set_winners["n"] == 1
    assert set_winners["hit_at_1"] == 0.0
    assert set_winners["hit_at_3"] == 1.0
    assert set_winners["hit_at_8"] == 1.0
    match = metrics["match_set_sequence_conditioned_on_observed_first_server"]
    assert match["hit_at_1"] == 1.0
    assert match["hit_at_12"] == 1.0
    full = metrics["full_match_game_path_conditioned_on_observed_first_server"]
    assert full["n"] == 1
    assert full["hit_at_1"] == 0.0
    assert full["hit_at_2"] == 1.0
    assert full["hit_at_4"] == 1.0
    assert 0.0 < full["mean_top1_prefix_fraction"] < 1.0
    assert metrics["coverage"]["set_winner_sequences"] == 1
    assert metrics["coverage"]["full_match_complete_paths"] == 1
