import json

import backend.neuro_shadow_runner_v935 as runner
from backend.neuro_shadow_runner_v935 import (
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    capture_file,
    capture_matches,
    run_action,
    train_file,
)
from backend.neuro_shadow_history_v935 import load_history


def _match():
    return {
        "id": 123,
        "p1": "Alpha",
        "p2": "Beta",
        "scheduled_time": "2026-09-01T10:00:00Z",
        "surface": "hard",
        "tour": "ATP",
        "best_of": 3,
        "service_model": {"p1_hold": 78.0, "p2_hold": 72.0},
        "second_set_context": {"p1_unconditional": 55.0},
        "superbet_market_v91": {
            "operator_verified": True,
            "canonical_selections": [
                {
                    "market": "set2_total",
                    "pick": "over",
                    "line": 9.5,
                    "player": None,
                    "market_id": "m1",
                    "outcome_id": "o1",
                    "operator_available": True,
                    "operator_line_verified": True,
                },
                {
                    "market": "future_unknown",
                    "pick": "x",
                    "line": None,
                    "player": None,
                    "market_id": "m2",
                    "outcome_id": "o2",
                    "operator_available": True,
                    "operator_line_verified": True,
                },
            ],
        },
    }


def test_runner_is_hard_shadow_only():
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False


def test_capture_uses_verified_canonical_context_only(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    unverified = _match()
    unverified["id"] = 124
    unverified["superbet_market_v91"]["operator_verified"] = False
    result = capture_matches([_match(), unverified], history_path=history, stats_path=stats)
    assert result["matches_seen"] == 2
    assert result["matches_with_verified_operator"] == 1
    assert result["new_candidate_selections"] == 1
    assert result["adapted_predictions"] == 1
    assert result["added_predictions"] == 1
    rows = load_history(history)
    assert len(rows) == 1
    assert rows[0]["market"] == "set2_total"
    assert rows[0]["operator_playable"] is False


def test_repeated_capture_keeps_first_forecast_and_skips_state_rebuild(tmp_path, monkeypatch):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    first = capture_matches([_match()], history_path=history, stats_path=stats)
    def fail_if_called(*args, **kwargs):
        raise AssertionError("unchanged selection must skip costly state adapter")
    monkeypatch.setattr(runner, "adapt_market_context", fail_if_called)
    second = capture_matches([_match()], history_path=history, stats_path=stats)
    assert first["added_predictions"] == 1
    assert second["added_predictions"] == 0
    assert second["new_candidate_selections"] == 0
    assert second["matches_skipped_already_captured"] == 1
    assert len(load_history(history)) == 1


def test_new_operator_selection_after_capture_is_processed_incrementally(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    capture_matches([_match()], history_path=history, stats_path=stats)
    changed = _match()
    changed["superbet_market_v91"]["canonical_selections"].append({
        "market": "set2_total",
        "pick": "under",
        "line": 9.5,
        "player": None,
        "market_id": "m1",
        "outcome_id": "o3",
        "operator_available": True,
        "operator_line_verified": True,
    })
    result = capture_matches([changed], history_path=history, stats_path=stats)
    assert result["new_candidate_selections"] == 1
    assert result["added_predictions"] == 1
    assert len(load_history(history)) == 2


def test_capture_file_handles_real_results_shape(tmp_path):
    results = tmp_path / "results.json"
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    results.write_text(json.dumps([_match()]), encoding="utf-8")
    result = capture_file(results, history_path=history, stats_path=stats)
    assert result["added_predictions"] == 1
    assert history.exists()
    assert stats.exists()


def test_training_status_can_run_after_capture(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    training = tmp_path / "training.json"
    capture_matches([_match()], history_path=history, stats_path=stats)
    report = train_file(history_path=history, training_path=training)
    assert training.exists()
    assert report["mode"] == "SHADOW"
    assert report["status"] == "COLLECTING_DATA"
    assert report["production_influence"] is False
    assert report["playable_influence"] is False


def test_hourly_run_never_invokes_heavy_capture_or_training(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(runner, "settle_file", lambda *a, **k: calls.append("settle") or {})
    monkeypatch.setattr(runner, "capture_file", lambda *a, **k: (_ for _ in ()).throw(AssertionError("hourly run must not capture heavy state")))
    monkeypatch.setattr(runner, "train_file", lambda *a, **k: (_ for _ in ()).throw(AssertionError("hourly run must not train")))
    monkeypatch.setattr(runner, "current_file", lambda *a, **k: calls.append("current") or {})
    payload = run_action(
        "run",
        results_path=tmp_path / "results.json",
        history_path=tmp_path / "history.json",
        stats_path=tmp_path / "stats.json",
        training_path=tmp_path / "training.json",
        current_path=tmp_path / "current.json",
    )
    assert calls == ["settle", "current"]
    assert payload["heavy_training"] is False
    assert payload["heavy_capture"] is False
    assert payload["training_shell_created"] is True
    assert (tmp_path / "training.json").exists()
    shell = json.loads((tmp_path / "training.json").read_text(encoding="utf-8"))
    assert shell["mode"] == "SHADOW"
    assert shell["ready_markets"] == []
    assert shell["production_influence"] is False


def test_hourly_run_does_not_overwrite_existing_training_artifact(monkeypatch, tmp_path):
    training = tmp_path / "training.json"
    training.write_text(json.dumps({"mode": "SHADOW", "sentinel": 123}), encoding="utf-8")
    monkeypatch.setattr(runner, "settle_file", lambda *a, **k: {})
    monkeypatch.setattr(runner, "current_file", lambda *a, **k: {})
    payload = run_action("run", training_path=training)
    assert payload["training_shell_created"] is False
    assert json.loads(training.read_text(encoding="utf-8"))["sentinel"] == 123


def test_full_mode_keeps_explicit_heavy_capture_and_training(monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "settle_file", lambda *a, **k: calls.append("settle") or {})
    monkeypatch.setattr(runner, "capture_file", lambda *a, **k: calls.append("capture") or {})
    monkeypatch.setattr(runner, "train_file", lambda *a, **k: calls.append("train") or {})
    monkeypatch.setattr(runner, "current_file", lambda *a, **k: calls.append("current") or {})
    payload = run_action("full")
    assert calls == ["settle", "capture", "train", "current"]
    assert payload["heavy_training"] is True
    assert payload["heavy_capture"] is True


def test_missing_or_bad_results_is_safe_noop(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    missing = capture_file(tmp_path / "missing.json", history_path=history, stats_path=stats)
    assert missing["matches_seen"] == 0
    bad = tmp_path / "bad.json"
    bad.write_text("not-json", encoding="utf-8")
    invalid = capture_file(bad, history_path=history, stats_path=stats)
    assert invalid["matches_seen"] == 0
