from __future__ import annotations

from backend.player_dna_market_backtest import binary_absolute_metrics
from backend.player_dna_market_walk_forward import (
    aggregate_format_diagnostics,
    evaluate_phase7_gate,
)


def _phase7_contract(**overrides):
    contract = {
        "brier_and_log_loss_present": True,
        "calibration_reliability_ece_present": True,
        "coverage_present": True,
        "sample_size_per_market_present": True,
        "confidence_buckets_present": True,
        "surface_tour_diagnostics_present": True,
        "bo3_bo5_diagnostics_present": True,
        "walk_forward_completed_required_folds": True,
        "chronology_contract_enforced": True,
        "promotion_thresholds_unchanged": True,
        "validation_completion_is_not_promotion": True,
    }
    contract.update(overrides)
    return contract


def _isolated_report(**extra):
    report = {
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
    }
    report.update(extra)
    return report


def test_phase7_absolute_binary_metrics_expose_calibration_coverage_and_confidence():
    metrics = binary_absolute_metrics(
        [(0.55, 1), (0.65, 1), (0.75, 0), (0.90, 1)],
        eligible_labels=5,
    )

    assert metrics["status"] == "EVALUATED"
    assert metrics["n"] == 4
    assert metrics["eligible_labels"] == 5
    assert metrics["coverage"] == 0.8
    assert metrics["brier"] is not None
    assert metrics["log_loss"] is not None
    assert metrics["ece_10_bin"] is not None
    assert metrics["calibration_bins"]
    assert len(metrics["confidence_buckets"]) == 5
    assert sum(row["n"] for row in metrics["confidence_buckets"]) == 4


def test_phase7_format_diagnostics_always_report_bo3_and_bo5_slots():
    report = aggregate_format_diagnostics([])

    assert report["mode"] == "SHADOW_FORMAT_DIAGNOSTIC_ONLY"
    assert report["production_influence"] is False
    assert report["promotion_gate"] is False
    assert report["required_formats_reported"] == ["BO3", "BO5"]
    assert set(report["formats"]) == {"BO3", "BO5"}
    assert report["formats"]["BO3"]["matched_settled_matches_total"] == 0
    assert report["formats"]["BO5"]["matched_settled_matches_total"] == 0


def test_phase7_can_close_validation_without_claiming_promotion():
    phase6 = {
        "phase6_complete": True,
        "phase7_ready": True,
    }
    backtest = _isolated_report(
        status="BACKTEST_COMPLETE_NO_PROMOTION",
        dynamic_lean_stateful_candidate={
            "signal": "DYNAMIC_LEAN_STATEFUL_E2E_PROMISING_SHADOW",
            "absolute_binary_diagnostics": {"match_p1_win": {}},
        },
    )
    walk_forward = _isolated_report(
        status="WALK_FORWARD_COMPLETE_NO_PROMOTION",
        signal="INSUFFICIENT_DYNAMIC_LEAN_MARKET_WALK_FORWARD_SAMPLE",
        summary={
            "completed_folds": 3,
            "supported_folds": 2,
            "repeatable_gain_folds": 1,
            "aggregate_matched_settled_matches": 638,
        },
        phase7_validation_contract=_phase7_contract(),
    )

    gate = evaluate_phase7_gate(backtest, walk_forward, phase6)

    assert gate["technical_validation_complete"] is True
    assert gate["phase7_complete"] is True
    assert gate["phase8_ready"] is True
    assert gate["promotion_evidence_sufficient"] is False
    assert gate["promotion_verdict"] == "EVIDENCE_INSUFFICIENT_NO_PROMOTION"
    assert gate["promotion_allowed_by_this_gate"] is False
    assert gate["production_influence"] is False
    assert gate["symphony2_influence"] is False
    assert gate["superbet_playable_influence"] is False
    assert gate["auto_promote"] is False


def test_phase7_gate_fails_closed_when_validation_contract_is_incomplete():
    phase6 = {
        "phase6_complete": True,
        "phase7_ready": True,
    }
    backtest = _isolated_report(
        status="BACKTEST_COMPLETE_NO_PROMOTION",
        dynamic_lean_stateful_candidate={
            "signal": "DYNAMIC_LEAN_STATEFUL_E2E_PROMISING_SHADOW",
            "absolute_binary_diagnostics": {"match_p1_win": {}},
        },
    )
    walk_forward = _isolated_report(
        status="WALK_FORWARD_COMPLETE_NO_PROMOTION",
        signal="DYNAMIC_LEAN_MARKET_WALK_FORWARD_ROBUST_SHADOW",
        summary={
            "completed_folds": 3,
            "supported_folds": 3,
            "repeatable_gain_folds": 2,
            "aggregate_matched_settled_matches": 700,
        },
        phase7_validation_contract=_phase7_contract(
            chronology_contract_enforced=False,
        ),
    )

    gate = evaluate_phase7_gate(backtest, walk_forward, phase6)

    assert gate["technical_validation_complete"] is False
    assert gate["phase7_complete"] is False
    assert gate["phase8_ready"] is False
    assert gate["promotion_allowed_by_this_gate"] is False
