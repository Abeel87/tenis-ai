import json

import backend.neuro_shadow_training_v936 as training
from backend.neuro_shadow_training_v936 import (
    AUTO_PROMOTION,
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    build_training_report,
    refresh_training_artifact,
    training_fingerprint,
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
    assert report["ready_markets"] == []
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


def test_training_groups_history_before_calling_each_market_model(monkeypatch):
    calls = []

    def fake_train(rows, market):
        calls.append((market, [row.get("market") for row in rows]))
        return {
            "market": market,
            "mode": "SHADOW",
            "status": "COLLECTING_DATA",
            "model": None,
            "production_influence": False,
            "playable_influence": False,
        }

    monkeypatch.setattr(training, "train_market", fake_train)
    report = training.build_training_report([
        {"market": "set2_total"},
        {"market": "match_game_handicap"},
        {"market": "set2_total"},
        {"market": ""},
    ])

    assert report["markets_seen"] == 2
    assert calls == [
        ("match_game_handicap", ["match_game_handicap"]),
        ("set2_total", ["set2_total", "set2_total"]),
    ]


def test_side_market_history_quarantines_misoriented_player_without_rewriting_history(monkeypatch):
    calls = []

    def fake_train(rows, market):
        calls.append((market, list(rows)))
        return {
            "market": market,
            "mode": "SHADOW",
            "status": "COLLECTING_DATA",
            "model": None,
            "production_influence": False,
            "playable_influence": False,
        }

    monkeypatch.setattr(training, "train_market", fake_train)
    correct = {
        "prediction_key": "good",
        "match_id": "m1",
        "p1": "Dalibor Svrcina",
        "p2": "Luciano Darderi",
        "market": "p1_exactly_1_set",
        "player": "Svrcina, Dalibor",
        "settlement": "hit",
    }
    wrong = {
        "prediction_key": "bad",
        "match_id": "m1",
        "p1": "Dalibor Svrcina",
        "p2": "Luciano Darderi",
        "market": "p2_exactly_1_set",
        "player": "Svrcina, Dalibor",
        "settlement": "miss",
    }
    original = json.loads(json.dumps([correct, wrong]))

    report = build_training_report([correct, wrong])

    assert report["history_rows_total"] == 2
    assert report["history_rows"] == 1
    assert report["orientation_quarantined_rows"] == 1
    assert calls == [("p1_exactly_1_set", [correct])]
    assert [correct, wrong] == original


def test_fingerprint_ignores_pending_and_void_but_tracks_scored_evidence():
    base = [{
        "prediction_key": "k1",
        "market": "set2_total",
        "settlement": "hit",
        "probability": 0.61,
        "feature_snapshot": {"numeric": {"state_probability": 0.61}},
    }]
    fp = training_fingerprint(base)
    assert training_fingerprint(base + [{"prediction_key": "pending", "settlement": None}]) == fp
    assert training_fingerprint(base + [{"prediction_key": "void", "settlement": "void"}]) == fp
    changed = [dict(base[0], settlement="miss")]
    assert training_fingerprint(changed) != fp


def test_refresh_reuses_model_when_scored_evidence_is_unchanged(tmp_path, monkeypatch):
    history = tmp_path / "history.json"
    artifact = tmp_path / "neural.json"
    rows = [{
        "prediction_key": "k1",
        "market": "set2_total",
        "settlement": "hit",
        "probability": 0.61,
        "feature_snapshot": {"numeric": {"state_probability": 0.61}},
    }]
    history.write_text(json.dumps(rows), encoding="utf-8")
    first = refresh_training_artifact(history, artifact)
    assert first["training_reused"] is False
    before = artifact.read_text(encoding="utf-8")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("unchanged scored evidence must not retrain")

    monkeypatch.setattr(training, "build_training_report", fail_if_called)
    second = refresh_training_artifact(history, artifact)
    assert second["training_reused"] is True
    assert artifact.read_text(encoding="utf-8") == before


def test_new_scored_evidence_invalidates_training_cache(tmp_path):
    history = tmp_path / "history.json"
    artifact = tmp_path / "neural.json"
    history.write_text("[]", encoding="utf-8")
    first = refresh_training_artifact(history, artifact)
    assert first["training_reused"] is False
    rows = [{
        "prediction_key": "k2",
        "market": "set2_total",
        "settlement": "miss",
        "probability": 0.47,
        "feature_snapshot": {"numeric": {"state_probability": 0.47}},
    }]
    history.write_text(json.dumps(rows), encoding="utf-8")
    second = refresh_training_artifact(history, artifact)
    assert second["training_reused"] is False
    assert second["training_fingerprint"] != first["training_fingerprint"]


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
    assert saved["auto_promote"] is False
