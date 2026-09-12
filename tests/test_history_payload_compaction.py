from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

from compact_frontend_data import prune_history_payload
from model_telemetry_v84c import collect_rows


def _autolearn_signal():
    return {
        "key": "set1_total|8.5|over",
        "label": "1. set OVER 8.5",
        "market": "set1_total",
        "pick": "over",
        "line": 8.5,
        "score": 76.0,
        "result": "hit",
        "source_model": "ensemble_v84",
        "model_scores": {
            "current": 72.0,
            "catboost": 78.0,
            "tabpfn": 74.0,
            "ensemble": 76.0,
        },
        "generator_selected": True,
        "dynamic_weighting": {
            "version": "v8.4D",
            "active": True,
            "status": "ACTIVE",
            "reason": "bounded_segment_adjustment",
            "dimensions": [
                {
                    "dimension": "tour",
                    "value": "ATP",
                    "models": {
                        "current": {"n": 60, "brier": 0.12, "factor": 1.1},
                        "catboost": {"n": 60, "brier": 0.22, "factor": 0.9},
                    },
                }
            ],
            "base_weights": {"current": 0.35, "catboost": 0.55, "tabpfn": 0.10},
            "effective_weights": {"current": 0.42, "catboost": 0.48, "tabpfn": 0.10},
            "max_shift": 0.07,
        },
        "local_weights": {"current": 0.42, "catboost": 0.48, "tabpfn": 0.10},
        "adaptive_prod_v79": {
            "version": "v7.9B-bayesian-meta",
            "status": "STRONG",
            "final_score": 73.5,
            "delta_pp": -2.5,
            "similar_n": 71,
        },
        "raw_score": 76.0,
        "uncapped_score": 73.0,
        "learned_score": 73.5,
        "final_score": 73.5,
        "delta": -2.5,
        "cap_pp": 8.0,
        "applied": True,
        "action": "downgrade",
        "lesson": "duplicated explanatory text",
        "similar_n": 71,
        "historical_accuracy": 0.61,
        "evidence": "STRONG",
        "components": [{"level": "market", "effective_n": 71}],
        "ensemble_raw": 76.0,
        "adaptive_delta_pp": -2.5,
    }


def test_settled_autolearn_compaction_keeps_training_settlement_and_telemetry_state(tmp_path):
    signal = _autolearn_signal()
    untouched_layer = [{"key": "operator", "model_scores": {"ensemble": 75}, "result": "hit"}]
    data = [{
        "match_key": "id:1",
        "status": "settled",
        "signals": [{"market": "match_winner", "pick": "A", "score": 80, "result": "hit"}],
        "autolearn_signals_v84": [signal],
        "player_intelligence_signals_v85": [{"key": signal["key"], "ml_features_v89": {"feature_coverage": 1.0}}],
        "playable_autolearn_signals_v912": untouched_layer,
        "superbet_candidate_signals_v925": [{"key": "candidate", "result": "hit"}],
    }]
    path = tmp_path / "history.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    report = prune_history_payload(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    row = saved[0]["autolearn_signals_v84"][0]

    # Canonical frozen prediction identity/result and every telemetry score stay.
    assert row["key"] == signal["key"]
    assert row["label"] == signal["label"]
    assert row["market"] == signal["market"]
    assert row["pick"] == signal["pick"]
    assert row["line"] == signal["line"]
    assert row["source_model"] == signal["source_model"]
    assert row["score"] == 76.0
    assert row["result"] == "hit"
    assert row["model_scores"] == signal["model_scores"]
    assert row["generator_selected"] is True

    # Keep exactly what model_telemetry_v84c.collect_rows consumes.
    assert row["adaptive_prod_v79"] == {"final_score": 73.5}
    assert row["dynamic_weighting"] == {"active": True}

    assert "local_weights" not in row
    for key in (
        "components", "lesson", "evidence", "action", "similar_n",
        "raw_score", "uncapped_score", "learned_score", "final_score",
        "adaptive_delta_pp",
    ):
        assert key not in row

    # Non-AutoLearn historical evidence is untouched.
    assert saved[0]["player_intelligence_signals_v85"] == data[0]["player_intelligence_signals_v85"]
    assert saved[0]["playable_autolearn_signals_v912"] == untouched_layer
    assert saved[0]["superbet_candidate_signals_v925"] == data[0]["superbet_candidate_signals_v925"]
    assert report["training_evidence_removed"] is False
    assert report["pending_forecasts_changed"] is False

    telemetry_models = {row["model"] for row in collect_rows(saved)}
    assert {"current", "catboost", "tabpfn", "ensemble", "adaptive_prod", "dynamic", "generator"} <= telemetry_models


def test_pending_autolearn_snapshot_is_not_pruned(tmp_path):
    signal = _autolearn_signal()
    data = [{"match_key": "id:2", "status": "pending", "autolearn_signals_v84": [signal]}]
    original = deepcopy(data)
    path = tmp_path / "history.json"
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    prune_history_payload(path)
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert saved == original
