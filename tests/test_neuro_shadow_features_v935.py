from backend.neuro_shadow_features import (
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    extract_feature_snapshot,
    model_signal_index,
    selection_signature,
)


def _match():
    return {
        "p1": "Alpha",
        "p2": "Beta",
        "best_of": 3,
        "surface": "Hard",
        "result": {"winner": "Alpha"},
    }


def _selection():
    return {
        "market": "set2_total",
        "pick": "Over",
        "line": 9.5,
        "checkpoint": None,
        "player": None,
    }


def test_feature_layer_is_hard_shadow_only():
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False


def test_exact_model_signal_index_and_probability_normalization():
    selection = _selection()
    signal = {
        **selection,
        "score": 72.0,
        "model_scores": {"current": 0.68, "catboost": 65.0, "tabpfn": 0.61},
        "adaptive_prod_v79": {"final_score": 70.0},
    }
    index = model_signal_index({"model_signals": [signal]})
    assert index[selection_signature(selection)] is signal

    snapshot = extract_feature_snapshot(
        _match(), selection, state_probability=0.64, model_signal=signal
    )
    numeric = snapshot["numeric"]
    assert numeric["state_probability"] == 0.64
    assert numeric["base_probability"] == 0.72
    assert numeric["current_probability"] == 0.68
    assert numeric["catboost_probability"] == 0.65
    assert numeric["tabpfn_probability"] == 0.61
    assert numeric["adaptive_probability"] == 0.70
    assert numeric["surface_hard"] == 1.0
    assert numeric["best_of_5"] == 0.0
    assert snapshot["existing_model_evidence_count"] == 5


def test_snapshot_never_copies_final_result_or_bookmaker_price():
    match = _match()
    match["final_result"] = {"winner": "Alpha", "sets": [[6, 0], [6, 0]]}
    selection = {**_selection(), "price": 1.91, "odds": 1.91}
    signal = {**selection, "score": 75.0, "result": "hit", "settlement": "hit"}
    snapshot = extract_feature_snapshot(match, selection, state_probability=0.55, model_signal=signal)
    assert snapshot["contains_final_result"] is False
    assert snapshot["contains_bookmaker_price"] is False
    assert "result" not in snapshot
    assert "price" not in snapshot
    assert "odds" not in snapshot


def test_missing_existing_models_stays_missing_instead_of_fabricated():
    snapshot = extract_feature_snapshot(_match(), _selection(), state_probability=0.57)
    numeric = snapshot["numeric"]
    assert numeric["state_probability"] == 0.57
    assert numeric["base_probability"] is None
    assert numeric["catboost_probability"] is None
    assert snapshot["existing_model_evidence_count"] == 0
    assert snapshot["has_existing_model_signal"] is False
