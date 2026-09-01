import json

from backend.neuro_shadow_history_v935 import (
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    append_predictions,
    load_history,
    merge_registered,
    settle_history,
)


def _match():
    return {
        "match_id": "m-1",
        "p1": "Alpha",
        "p2": "Beta",
        "scheduled_time": "2026-09-01T10:00:00Z",
        "surface": "hard",
        "tour": "ATP",
    }


def _row(prob=0.7):
    return {
        "market": "set2_winner",
        "pick": "Alpha",
        "line": None,
        "player": None,
        "probability": prob,
        "operator": "Superbet",
        "source_market_id": "mk1",
        "source_outcome_id": "oc1",
        "adapter_version": "x",
        "mode": "SHADOW",
        "operator_playable": False,
    }


def test_history_module_is_hard_shadow_only():
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False


def test_append_predictions_is_deduplicated_and_first_forecast_wins(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"

    first = append_predictions(_match(), [_row(0.7)], history_path=history, stats_path=stats, created_at="t1")
    second = append_predictions(_match(), [_row(0.9)], history_path=history, stats_path=stats, created_at="t2")

    assert first["added"] == 1
    assert second["added"] == 0
    rows = load_history(history)
    assert len(rows) == 1
    assert rows[0]["probability"] == 0.7
    assert rows[0]["created_at"] == "t1"
    assert rows[0]["settlement"] is None


def test_merge_registered_does_not_overwrite_existing_prediction():
    existing = [{"prediction_key": "k", "probability": 0.61}]
    incoming = [{"prediction_key": "k", "probability": 0.99}, {"prediction_key": "k2", "probability": 0.55}]
    merged = merge_registered(existing, incoming)
    assert merged == [
        {"prediction_key": "k", "probability": 0.61},
        {"prediction_key": "k2", "probability": 0.55},
    ]


def test_settle_history_updates_pending_row_and_metrics(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    append_predictions(_match(), [_row(0.7)], history_path=history, stats_path=stats, created_at="t1")

    final = {
        "match_id": "m-1",
        "status": "completed",
        "p1": "Alpha",
        "p2": "Beta",
        "sets": [[6, 4], [6, 3]],
        "number_of_sets": 2,
    }
    result = settle_history([final], history_path=history, stats_path=stats)

    assert result["settled_now"] == 1
    assert result["pending"] == 0
    assert result["scored"] == 1
    rows = load_history(history)
    assert rows[0]["settlement"] == "hit"
    assert rows[0]["probability"] == 0.7
    assert rows[0]["target"] == 1.0
    payload = json.loads(stats.read_text(encoding="utf-8"))
    assert payload["overall"]["n"] == 1
    assert payload["overall"]["brier"] == (0.7 - 1.0) ** 2


def test_void_is_persisted_but_not_scored(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    row = _row(0.7)
    row["market"] = "set3_winner"
    append_predictions(_match(), [row], history_path=history, stats_path=stats, created_at="t1")

    final = {
        "match_id": "m-1",
        "status": "completed",
        "p1": "Alpha",
        "p2": "Beta",
        "sets": [[6, 4], [6, 3]],
        "number_of_sets": 2,
    }
    result = settle_history([final], history_path=history, stats_path=stats)
    assert result["settled_now"] == 1
    assert result["scored"] == 0
    rows = load_history(history)
    assert rows[0]["settlement"] == "void"


def test_missing_final_leaves_prediction_pending(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    append_predictions(_match(), [_row()], history_path=history, stats_path=stats, created_at="t1")
    result = settle_history([], history_path=history, stats_path=stats)
    assert result["settled_now"] == 0
    assert result["pending"] == 1
    assert load_history(history)[0]["settlement"] is None
