from backend.neuro_shadow_current_v936 import (
    MODE,
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
    feed = build_current_feed([_result()], _history(), {"markets": {"set2_winner": {"status": "COLLECTING_DATA", "model": None}}})
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
    monkeypatch.setattr("backend.neuro_shadow_current_v936.predict", lambda report, snapshot: 0.71)
    training = {"ready_markets": ["set2_winner"], "markets": {"set2_winner": {"status": "SHADOW_MODEL_READY", "model": {}}}}
    feed = build_current_feed([_result()], _history(), training)
    row = feed["matches"][0]["rows"][0]
    assert row["neural_probability"] == 0.71
    assert row["neural_status"] == "SHADOW_MODEL_READY"
    assert feed["neural_rows_count"] == 1
    assert feed["ready_markets"] == ["set2_winner"]
