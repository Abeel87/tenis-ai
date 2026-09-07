import json

import backend.neuro_shadow_training as training
from backend.neuro_shadow_training import (
    AUTO_PROMOTION,
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    PHASE8_FEATURE_NAMES,
    _phase8_feature_vector,
    _phase8_fold_specs,
    _phase8_items,
    build_training_report,
    evaluate_phase8_market,
    refresh_training_artifact,
    summarize_phase8_gate,
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


def _phase8_snapshot(probability, *, bookmaker=False, final=False):
    return {
        "numeric": {
            "state_probability": probability,
            "base_probability": probability,
            "current_probability": probability,
            "catboost_probability": 1.0 - probability,
            "tabpfn_probability": 1.0 - probability,
            "adaptive_probability": probability,
            "best_of_5": 0.0,
            "surface_hard": 1.0,
            "surface_clay": 0.0,
            "surface_grass": 0.0,
        },
        "contains_final_result": final,
        "contains_bookmaker_price": bookmaker,
    }


def _phase8_row(index, hit, *, scheduled_time=None):
    probability = 0.78 if hit else 0.22
    return {
        "prediction_key": f"phase8-{index}",
        "match_id": f"phase8-match-{index}",
        "market": "set2_total",
        "settlement": "hit" if hit else "miss",
        "scheduled_time": scheduled_time
        or f"2026-01-{1 + index // 24:02d}T{index % 24:02d}:00:00Z",
        "created_at": scheduled_time
        or f"2026-01-{1 + index // 24:02d}T{index % 24:02d}:00:00Z",
        "feature_snapshot": _phase8_snapshot(probability),
    }


def test_phase8_feature_contract_forbids_result_and_bookmaker_and_excludes_old_model_outputs():
    row = _phase8_row(0, True)
    vector = _phase8_feature_vector(row)
    assert vector is not None
    assert len(vector) == len(PHASE8_FEATURE_NAMES)
    assert "catboost_probability" not in PHASE8_FEATURE_NAMES
    assert "tabpfn_probability" not in PHASE8_FEATURE_NAMES

    bookmaker = _phase8_row(1, False)
    bookmaker["feature_snapshot"] = _phase8_snapshot(0.4, bookmaker=True)
    assert _phase8_feature_vector(bookmaker) is None

    final = _phase8_row(2, True)
    final["feature_snapshot"] = _phase8_snapshot(0.6, final=True)
    assert _phase8_feature_vector(final) is None


def test_phase8_fold_specs_never_split_equal_timestamp_groups():
    rows = [_phase8_row(i, i % 2 == 0) for i in range(120)]
    shared_time = "2026-01-05T12:30:00Z"
    for i in range(48, 54):
        rows[i]["scheduled_time"] = shared_time
        rows[i]["created_at"] = shared_time

    items = _phase8_items(rows, "set2_total")
    specs = _phase8_fold_specs(items)

    assert len(specs) == 3
    for spec in specs:
        assert spec["same_timestamp_split"] is False
        train_times = {item[0]["scheduled_time"] for item in spec["train"]}
        eval_times = {item[0]["scheduled_time"] for item in spec["evaluation"]}
        assert train_times.isdisjoint(eval_times)


def test_phase8_market_walk_forward_compares_identical_rows_for_all_model_classes():
    rows = [_phase8_row(i, i % 2 == 0) for i in range(160)]
    report = evaluate_phase8_market(rows, "set2_total")

    assert report["status"] == "WALK_FORWARD_COMPLETE"
    assert report["complete_folds"] == 3
    assert report["required_folds"] == 3
    assert report["runtime_switch_authorized"] is False
    for fold in report["folds"]:
        assert fold["status"] == "FOLD_COMPLETE"
        assert fold["same_timestamp_split"] is False
        assert fold["same_eval_rows_all_models"] is True
        models = fold["models"]
        assert set(models) == {"logistic", "catboost", "neural", "ensemble"}
        assert len({models[name]["n"] for name in models}) == 1
        for metrics in models.values():
            assert metrics["brier"] is not None
            assert metrics["log_loss"] is not None
            assert metrics["ece_10_bin"] is not None


def test_phase8_gate_closes_evaluation_without_global_model_promotion():
    market_reports = {}
    for index in range(6):
        market_reports[f"market-{index}"] = {
            "status": "WALK_FORWARD_COMPLETE",
            "complete_folds": 3,
            "folds": [
                {
                    "status": "FOLD_COMPLETE",
                    "same_eval_rows_all_models": True,
                }
                for _ in range(3)
            ],
            "neural_review_candidate": index == 0,
            "ensemble_review_candidate": index == 1,
        }

    summary = summarize_phase8_gate(
        market_reports,
        {
            "phase7_complete": True,
            "phase8_ready": True,
        },
    )

    assert summary["technical_validation_complete"] is True
    assert summary["phase8_complete"] is True
    assert summary["phase9_ready"] is True
    assert summary["supported_markets"] == 6
    assert summary["neural_review_candidates"] == ["market-0"]
    assert summary["ensemble_review_candidates"] == ["market-1"]
    assert summary["neural_global_promotion_authorized"] is False
    assert summary["ensemble_global_promotion_authorized"] is False
    assert summary["promotion_verdict"] == "PER_MARKET_REVIEW_CANDIDATES_SHADOW_ONLY"
