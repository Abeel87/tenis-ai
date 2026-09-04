from backend.player_dna_market_backtest import (
    binary_metrics,
    reconstruct_match_label,
)


def _row(idx, sets, games):
    return {
        "event_index": idx,
        "match_format": "BO3",
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
