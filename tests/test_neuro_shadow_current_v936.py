from backend.neuro_shadow_current import (
    MODE,
    NEURAL_VERSION,
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    build_current_feed,
)


def _result():
    return {"match_id": "m1", "p1": "Alpha", "p2": "Beta", "scheduled_time": "2026-09-01T12:00:00Z", "surface": "hard", "tour": "ATP"}


def _history():
    return [{
        "prediction_key": "m1|set2_winner|Alpha",
        "match_id": "m1",
        "p1": "Alpha",
        "p2": "Beta",
        "market": "set2_winner",
        "pick": "Alpha",
        "probability": 0.63,
        "feature_snapshot": {"numeric": {}},
        "source_model": "state_distribution",
        "mode": "SHADOW",
        "operator_playable": False,
    }]


def test_current_feed_is_hard_shadow_only():
    assert MODE == "SHADOW"
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False
    feed = build_current_feed([_result()], _history(), {})
    assert feed["mode"] == "SHADOW"
    assert feed["operator_playable"] is False
    assert feed["production_influence"] is False
    assert feed["playable_influence"] is False


def test_collecting_market_never_fabricates_neural_probability():
    training = {
        "neural_version": NEURAL_VERSION,
        "markets": {"set2_winner": {"status": "COLLECTING_DATA", "model": None}},
    }
    feed = build_current_feed([_result()], _history(), training)
    row = feed["matches"][0]["rows"][0]
    assert row["state_probability"] == 0.63
    assert row["neural_probability"] is None
    assert row["neural_status"] == "COLLECTING_DATA"
    assert feed["neural_rows_count"] == 0


def test_old_history_not_in_current_results_is_excluded():
    feed = build_current_feed([], _history(), {})
    assert feed["matches_count"] == 0
    assert feed["rows_count"] == 0
    assert feed["status"] == "NO_CURRENT_ROWS"


def test_ready_market_can_emit_real_neural_probability(monkeypatch):
    monkeypatch.setattr("backend.neuro_shadow_current.predict", lambda report, snapshot: 0.71)
    training = {
        "neural_version": NEURAL_VERSION,
        "ready_markets": ["set2_winner"],
        "markets": {"set2_winner": {"status": "SHADOW_MODEL_READY", "model": {}}},
    }
    feed = build_current_feed([_result()], _history(), training)
    row = feed["matches"][0]["rows"][0]
    assert row["neural_probability"] == 0.71
    assert row["neural_status"] == "SHADOW_MODEL_READY"
    assert feed["neural_rows_count"] == 1
    assert feed["ready_markets"] == ["set2_winner"]
    assert feed["training_artifact_compatible"] is True


def test_stale_ready_artifact_cannot_emit_neural_probability(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("stale model must never reach predict")

    monkeypatch.setattr("backend.neuro_shadow_current.predict", fail_if_called)
    training = {
        "neural_version": "neuro-shadow-neural-vOLD",
        "ready_markets": ["set2_winner"],
        "markets": {"set2_winner": {"status": "SHADOW_MODEL_READY", "model": {}}},
    }
    feed = build_current_feed([_result()], _history(), training)
    row = feed["matches"][0]["rows"][0]
    assert row["state_probability"] == 0.63
    assert row["neural_probability"] is None
    assert row["neural_status"] == "STALE_MODEL_ARTIFACT"
    assert feed["neural_rows_count"] == 0
    assert feed["ready_markets"] == []
    assert feed["training_artifact_compatible"] is False


def test_zero_match_id_is_preserved_in_current_feed():
    result = {**_result(), "match_id": 0}
    history = [{**_history()[0], "match_id": 0, "prediction_key": "0|set2_winner|Alpha"}]
    feed = build_current_feed([result], history, {})
    assert feed["matches_count"] == 1
    assert feed["matches"][0]["match_id"] == "0"
    assert feed["rows_count"] == 1
