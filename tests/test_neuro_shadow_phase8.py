from __future__ import annotations

from datetime import datetime, timezone

from backend.neuro_shadow_training import (
    PHASE8_TRACKS,
    _phase8_feature_vector,
    _phase8_fold_specs,
    evaluate_phase8_challengers,
    phase8_feature_names,
)


def _phase7_ready():
    return {
        "phase7_complete": True,
        "phase8_ready": True,
    }


def _row(match_index: int, market: str, pick_index: int, hit: bool):
    probability = 0.72 if hit else 0.28
    surface = ("hard", "clay", "grass")[match_index % 3]
    return {
        "prediction_key": f"{match_index}|{market}|{pick_index}",
        "match_id": f"m-{match_index:03d}",
        "scheduled_time": f"2026-01-{1 + match_index // 24:02d}T{match_index % 24:02d}:00:00Z",
        "surface": surface,
        "tour": "atp",
        "market": market,
        "pick": str(pick_index),
        "line": None,
        "player": None,
        "settlement": "hit" if hit else "miss",
        "mode": "SHADOW",
        "operator_playable": False,
        "feature_snapshot": {
            "numeric": {
                "state_probability": probability,
                "base_probability": 0.99 if hit else 0.01,
                "current_probability": 0.98 if hit else 0.02,
                "catboost_probability": 0.97 if hit else 0.03,
                "tabpfn_probability": 0.96 if hit else 0.04,
                "adaptive_probability": 0.95 if hit else 0.05,
                "best_of_5": 1.0 if match_index % 5 == 0 else 0.0,
                "surface_hard": 1.0 if surface == "hard" else 0.0,
                "surface_clay": 1.0 if surface == "clay" else 0.0,
                "surface_grass": 1.0 if surface == "grass" else 0.0,
            },
            "contains_final_result": False,
            "contains_bookmaker_price": False,
        },
    }


def _synthetic_history(match_count: int = 120):
    markets = ("any_set_to_nil", "match_games_parity", "set1_games_parity")
    rows = []
    for match_index in range(match_count):
        for market_index, market in enumerate(markets):
            first_hit = (match_index + market_index) % 2 == 0
            rows.append(_row(match_index, market, 0, first_hit))
            rows.append(_row(match_index, market, 1, not first_hit))
    return rows


def test_phase8_feature_contract_excludes_upstream_model_probabilities():
    names = phase8_feature_names()
    assert "state_probability" in names
    assert "state_logit" in names
    assert all(
        forbidden not in names
        for forbidden in (
            "base_probability",
            "current_probability",
            "catboost_probability",
            "tabpfn_probability",
            "adaptive_probability",
        )
    )

    item = {
        "row": _row(0, "any_set_to_nil", 0, True),
        "match_id": "m-000",
        "scheduled_time": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "market": "any_set_to_nil",
        "target": 1,
    }
    first = _phase8_feature_vector(item)
    item["row"]["feature_snapshot"]["numeric"]["catboost_probability"] = 0.01
    item["row"]["feature_snapshot"]["numeric"]["base_probability"] = 0.02
    item["row"]["price"] = 9.99
    second = _phase8_feature_vector(item)
    assert first == second


def test_phase8_fold_specs_never_split_same_timestamp_groups():
    records = []
    for index in range(80):
        timestamp = datetime(2026, 1, 1 + index // 4, 12, tzinfo=timezone.utc)
        records.append({
            "match_id": f"m-{index}",
            "scheduled_time": timestamp,
        })
    specs = _phase8_fold_specs(records)
    assert len(specs) == 3
    for spec in specs:
        assert spec["same_timestamp_split"] is False
        assert spec["train_ids"].isdisjoint(spec["eval_ids"])


def test_phase8_blocks_without_phase7_prerequisite():
    report = evaluate_phase8_challengers([], {})
    assert report["status"] == "PHASE8_BLOCKED_PHASE7_PREREQUISITE"
    assert report["phase8_complete"] is False
    assert report["phase9_ready"] is False
    assert report["promotion_allowed_by_this_gate"] is False
    assert report["nn_promotion_evidence_sufficient"] is False


def test_phase8_compares_all_tracks_on_identical_walk_forward_rows():
    report = evaluate_phase8_challengers(
        _synthetic_history(),
        _phase7_ready(),
        catboost_iterations=10,
        nn_epochs=30,
    )

    assert report["status"] == "PHASE8_CHALLENGER_EVALUATION_COMPLETE_NO_PROMOTION"
    assert report["phase8_complete"] is True
    assert report["phase9_ready"] is True
    assert report["promotion_allowed_by_this_gate"] is False
    assert report["auto_promote"] is False
    assert len(report["folds"]) == 3

    for fold in report["folds"]:
        assert fold["status"] == "FOLD_COMPLETE"
        assert fold["support_sufficient"] is True
        assert fold["same_timestamp_split"] is False
        assert set(fold["metrics"]) == set(PHASE8_TRACKS)
        assert all(
            fold["metrics"][track]["n"] == fold["eval_rows"]
            for track in PHASE8_TRACKS
        )
        assert len(fold["eval_prediction_key_fingerprint_sha256"]) == 64

    aggregate = report["aggregate"]
    assert aggregate["rows"] > 0
    assert aggregate["matches"] > 0
    assert set(aggregate["metrics"]) == set(PHASE8_TRACKS)
    assert all(
        aggregate["metrics"][track]["n"] == aggregate["rows"]
        for track in PHASE8_TRACKS
    )
    assert aggregate["best_challenger_by_brier"] in {
        "logistic_baseline",
        "catboost",
        "neural_network",
        "ensemble",
    }
    assert report["promotion_verdict"] in {
        "NN_REMAINS_SHADOW_CHALLENGER",
        "NN_EVIDENCE_READY_FOR_AUDIT_REVIEW",
    }
