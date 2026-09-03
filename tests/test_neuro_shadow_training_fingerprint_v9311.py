from backend.neuro_shadow_training import training_fingerprint


def _row():
    return {
        "prediction_key": "match-1|set2_total|over|9.5|||",
        "match_id": "match-1",
        "p1": "Alpha",
        "p2": "Beta",
        "scheduled_time": "2026-09-01T10:00:00Z",
        "created_at": "2026-09-01T08:00:00Z",
        "market": "set2_total",
        "settlement": "hit",
        "probability": 0.61,
        "feature_snapshot": {"numeric": {"state_probability": 0.61}},
    }


def test_split_time_change_invalidates_training_fingerprint():
    base = _row()
    changed = dict(base, scheduled_time="2026-09-01T11:00:00Z")
    assert training_fingerprint([base]) != training_fingerprint([changed])


def test_match_group_identity_change_invalidates_training_fingerprint():
    base = _row()
    changed = dict(base, match_id="match-2")
    assert training_fingerprint([base]) != training_fingerprint([changed])


def test_pending_split_metadata_still_does_not_trigger_retrain():
    base = _row()
    pending = dict(base, prediction_key="pending", settlement=None, scheduled_time="2099-01-01T00:00:00Z")
    assert training_fingerprint([base]) == training_fingerprint([base, pending])
