from datetime import datetime, timezone

from backend.player_dna_hold_walk_forward import (
    FOLDS,
    UNIQUE_DURATION_MARKETS,
    aggregate_folds,
    aggregate_segments,
    partition_feature_rows,
)


def _row(match_id, hour):
    return {
        "match_id": str(match_id),
        "scheduled_time": datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
    }


def test_partition_never_splits_same_timestamp_group():
    rows = [
        _row(1, 1),
        _row(2, 2),
        _row(3, 3),
        _row(4, 3),
        _row(5, 4),
        _row(6, 5),
        _row(7, 6),
        _row(8, 7),
    ]
    fit, calibration, test, split = partition_feature_rows(rows, 0.40, 0.70, 1.0)
    assert split["same_timestamp_split"] is False
    buckets = [
        {row["match_id"] for row in fit},
        {row["match_id"] for row in calibration},
        {row["match_id"] for row in test},
    ]
    assert sum(int("3" in bucket) + int("4" in bucket) for bucket in buckets) == 2
    assert any({"3", "4"}.issubset(bucket) for bucket in buckets)


def _fold(name, promising=True, game=True, duration=True, match_gain=0.001, first_set_gain=0.001):
    comparison = {
        market: {"improved": duration, "brier_gain_calibrated_vs_raw": 0.001 if duration else -0.001}
        for market in UNIQUE_DURATION_MARKETS
    }
    return {
        "name": name,
        "status": "FOLD_COMPLETE",
        "signal": "PROMISING" if promising else "NOT_YET_PROVEN",
        "game_hold_test": {"improved": game},
        "market_comparison": comparison,
        "summary": {
            "match_winner_brier_gain_calibrated_vs_raw": match_gain,
            "first_set_winner_brier_gain_calibrated_vs_raw": first_set_gain,
        },
    }


def test_aggregate_requires_repeatable_multi_fold_signal():
    folds = [_fold("wf1"), _fold("wf2"), _fold("wf3", promising=False)]
    summary = aggregate_folds(folds)
    assert summary["completed_folds"] == len(FOLDS)
    assert summary["promising_folds"] == 2
    assert summary["game_hold_improved_folds"] == 3
    assert summary["robust"] is True


def test_aggregate_rejects_catastrophic_primary_collapse():
    folds = [
        _fold("wf1"),
        _fold("wf2", match_gain=-0.02),
        _fold("wf3"),
    ]
    summary = aggregate_folds(folds)
    assert summary["no_catastrophic_primary_collapse"] is False
    assert summary["robust"] is False


def test_mature_walk_forward_windows_are_adjacent_and_disjoint():
    assert FOLDS == (
        ("wf1", 0.60, 0.70, 0.80),
        ("wf2", 0.70, 0.80, 0.90),
        ("wf3", 0.80, 0.90, 1.00),
    )
    assert FOLDS[0][3] == FOLDS[1][2]
    assert FOLDS[1][3] == FOLDS[2][2]


def test_segment_aggregate_requires_repeatability():
    folds = [
        {
            "segments": {
                "tour": {
                    "atp": {
                        "settled_matches": 40,
                        "duration_markets_improved": 4,
                        "match_winner_brier_gain": 0.01,
                        "first_set_winner_brier_gain": 0.00,
                    },
                    "wta": {
                        "settled_matches": 35,
                        "duration_markets_improved": 1,
                        "match_winner_brier_gain": 0.00,
                        "first_set_winner_brier_gain": -0.002,
                    },
                },
                "surface": {},
            }
        },
        {
            "segments": {
                "tour": {
                    "atp": {
                        "settled_matches": 50,
                        "duration_markets_improved": 3,
                        "match_winner_brier_gain": 0.00,
                        "first_set_winner_brier_gain": 0.001,
                    },
                    "wta": {
                        "settled_matches": 45,
                        "duration_markets_improved": 0,
                        "match_winner_brier_gain": 0.00,
                        "first_set_winner_brier_gain": -0.003,
                    },
                },
                "surface": {},
            }
        },
    ]
    summary = aggregate_segments(folds)
    assert summary["tour"]["atp"]["repeatable_duration_signal"] is True
    assert summary["tour"]["wta"]["repeatable_duration_signal"] is False
