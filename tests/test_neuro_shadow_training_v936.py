import json

from backend.neuro_shadow_training_v936 import (
    AUTO_PROMOTION,
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    build_training_report,
    refresh_training_artifact,
)


def test_training_artifact_is_hard_shadow_only():
    assert AUTO_PROMOTION is False
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False


def test_empty_history_stays_collecting():
    report = build_training_report([])
    assert report["status"] == "COLLECTING_DATA"
    assert report["markets_seen"] == 0
    assert report["markets_ready"] == 0
    assert report["markets"] == {}


def test_small_market_history_does_not_fabricate_model():
    rows = [
        {
            "market": "set2_total",
            "settlement": "hit" if i % 2 else "miss",
            "scheduled_time": f"2026-08-{(i % 20) + 1:02d}T10:00:00Z",
            "feature_snapshot": {
                "numeric": {
                    "state_probability": 0.55,
                    "base_probability": None,
                    "current_probability": None,
                    "catboost_probability": None,
                    "tabpfn_probability": None,
                    "adaptive_probability": None,
                    "best_of_5": 0.0,
                    "surface_hard": 1.0,
                    "surface_clay": 0.0,
                    "surface_grass": 0.0,
                }
            },
        }
        for i in range(12)
    ]
    report = build_training_report(rows)
    market = report["markets"]["set2_total"]
    assert report["status"] == "COLLECTING_DATA"
    assert market["status"] == "COLLECTING_DATA"
    assert market["model"] is None


def test_refresh_writes_dedicated_artifact(tmp_path):
    history = tmp_path / "history.json"
    artifact = tmp_path / "neural.json"
    history.write_text("[]", encoding="utf-8")
    report = refresh_training_artifact(history, artifact)
    assert artifact.exists()
    saved = json.loads(artifact.read_text(encoding="utf-8"))
    assert saved == report
    assert saved["production_influence"] is False
    assert saved["playable_influence"] is False
    assert saved["auto_promotion"] is False
