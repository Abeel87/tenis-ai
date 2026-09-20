from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import backend.prediction_ledger_selection_shadow as joins
import backend.prediction_ledger_shadow as ledger


def _ledger_row(**overrides):
    row = {
        "schema_version": ledger.SCHEMA_VERSION,
        "prediction_id": "pred_123",
        "match_key": "id:123",
        "candidate_key": "set1_total|8.5|over",
        "market": "set1_total",
        "pick": "over",
        "line": 8.5,
        "scheduled_time": "2026-09-21T12:00:00+00:00",
        "captured_at": "2026-09-21T10:00:00+00:00",
        "model_scores": {
            "current": {"available": True, "value": 0.61},
            "catboost": {"available": True, "value": 0.64},
            "tabpfn": {"available": True, "value": 0.60},
        },
    }
    row.update(overrides)
    return row


def _ledger_doc(row=None):
    return {"schema_version": ledger.SCHEMA_VERSION, "rows": [row or _ledger_row()]}


def _playable_entry(signal=None, **overrides):
    entry = {
        "id": "123",
        "scheduled_time": "2026-09-21T12:00:00+00:00",
        "playable_captured_at_v912": "2026-09-21T10:30:00+00:00",
        "playable_autolearn_signals_v912": [signal or {
            "key": "superbet|set1_total|8.5|over",
            "market": "set1_total",
            "pick": "over",
            "line": 8.5,
        }],
    }
    entry.update(overrides)
    return entry


def _symphony_entry(leg=None, **overrides):
    entry = {
        "prediction_id": "composition_abc",
        "version": "symphony2-tracker-3",
        "match_id": "123",
        "scheduled_time": "2026-09-21T12:00:00+00:00",
        "captured_at": "2026-09-21T11:00:00+00:00",
        "selection": [leg or {
            "selection_id": "leg-1",
            "market": "set1_total",
            "pick": "over",
            "line": 8.5,
            "checkpoint": None,
            "player": None,
        }],
    }
    entry.update(overrides)
    return entry


def _build(row=None, playable=None, symphony=None):
    return joins.build_sidecar(
        _ledger_doc(row),
        playable if playable is not None else [_playable_entry()],
        {"entries": symphony if symphony is not None else [_symphony_entry()]},
        now=datetime(2026, 9, 21, 11, 30, tzinfo=timezone.utc),
    )


def test_exact_playable_and_symphony_join_without_raw_key_equality():
    doc = _build()
    facts = doc["rows"][0]["facts"]
    assert facts["playable"]["value"] is True
    assert facts["playable"]["signal_key"] == "superbet|set1_total|8.5|over"
    assert facts["symphony_selected"]["value"] is True
    assert facts["symphony_selected"]["composition_prediction_id"] == "composition_abc"
    assert facts["ineed_selected"]["value"] is None
    assert doc["summary"]["population_counts"] == {
        "ALL": 1,
        "PLAYABLE": 1,
        "GENERATOR_SELECTED": None,
        "SYMPHONY_SELECTED": 1,
        "INEED_SELECTED": None,
    }


def test_same_match_but_different_line_does_not_join_and_is_not_false():
    signal = {"market": "set1_total", "pick": "over", "line": 9.5}
    leg = {"selection_id": "leg-x", "market": "set1_total", "pick": "over", "line": 9.5}
    doc = _build(playable=[_playable_entry(signal)], symphony=[_symphony_entry(leg)])
    facts = doc["rows"][0]["facts"]
    assert facts["playable"]["value"] is None
    assert facts["symphony_selected"]["value"] is None
    assert facts["playable"]["status"] == "N/D"
    assert facts["symphony_selected"]["status"] == "N/D"


def test_same_signature_at_or_after_start_fails_closed_on_chronology():
    playable = _playable_entry(playable_captured_at_v912="2026-09-21T12:00:00+00:00")
    symphony = _symphony_entry(captured_at="2026-09-21T12:00:01+00:00")
    doc = _build(playable=[playable], symphony=[symphony])
    facts = doc["rows"][0]["facts"]
    assert facts["playable"]["reason"] == "EXACT_EVIDENCE_WITHOUT_VALID_PREMATCH_CHRONOLOGY"
    assert facts["symphony_selected"]["reason"] == "EXACT_EVIDENCE_WITHOUT_VALID_PREMATCH_CHRONOLOGY"


def test_duplicate_exact_playable_evidence_is_ambiguous_not_selected():
    doc = _build(
        playable=[_playable_entry(), _playable_entry(playable_captured_at_v912="2026-09-21T10:31:00+00:00")],
        symphony=[],
    )
    fact = doc["rows"][0]["facts"]["playable"]
    assert fact["value"] is None
    assert fact["reason"] == "AMBIGUOUS_EXACT_PREMATCH_EVIDENCE"
    assert fact["matching_evidence_count"] == 2


def test_multiple_symphony_compositions_are_preserved_as_ambiguous_evidence():
    second = _symphony_entry(prediction_id="composition_xyz", captured_at="2026-09-21T11:01:00+00:00")
    doc = _build(playable=[], symphony=[_symphony_entry(), second])
    fact = doc["rows"][0]["facts"]["symphony_selected"]
    assert fact["value"] is None
    assert fact["reason"] == "AMBIGUOUS_EXACT_PREMATCH_COMPOSITION_EVIDENCE"
    assert fact["composition_prediction_ids"] == ["composition_abc", "composition_xyz"]


def test_game_state_requires_strict_candidate_checkpoint_and_score_agreement():
    row = _ledger_row(
        candidate_key="state|6|3:3",
        market="game_state",
        pick="3:3",
        line=None,
    )
    good_signal = {"market": "game_state", "pick": "3:3", "checkpoint": 6}
    good_leg = {"selection_id": "state-6", "market": "game_state", "pick": "3:3", "checkpoint": 6}
    doc = _build(row=row, playable=[_playable_entry(good_signal)], symphony=[_symphony_entry(good_leg)])
    assert doc["rows"][0]["facts"]["playable"]["value"] is True
    assert doc["rows"][0]["facts"]["symphony_selected"]["value"] is True

    conflict = _ledger_row(
        candidate_key="state|4|3:3",
        market="game_state",
        pick="2:2",
        line=None,
    )
    failed = _build(row=conflict, playable=[_playable_entry(good_signal)], symphony=[_symphony_entry(good_leg)])
    assert failed["rows"][0]["facts"]["playable"]["reason"] == "GAME_STATE_SCORE_CONFLICT"
    assert failed["rows"][0]["facts"]["symphony_selected"]["reason"] == "GAME_STATE_SCORE_CONFLICT"


def test_invalid_ledger_chronology_blocks_all_downstream_positive_facts():
    row = _ledger_row(captured_at="2026-09-21T12:00:00+00:00")
    doc = _build(row=row)
    result = doc["rows"][0]
    assert result["ledger_pre_match_valid"] is False
    assert result["facts"]["playable"]["value"] is None
    assert result["facts"]["symphony_selected"]["value"] is None
    assert result["facts"]["playable"]["reason"] == "LEDGER_NOT_VALID_PREMATCH_EVIDENCE"


def test_sidecar_does_not_mutate_source_ledger_and_keeps_ineed_unwired():
    source = _ledger_doc()
    before = deepcopy(source)
    doc = joins.build_sidecar(
        source,
        [_playable_entry()],
        {"entries": [_symphony_entry()]},
        now=datetime(2026, 9, 21, 11, 30, tzinfo=timezone.utc),
    )
    assert source == before
    assert doc["ineed_contract"]["network_fetch_enabled"] is False
    assert doc["ineed_contract"]["historical_backfill_enabled"] is False
    assert doc["production_influence"] is False
    assert doc["runtime_gating_enabled"] is False
    assert doc["learning_consumer_enabled"] is False
    assert doc["telemetry_consumer_enabled"] is False


def test_shadow_joiner_is_not_imported_by_learning_telemetry_or_runtime_owners():
    root = Path(__file__).resolve().parents[1]
    forbidden_consumers = (
        "backend/model_telemetry_v84c.py",
        "backend/adaptive_learning_v79.py",
        "backend/dynamic_weights_v84d.py",
        "backend/autolearn_v84.py",
        "backend/superbet_playable.py",
        "backend/symphony2_engine.py",
        "backend/symphony2_tracker.py",
        "backend/ineed_money.py",
    )
    for relative in forbidden_consumers:
        source = (root / relative).read_text(encoding="utf-8")
        assert "prediction_ledger_selection_shadow" not in source
