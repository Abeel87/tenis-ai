from datetime import datetime, timezone
from pathlib import Path

from backend import symphony_model_tracker_v93 as tracker
from backend import symphony_tracker_v90d as legacy

ROOT = Path(__file__).resolve().parents[1]


def _actual():
    return {
        "status": "completed",
        "p1": "Alpha",
        "p2": "Beta",
        "winner": "Alpha",
        "sets": [[6, 0], [4, 6], [6, 3]],
        "match_score": "2:1",
        "number_of_sets": 3,
        "total_games": 25,
        "first_set_score": "6:0",
        "pbp": {"states": {"2": "1:1", "4": "2:2", "6": "3:3"}},
    }


def test_deep_tracker_settles_new_final_score_families_but_not_set2_checkpoints():
    actual = _actual()
    cases = [
        ({"market": "set2_exact_score", "pick": "4:6"}, True),
        ({"market": "exact_sets", "pick": "3"}, True),
        ({"market": "match_games_parity", "pick": "odd"}, True),
        ({"market": "set1_games_parity", "pick": "even"}, True),
        ({"market": "set2_games_parity", "pick": "even"}, True),
        ({"market": "any_set_to_nil", "pick": "yes"}, True),
        ({"market": "p1_exactly_2_sets", "pick": "yes"}, True),
        ({"market": "p2_exactly_1_set", "pick": "yes"}, True),
        ({"market": "p1_wins_a_set", "pick": "yes"}, True),
        ({"market": "set_handicap", "pick": "Alpha", "line": -0.5}, True),
    ]
    for leg, expected in cases:
        assert tracker.evaluate_model_leg(leg, actual, "Alpha", "Beta") is expected, leg

    assert tracker.evaluate_model_leg(
        {"market": "set2_game_state", "pick": "2:2", "checkpoint": 4},
        actual,
        "Alpha",
        "Beta",
    ) is None

    # Existing first-set PBP settlement continues to work through v9.0D.
    assert tracker.evaluate_model_leg(
        {"market": "game_state", "pick": "2:2", "checkpoint": 4},
        actual,
        "Alpha",
        "Beta",
    ) is True


def test_model_stats_are_observation_only_and_add_market_and_joint_calibration():
    history = {
        "matches": [{
            "status": "settled",
            "recommended_leg_count": 2,
            "scheduled_time": "2026-08-28T10:00:00+00:00",
            "compositions": {
                "2": {
                    "story_type": "COMEBACK_AFTER_SET1",
                    "symphony_score": 84.0,
                    "joint_probability": 34.0,
                    "path_coverage": 1.0,
                    "fragility": {"value": 9.0},
                    "selection": [
                        {"market": "exact_sets", "pick": "3", "evidence_score": 78.0, "path_probability": 63.0},
                        {"market": "p1_wins_a_set", "pick": "yes", "evidence_score": 82.0, "path_probability": 91.0},
                    ],
                }
            },
            "settlement": {
                "compositions": {
                    "2": {
                        "resolved_legs": 2,
                        "hit_legs": 2,
                        "miss_legs": 0,
                        "unknown_legs": 0,
                        "fully_resolved": True,
                        "full_result": "hit",
                        "legs_detail": [
                            {"market": "exact_sets", "result": "hit"},
                            {"market": "p1_wins_a_set", "result": "hit"},
                        ],
                    }
                }
            },
        }]
    }
    stats = tracker.aggregate(history, datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc))

    assert stats["layer"] == "MODEL_RAW_DEEP"
    assert stats["mode"] == "MODEL_RAW_DEEP_STATS_ONLY"
    assert stats["analysis_only"] is True
    assert stats["operator_playable"] is False
    assert stats["learning_contract"]["separate_from_superbet_playable"] is True
    assert stats["learning_contract"]["feeds_existing_auto_learning"] is False
    assert stats["auto"]["full_hit_rate"] == 100.0

    by_market = {row["market"]: row for row in stats["auto_market_accuracy"]}
    assert by_market["exact_sets"]["accuracy"] == 100.0
    assert by_market["p1_wins_a_set"]["accuracy"] == 100.0
    assert stats["auto_story_types"][0]["story_type"] == "COMEBACK_AFTER_SET1"
    assert stats["joint_calibration"][0]["bucket"] == "30-40%"
    assert stats["joint_calibration"][0]["observed_full_hit_rate"] == 100.0


def test_model_history_and_stats_never_overwrite_existing_symphony_learning_files():
    assert tracker.REPORT_PATH.name == "symphony_model_v93.json"
    assert tracker.HISTORY_PATH.name == "symphony_model_history_v93.json"
    assert tracker.STATS_PATH.name == "symphony_model_stats_v93.json"
    assert tracker.HISTORY_PATH != legacy.HISTORY_PATH
    assert tracker.STATS_PATH != legacy.STATS_PATH


def test_stats_ui_reads_both_layers_and_labels_model_raw_separately():
    js = (ROOT / "frontend" / "symphony-stats-v90d.js").read_text(encoding="utf-8")
    assert "symphony_stats_v90d.json" in js
    assert "symphony_model_stats_v93.json" in js
    assert "MODEL/RAW DEEP" in js
    assert "bez wpływu na AUTO/PLAYABLE" in js
    assert "Kalibracja joint probability" in js
    assert "Rynki użyte przez AUTO" in js
