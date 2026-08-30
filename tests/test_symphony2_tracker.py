from backend.symphony2_tracker import capture, settle, performance_stats


def _current():
    return {
        "version": "symphony2-runtime-1",
        "matches": [{
            "id": 123,
            "p1": "A",
            "p2": "B",
            "scheduled_time": "2026-08-31T10:00:00Z",
            "recommended_leg_count": 2,
            "compositions": {
                "2": {
                    "legs": 2,
                    "score": 77.0,
                    "joint_probability": None,
                    "joint_status": "PENDING_EXACT_SHARED_STATE_ENGINE",
                    "selection": [
                        {"selection_id": "a", "market": "match_total", "pick": "over", "line": 21.5, "operator_model_probability": 72.0, "fixture_line_verified": True},
                        {"selection_id": "b", "market": "set1_total", "pick": "under", "line": 10.5, "operator_model_probability": 69.0, "fixture_line_verified": True},
                    ],
                }
            },
        }],
    }


def test_capture_starts_clean_and_deduplicates():
    doc, count = capture(_current(), {})
    assert count == 1
    assert doc["legacy_symphony_results_imported"] is False
    assert len(doc["entries"]) == 1

    again, count2 = capture(_current(), doc)
    assert count2 == 0
    assert len(again["entries"]) == 1


def test_exact_operator_signature_settles_composition():
    doc, _ = capture(_current(), {})
    base = [{
        "id": 123,
        "playable_autolearn_signals_v912": [
            {"market": "match_total", "pick": "over", "line": 21.5, "result": "hit"},
            {"market": "set1_total", "pick": "under", "line": 10.5, "result": "hit"},
        ],
    }]
    settled, count = settle(doc, base)
    assert count == 1
    assert settled["entries"][0]["result"] == "hit"
    stats = performance_stats(settled)
    assert stats["compositions_settled"] == 1
    assert stats["composition_accuracy"] == 100.0
    assert stats["legacy_symphony_stats_used"] is False


def test_different_line_never_settles_prediction():
    doc, _ = capture(_current(), {})
    base = [{
        "id": 123,
        "playable_signals_v912": [
            {"market": "match_total", "pick": "over", "line": 22.5, "result": "hit"},
            {"market": "set1_total", "pick": "under", "line": 10.5, "result": "hit"},
        ],
    }]
    settled, count = settle(doc, base)
    assert count == 0
    assert settled["entries"][0]["result"] == "pending"
    assert settled["entries"][0]["selection"][0]["result"] == "pending"


def test_capture_rejects_unverified_line():
    current = _current()
    current["matches"][0]["compositions"]["2"]["selection"][0]["fixture_line_verified"] = False
    doc, count = capture(current, {})
    assert count == 0
    assert doc["entries"] == []
