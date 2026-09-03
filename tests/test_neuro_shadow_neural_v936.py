import json
from pathlib import Path

from backend.neuro_shadow_neural import (
    FEATURE_NAMES,
    MODEL_VERSION,
    build_artifact,
    predict_probability,
    train_model,
)


def _rows():
    base = {
        "feature_snapshot": {
            "numeric": {
                "state_probability": 0.7,
                "sym_prob": 0.68,
                "base_prob": 0.66,
                "hold_edge": 0.08,
                "elo_edge": 0.04,
                "player_form_edge": 0.03,
                "market_line": 9.5,
            },
            "metadata": {
                "market": "set2_total",
                "surface": "hard",
                "tour": "ATP",
                "side": 1,
                "pick": "over",
            },
        },
        "market": "set2_total",
        "surface": "hard",
        "tour": "ATP",
        "side": 1,
        "pick": "over",
        "line": 9.5,
    }
    out = []
    for i in range(24):
        row = json.loads(json.dumps(base))
        row["settlement"] = "hit" if i % 3 else "miss"
        row["feature_snapshot"]["numeric"]["state_probability"] = 0.55 + (i % 8) * 0.04
        row["feature_snapshot"]["numeric"]["sym_prob"] = 0.54 + (i % 6) * 0.05
        row["feature_snapshot"]["numeric"]["base_prob"] = 0.52 + (i % 5) * 0.05
        row["feature_snapshot"]["numeric"]["hold_edge"] = (i % 4) * 0.03
        out.append(row)
    return out


def test_feature_contract_is_stable_and_versioned():
    assert MODEL_VERSION
    assert FEATURE_NAMES == (
        "state_probability",
        "sym_prob",
        "base_prob",
        "hold_edge",
        "elo_edge",
        "player_form_edge",
        "market_line",
    )


def test_train_model_returns_deterministic_artifact_shape():
    artifact = train_model(_rows())
    assert artifact["model_version"] == MODEL_VERSION
    assert artifact["feature_names"] == list(FEATURE_NAMES)
    assert artifact["n"] == 24
    assert len(artifact["weights"]) == len(FEATURE_NAMES)
    assert isinstance(artifact["bias"], float)
    assert artifact["training"]["scored"] == 24


def test_predict_probability_is_bounded_and_repeatable():
    artifact = train_model(_rows())
    sample = _rows()[1]["feature_snapshot"]
    p1 = predict_probability(sample, artifact)
    p2 = predict_probability(sample, artifact)
    assert p1 == p2
    assert 0.0 <= p1 <= 1.0


def test_build_artifact_serializes_to_json(tmp_path: Path):
    artifact = build_artifact(_rows(), generated_at="2026-09-01T12:00:00Z")
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["generated_at"] == "2026-09-01T12:00:00Z"
    assert loaded["model_version"] == MODEL_VERSION


def test_predict_probability_falls_back_when_artifact_missing():
    sample = _rows()[0]["feature_snapshot"]
    p = predict_probability(sample, None)
    assert p == sample["numeric"]["state_probability"]


def test_predict_probability_rejects_invalid_feature_snapshot():
    artifact = train_model(_rows())
    assert predict_probability({}, artifact) is None
    assert predict_probability({"numeric": {}}, artifact) is None


def test_train_model_ignores_unscored_rows():
    rows = _rows()
    rows.extend([
        {**rows[0], "settlement": "void"},
        {**rows[0], "settlement": "unverifiable"},
        {**rows[0], "settlement": None},
    ])
    artifact = train_model(rows)
    assert artifact["n"] == 24


def test_train_model_is_order_stable_for_same_rows():
    rows = _rows()
    forward = train_model(rows)
    backward = train_model(list(reversed(rows)))
    assert forward["weights"] == backward["weights"]
    assert forward["bias"] == backward["bias"]


def test_train_model_uses_only_snapshot_numeric_contract():
    rows = _rows()
    baseline = train_model(rows)
    mutated = json.loads(json.dumps(rows))
    for row in mutated:
        row["probability"] = 0.01
        row["match_id"] = "noise"
        row["feature_snapshot"]["metadata"]["surface"] = "clay"
    candidate = train_model(mutated)
    assert baseline["weights"] == candidate["weights"]
    assert baseline["bias"] == candidate["bias"]


def test_train_model_handles_constant_feature_columns():
    rows = _rows()
    for row in rows:
        row["feature_snapshot"]["numeric"]["elo_edge"] = 0.0
    artifact = train_model(rows)
    assert len(artifact["weights"]) == len(FEATURE_NAMES)
    assert all(isinstance(v, float) for v in artifact["weights"])


def test_probability_moves_with_signal_direction():
    rows = _rows()
    artifact = train_model(rows)
    low = json.loads(json.dumps(rows[0]["feature_snapshot"]))
    high = json.loads(json.dumps(rows[0]["feature_snapshot"]))
    for key in ("state_probability", "sym_prob", "base_prob"):
        low["numeric"][key] = 0.45
        high["numeric"][key] = 0.85
    p_low = predict_probability(low, artifact)
    p_high = predict_probability(high, artifact)
    assert p_low is not None and p_high is not None
    assert p_low != p_high
