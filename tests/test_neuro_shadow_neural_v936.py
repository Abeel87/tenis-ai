import math

from backend.neuro_shadow_neural_v936 import (
    AUTO_PROMOTE,
    MIN_SETTLED,
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    predict,
    train_market,
)


def _snapshot(state, base=None, catboost=None):
    return {
        "numeric": {
            "state_probability": state,
            "base_probability": base,
            "current_probability": base,
            "catboost_probability": catboost,
            "tabpfn_probability": None,
            "adaptive_probability": base,
            "best_of_5": 0.0,
            "surface_hard": 1.0,
            "surface_clay": 0.0,
            "surface_grass": 0.0,
        },
        "contains_final_result": False,
        "contains_bookmaker_price": False,
    }


def _row(index, hit, market="set2_total"):
    # Learnable but not perfect relation: high state probability usually hits.
    state = 0.72 if hit else 0.28
    jitter = ((index % 7) - 3) * 0.01
    state = max(0.05, min(0.95, state + jitter))
    return {
        "market": market,
        "settlement": "hit" if hit else "miss",
        "scheduled_time": f"2026-01-{1 + index // 24:02d}T{index % 24:02d}:00:00Z",
        "created_at": f"2026-01-{1 + index // 24:02d}T{index % 24:02d}:00:00Z",
        "feature_snapshot": _snapshot(state, base=0.65 if hit else 0.35, catboost=state),
    }


def test_neural_layer_is_hard_shadow_only():
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False
    assert AUTO_PROMOTE is False


def test_insufficient_sample_never_emits_model_or_probability():
    rows = [_row(i, i % 2 == 0) for i in range(MIN_SETTLED - 1)]
    report = train_market(rows, "set2_total")
    assert report["status"] == "COLLECTING_DATA"
    assert report["model"] is None
    assert predict(report, _snapshot(0.8)) is None


def test_class_imbalance_gate_blocks_training():
    rows = [_row(i, i < 10) for i in range(MIN_SETTLED + 20)]
    report = train_market(rows, "set2_total")
    assert report["status"] == "COLLECTING_DATA"
    assert report["model"] is None


def test_settled_hit_miss_only_and_per_market_only():
    rows = [_row(i, i % 2 == 0) for i in range(MIN_SETTLED + 20)]
    rows.extend([
        {**_row(200, True), "settlement": "void"},
        {**_row(201, False), "settlement": None},
        _row(202, True, market="set3_total"),
    ])
    report = train_market(rows, "set2_total")
    assert report["gate"]["settled"] == MIN_SETTLED + 20
    assert report["status"] == "SHADOW_MODEL_READY"


def test_training_is_deterministic_and_chronological():
    rows = [_row(i, i % 2 == 0) for i in range(MIN_SETTLED + 40)]
    report1 = train_market(list(reversed(rows)), "set2_total")
    report2 = train_market(rows, "set2_total")
    assert report1["status"] == "SHADOW_MODEL_READY"
    assert report1["validation_start"] == report2["validation_start"]
    assert report1["validation_end"] == report2["validation_end"]
    assert report1["validation"] == report2["validation"]
    assert report1["model"] == report2["model"]


def test_ready_model_returns_bounded_neural_shadow_probability():
    rows = [_row(i, i % 2 == 0) for i in range(MIN_SETTLED + 40)]
    report = train_market(rows, "set2_total")
    p = predict(report, _snapshot(0.8, base=0.75, catboost=0.78))
    assert p is not None
    assert 0.0 <= p <= 1.0
    assert math.isfinite(p)
    assert report["validation"]["brier"] is not None
    assert report["state_baseline_validation"]["brier"] is not None
    assert report["auto_promote"] is False


def test_missing_model_inputs_are_masked_not_fabricated_from_results():
    rows = [_row(i, i % 2 == 0) for i in range(MIN_SETTLED + 40)]
    report = train_market(rows, "set2_total")
    snapshot = _snapshot(0.61, base=None, catboost=None)
    snapshot["final_result"] = {"winner": "Alpha"}
    snapshot["price"] = 1.95
    p = predict(report, snapshot)
    assert p is not None
    assert 0.0 <= p <= 1.0
