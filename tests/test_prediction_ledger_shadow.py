from datetime import datetime, timezone

import backend.prediction_ledger_shadow as ledger


def _row():
    return {
        "match_key": "id:123",
        "scheduled_time": "2026-09-21T12:00:00+00:00",
        "candidate_key": "set1_total|8.5|over",
        "market": "set1_total",
        "pick": "over",
        "line": 8.5,
        "support": 6,
        "tour": "ATP",
        "surface": "HARD",
    }


def test_capture_all_supported_prediction_before_selection():
    now = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    rows = ledger.capture_rows([_row()], [0.61], [0.64], [None], now=now)
    assert len(rows) == 1
    item = rows[0]
    assert item["population_tags"] == ["ALL"]
    assert item["captured_at"] < item["scheduled_time"]
    assert item["model_scores"]["current"]["available"] is True
    assert item["model_scores"]["catboost"]["available"] is True
    assert item["model_scores"]["tabpfn"]["available"] is False
    assert "generator_selected" not in item
    assert "playable" not in item


def test_capture_rejects_at_or_after_start_and_keeps_id_stable():
    before = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    first = ledger.capture_rows([_row()], [0.61], [0.64], [0.59], now=before)[0]
    again = ledger.capture_rows([_row()], [0.70], [0.71], [0.72], now=before)[0]
    assert first["prediction_id"] == again["prediction_id"]

    at_start = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    assert ledger.capture_rows([_row()], [0.61], [0.64], [0.59], now=at_start) == []


def test_capture_has_owner_version_semantics_and_provenance():
    now = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    item = ledger.capture_rows([_row()], [0.61], [None], [None], now=now)[0]
    assert item["schema_version"] == ledger.SCHEMA_VERSION
    assert item["producer"]["owner"] == "autolearn_v84"
    assert item["score_semantics"] == "probability_0_1"
    assert item["candidate_identity"] == _row()["candidate_key"]
    assert item["context_snapshot_sha256"].startswith("sha256:")
    assert item["production_influence"] is False
    assert item["learning_consumer_enabled"] is False


def test_merge_is_append_only_and_keeps_first_frozen_snapshot():
    now = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    first = ledger.capture_rows([_row()], [0.61], [0.64], [0.59], now=now)[0]
    existing = ledger.merge_ledger({}, [first], now=now)
    changed = ledger.capture_rows([_row()], [0.91], [0.92], [0.93], now=now)[0]
    merged = ledger.merge_ledger(existing, [changed], now=now)
    assert merged["summary"]["captured_this_run"] == 0
    assert len(merged["rows"]) == 1
    assert merged["rows"][0]["model_scores"]["current"]["value"] == 0.61


def test_autolearn_capture_boundary_is_pre_selection_and_consumers_stay_unwired():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "backend" / "autolearn_v84.py").read_text(encoding="utf-8")
    decorated_at = source.index("decorated = _decorate_results(")
    ledger_at = source.index("prediction_ledger_shadow.capture_rows(")
    legacy_at = source.index("history, captured = _capture_frozen(")
    assert decorated_at < ledger_at < legacy_at
    for relative in (
        "backend/model_telemetry_v84c.py",
        "backend/adaptive_learning_v79.py",
        "backend/dynamic_weights_v84d.py",
        "backend/specialist_learning_v79b.py",
    ):
        assert "prediction_ledger_shadow" not in (root / relative).read_text(encoding="utf-8")


def test_summary_labels_all_without_inventing_downstream_populations():
    now = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    rows = ledger.capture_rows([_row()], [0.61], [0.64], [0.59], now=now)
    merged = ledger.merge_ledger({}, rows, now=now)
    summary = merged["summary"]
    assert summary["population_counts"] == {"ALL": 1, "PLAYABLE": None, "SELECTED": None}
    assert summary["model_available_counts"] == {"current": 1, "catboost": 1, "tabpfn": 1}
    assert summary["common_current_catboost_tabpfn"] == 1


def test_existing_unknown_schema_fails_closed():
    import pytest
    now = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="schema mismatch"):
        ledger.merge_ledger({"schema_version": "other", "rows": []}, [], now=now)
