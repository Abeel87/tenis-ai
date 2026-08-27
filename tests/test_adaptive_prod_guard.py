from copy import deepcopy
from datetime import datetime, timezone

from backend.adaptive_learning_v79 import (
    MODE,
    adjust_score,
    build_cells,
    build_report,
    collect_training_rows,
    decorate_frozen_history,
    decorate_results,
)


def _row(hit, raw=0.90, n_source="ensemble_v84"):
    return {
        "source_model": n_source,
        "market": "set1_total",
        "key": "set1_total|8.5|over",
        "tour": "ATP",
        "surface": "hard",
        "band": "90-100" if raw >= 0.90 else "<55",
        "raw": raw,
        "hit": float(hit),
        "weight": 1.0,
    }


def test_production_downgrade_uses_evidence_cap():
    cases = [(5, "COLLECTING", 0.0), (6, "EARLY", 4.0), (20, "STRONG", 8.0)]
    for sample, expected_evidence, expected_cap in cases:
        cells = build_cells([_row(0) for _ in range(sample)])
        signal = {"market": "set1_total", "line": 8.5, "pick": "over", "score": 90}

        got = adjust_score(90, "ensemble_v84", signal, cells, "ATP", "hard")

        assert got["evidence"] == expected_evidence
        assert got["cap_pp"] == expected_cap
        assert abs(got["delta"]) <= expected_cap
        if expected_evidence == "COLLECTING":
            assert got["final_score"] == got["raw_score"] == 90.0
            assert got["applied"] is False
        else:
            assert -expected_cap <= got["delta"] < 0


def test_production_upgrade_is_bounded_symmetrically():
    for sample, expected_cap in ((6, 4.0), (20, 8.0)):
        cells = build_cells([_row(1, raw=0.10) for _ in range(sample)])
        signal = {"market": "set1_total", "line": 8.5, "pick": "over", "score": 10}

        got = adjust_score(10, "ensemble_v84", signal, cells, "ATP", "hard")

        assert 0 < got["delta"] <= expected_cap
        assert got["final_score"] == 10.0 + got["delta"]


def test_ensemble_post_adjustment_preserves_all_raw_models_and_shadow_payloads():
    cells = build_cells([_row(0) for _ in range(20)])
    player_shadow = {"mode": "SHADOW", "shadow_score": 87.5}
    accuracy_shadow = {"production_mode": "shadow_only", "production_changed": False}
    raw_signal = {
        "key": "set1_total|8.5|over",
        "label": "1S O8.5",
        "market": "set1_total",
        "pick": "over",
        "line": 8.5,
        "current": 88.0,
        "catboost": 91.0,
        "tabpfn": 92.0,
        "ensemble": 90.0,
        "player_intelligence_v85": player_shadow,
    }
    second_raw_signal = {
        "key": "match_total|18.5|over",
        "label": "M O18.5",
        "market": "match_total",
        "pick": "over",
        "line": 18.5,
        "current": 74.4,
        "catboost": 75.5,
        "tabpfn": None,
        "ensemble": 74.8,
    }
    match = {
        "id": 1,
        "tour": "ATP",
        "surface": "hard",
        "player_intelligence_v85": player_shadow,
        "accuracy_lab_v86": accuracy_shadow,
        "autolearn_v84": {
            "version": "v8.4B",
            "signals": [raw_signal, second_raw_signal],
            "by_key": {
                raw_signal["key"]: raw_signal,
                second_raw_signal["key"]: second_raw_signal,
            },
        },
    }
    before = deepcopy(match)

    got = decorate_results([match], cells)[0]
    by_key = got["autolearn_v84"]["by_key"]
    signal = by_key[raw_signal["key"]]

    for field in ("current", "catboost", "tabpfn", "ensemble"):
        assert signal[field] == before["autolearn_v84"]["signals"][0][field]
        assert by_key[second_raw_signal["key"]][field] == second_raw_signal[field]
    assert set(by_key) == {raw_signal["key"], second_raw_signal["key"]}
    assert len(got["autolearn_v84"]["signals"]) == 2
    assert signal["ensemble_raw"] == signal["raw_score"] == 90.0
    assert signal["final_score"] == 82.0
    assert signal["adaptive_delta_pp"] == -8.0
    assert signal["adaptive_prod_v79"]["status"] == "STRONG"
    assert signal["adaptive_prod_v79"]["cap_pp"] == 8.0
    assert by_key[raw_signal["key"]]["final_score"] == 82.0
    assert got["adaptive_learning_v79"]["mode"] == MODE == "PROD"
    assert got["player_intelligence_v85"] == before["player_intelligence_v85"]
    assert got["accuracy_lab_v86"] == before["accuracy_lab_v86"]
    assert signal["player_intelligence_v85"] == player_shadow


def test_ensemble_tracking_is_separate_from_base_official_counter():
    history = [{
        "model_version": "v7.8D-calibration-guard",
        "tour": "ATP",
        "surface": "hard",
        "signals": [{
            "market": "set1_total", "line": 8.5, "pick": "over",
            "score": 75, "result": "hit", "source_model": "adaptive",
        }],
        "autolearn_signals_v84": [{
            "market": "set1_total", "line": 8.5, "pick": "over",
            "score": 77, "result": "hit", "source_model": "ensemble_v84",
        }],
    }]

    rows = collect_training_rows(history, [])
    report = build_report(rows, build_cells(rows))

    assert {row["source_model"] for row in rows} == {"adaptive", "ensemble_v84"}
    assert report["training"]["official_effective_rows"] == 1.0
    assert report["training"]["ensemble_effective_rows"] == 1.0
    assert report["training"]["production_effective_rows"] == 1.0
    assert report["promotion_gate"]["ready"] is False
    assert report["promotion_gate"]["production_source"] == "ensemble_v84"
    assert build_report([], build_cells([]))["promotion_gate"]["ready"] is False

    fallback_rows = [_row(1, n_source="adaptive") for _ in range(6)]
    fallback_report = build_report(fallback_rows, build_cells(fallback_rows))
    assert fallback_report["promotion_gate"]["ready"] is True
    assert fallback_report["promotion_gate"]["production_source"] == "adaptive_base_fallback"


def test_pending_history_freezes_raw_and_final_once_without_future_leakage():
    early_cells = build_cells([_row(0) for _ in range(6)])
    pending = [{
        "status": "pending",
        "scheduled_time": "2026-08-27T12:00:00Z",
        "tour": "ATP",
        "surface": "hard",
        "autolearn_signals_v84": [{
            "key": "set1_total|8.5|over",
            "market": "set1_total",
            "pick": "over",
            "line": 8.5,
            "score": 90.0,
            "result": "pending",
            "source_model": "ensemble_v84",
            "model_scores": {
                "current": 88.0, "catboost": 91.0, "tabpfn": 92.0, "ensemble": 90.0,
            },
        }],
    }]

    first = decorate_frozen_history(pending, early_cells, now=datetime(2026,8,27,10,tzinfo=timezone.utc))
    frozen = first[0]["autolearn_signals_v84"][0]
    assert frozen["score"] == frozen["ensemble_raw"] == frozen["raw_score"] == 90.0
    assert frozen["final_score"] < 90.0
    assert frozen["model_scores"] == pending[0]["autolearn_signals_v84"][0]["model_scores"]

    # Even stronger future evidence may not rewrite the already frozen forecast.
    strong_cells = build_cells([_row(1) for _ in range(20)])
    second = decorate_frozen_history(first, strong_cells)
    assert second[0]["autolearn_signals_v84"][0] == frozen


def test_final_is_not_backfilled_after_start_or_settlement():
    now = datetime(2026,8,27,12,tzinfo=timezone.utc)
    for status, scheduled in (("settled", "2026-08-27T14:00:00Z"),
                              ("pending", "2026-08-27T11:00:00Z"),
                              ("pending", None)):
        history = [{"status": status, "scheduled_time": scheduled,
                    "autolearn_signals_v84": [{"market":"match_total", "pick":"over", "line":18.5,
                                                "result":"pending", "score":75}]}]
        before = deepcopy(history)
        assert decorate_frozen_history(history, {}, now=now) == before
