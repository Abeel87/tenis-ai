from datetime import datetime, timezone

from backend.symphony_leg_learning_v90d import apply_historical_leg_learning
from backend.symphony_tracker_v90d import (
    aggregate,
    capture,
    evaluate_leg,
    settle,
)


def _legs():
    return [
        {"key": "winner|A", "label": "A wygra", "market": "match_winner", "pick": "A"},
        {"key": "set1|A", "label": "A 1. set", "market": "set1_winner", "pick": "A"},
        {"key": "set1_total|8.5|over", "label": "1. set O8.5", "market": "set1_total", "pick": "over", "line": 8.5},
        {"key": "match_total|20.5|under", "label": "Mecz U20.5", "market": "match_total", "pick": "under", "line": 20.5},
        {"key": "exact|2:0", "label": "2:0", "market": "exact_match_score", "pick": "2:0"},
        {"key": "set1_exact|6:4", "label": "6:4", "market": "set1_exact_score", "pick": "6:4"},
    ]


def _report(score=90.0):
    legs = _legs()
    compositions = {}
    for n in range(2, 7):
        compositions[str(n)] = {
            "story_type": "FAST_CONTROL",
            "symphony_score": score - (n - 2),
            "joint_probability": 65 - 5 * (n - 2),
            "path_coverage": 1.0,
            "prod_shadow_agreement": 0.8,
            "model_conflict": 0.05,
            "fragility": [{"key": legs[n - 1]["key"], "label": legs[n - 1]["label"], "fragility": 8 + n}],
            "selection": legs[:n],
        }
    return {
        "version": "v9.0D.1",
        "engine_version": "v9.0B",
        "matches": [{
            "id": 123,
            "match_key": "id:123",
            "p1": "A",
            "p2": "B",
            "scheduled_time": "2026-08-27T22:00:00Z",
            "tour": "atp",
            "tournament": "Test",
            "surface": "hard",
            "best_of": 3,
            "recommended_leg_count": 4,
            "leg_count_intelligence": {"recommended": 4},
            "compositions": compositions,
        }],
    }


def _feed():
    return {
        "matches": [{
            "match_id": 123,
            "match_key": "id:123",
            "status": "completed",
            "p1": "A",
            "p2": "B",
            "winner": "A",
            "sets": [[6, 4], [6, 3]],
            "match_score": "2:0",
            "number_of_sets": 2,
            "total_games": 19,
            "first_set_score": "6:4",
            "pbp": {"states": {"2": "1:1", "4": "3:1", "6": "4:2"}},
        }]
    }


def test_capture_keeps_latest_snapshot_before_freeze_and_never_overwrites_after():
    t1 = datetime(2026, 8, 27, 20, 0, tzinfo=timezone.utc)
    history, added, updated = capture(_report(90), {}, t1)
    assert added == 1 and updated == 0
    assert history["matches"][0]["compositions"]["2"]["symphony_score"] == 90

    t2 = datetime(2026, 8, 27, 21, 30, tzinfo=timezone.utc)
    history, added, updated = capture(_report(94), history, t2)
    assert added == 0 and updated == 1
    assert history["matches"][0]["compositions"]["2"]["symphony_score"] == 94

    # Freeze is 5 minutes before the 22:00 start. A 21:56 run must not replace it.
    t3 = datetime(2026, 8, 27, 21, 56, tzinfo=timezone.utc)
    history, added, updated = capture(_report(99), history, t3)
    assert added == 0 and updated == 0
    assert history["matches"][0]["compositions"]["2"]["symphony_score"] == 94


def test_settlement_scores_every_leg_count_on_the_same_match():
    now = datetime(2026, 8, 27, 20, 0, tzinfo=timezone.utc)
    history, _, _ = capture(_report(), {}, now)
    settled_at = datetime(2026, 8, 27, 23, 30, tzinfo=timezone.utc)
    history, settled, voided = settle(history, _feed(), settled_at)
    assert settled == 1 and voided == 0
    row = history["matches"][0]
    assert row["status"] == "settled"
    for n in range(2, 7):
        result = row["settlement"]["compositions"][str(n)]
        assert result["fully_resolved"] is True
        assert result["full_result"] == "hit"
        assert result["hit_legs"] == n

    stats = aggregate(history, settled_at)
    assert stats["settled_matches"] == 1
    for n in range(2, 7):
        bucket = stats["leg_counts"][str(n)]
        assert bucket["full_settled"] == 1
        assert bucket["full_hit_rate"] == 100.0
        assert bucket["leg_accuracy"] == 100.0
        assert bucket["history_weight_ready"] is False
    assert stats["auto"]["full_settled"] == 1
    assert stats["auto"]["full_hit_rate"] == 100.0


def test_unknown_serve_actual_is_unknown_not_a_fake_miss():
    actual = _feed()["matches"][0]
    leg = {"market": "most_aces", "pick": "A", "key": "most_aces|A"}
    assert evaluate_leg(leg, actual, "A", "B") is None


def test_history_only_changes_auto_after_multiple_leg_buckets_are_ready():
    intelligence = {
        "recommended": 3,
        "mode": "CURRENT_MATCH_MATH",
        "historical_learning_active": False,
        "reason": "3 zdarzenia",
        "options": [
            {"legs": 3, "eligible": True, "auto_utility": 100.0},
            {"legs": 4, "eligible": True, "auto_utility": 99.5},
        ],
    }
    stats = {
        "leg_counts": {
            "3": {"history_weight_ready": True, "normalized_quality": 70.0, "full_settled": 30, "resolved_legs": 90},
            "4": {"history_weight_ready": True, "normalized_quality": 80.0, "full_settled": 30, "resolved_legs": 120},
        }
    }
    learned = apply_historical_leg_learning(intelligence, stats)
    assert learned["historical_learning_active"] is True
    assert learned["recommended"] == 4
    opt3 = next(x for x in learned["options"] if x["legs"] == 3)
    opt4 = next(x for x in learned["options"] if x["legs"] == 4)
    assert opt3["history_bonus"] < 0 < opt4["history_bonus"]


def test_single_ready_bucket_cannot_steer_auto():
    intelligence = {
        "recommended": 3,
        "mode": "CURRENT_MATCH_MATH",
        "options": [
            {"legs": 3, "eligible": True, "auto_utility": 100.0},
            {"legs": 4, "eligible": True, "auto_utility": 99.5},
        ],
    }
    stats = {
        "leg_counts": {
            "4": {"history_weight_ready": True, "normalized_quality": 90.0, "full_settled": 50, "resolved_legs": 200},
        }
    }
    learned = apply_historical_leg_learning(intelligence, stats)
    assert learned["historical_learning_active"] is False
    assert learned["recommended"] == 3
