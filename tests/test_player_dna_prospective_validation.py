from datetime import datetime, timedelta, timezone

import pytest

from backend.player_dna_tennis_simulator import (
    trajectory_simulator_contract,
    trajectory_simulator_contract_fingerprint,
)

from backend.player_dna_prospective_validation import (
    DURATION_MARKETS,
    SIMULATOR_SOURCE,
    _build_trajectory_evidence,
    _sha256_file,
    _ledger_integrity,
    _settle_trajectory_snapshots,
    _trajectory_evaluation,
    _trajectory_historical_benchmark,
    build_report,
    prospective_eligibility,
)


def _walk_forward():
    return {
        "mode": "SHADOW_WALK_FORWARD_AUDIT_ONLY",
        "status": "WALK_FORWARD_COMPLETE_NO_INTEGRATION",
        "signal": "HOLD_CALIBRATION_WALK_FORWARD_ROBUST_SHADOW",
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_integrate": False,
        "segment_aggregate": {
            "tour": {
                "atp": {"repeatable_duration_signal": True},
                "challenger": {"repeatable_duration_signal": True},
                "wta": {"repeatable_duration_signal": False},
            },
            "surface": {
                "hard": {"repeatable_duration_signal": True},
                "clay": {"repeatable_duration_signal": True},
                "grass": {"repeatable_duration_signal": False},
            },
        },
    }


def _sim(p=0.5):
    return {
        "mode": "SHADOW_SIMULATION_ONLY",
        "first_set": {
            "tiebreak": p,
            "over": {
                "8.5": p,
                "9.5": p,
                "10.5": p,
            },
        },
    }


def _candidate(p=0.45):
    row = _sim(p)
    row.update({
        "mode": "SHADOW_HOLD_CALIBRATED_CANDIDATE",
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
    })
    return row


def _current_row(match_id="1", tour="atp", surface="hard", scheduled=None):
    scheduled = scheduled or (datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc))
    return {
        "match_id": match_id,
        "scheduled_time": scheduled.isoformat(),
        "tour": tour,
        "surface": surface,
        "p1": "A",
        "p2": "B",
        "simulation": _sim(0.55),
        "hold_calibrated_candidate": _candidate(0.50),
        "source_model_fingerprint_sha256": "abc",
    }


def _settled_snapshot(match_id, tour="atp", surface="hard"):
    actual = {market: True for market in DURATION_MARKETS}
    raw = {market: 0.60 for market in DURATION_MARKETS}
    calibrated = {market: 0.90 for market in DURATION_MARKETS}
    return {
        "match_id": str(match_id),
        "scheduled_time": "2026-09-04T10:00:00+00:00",
        "captured_at": "2026-09-04T09:00:00+00:00",
        "captured_pre_match": True,
        "tour": tour,
        "surface": surface,
        "p1": f"A{match_id}",
        "p2": f"B{match_id}",
        "source_model_fingerprint_sha256": "abc",
        "raw_probabilities": raw,
        "calibrated_probabilities": calibrated,
        "settled": True,
        "actual": actual,
        "settled_at": "2026-09-04T12:00:00+00:00",
    }


def _point_rows_for_settled(match_id="1"):
    # _labels_by_match reconstructs from a final BO3 score plus early tape.
    return [
        {
            "match_id": match_id,
            "event_index": 1,
            "match_format": "BO3",
            "score_after": {"sets": [0, 0], "games": [[1], [1]]},
        },
        {
            "match_id": match_id,
            "event_index": 2,
            "match_format": "BO3",
            "score_after": {"sets": [2, 0], "games": [[6, 6], [4, 3]]},
        },
    ]


def test_eligibility_requires_repeatable_tour_and_surface():
    wf = _walk_forward()
    assert prospective_eligibility({"tour": "ATP", "surface": "HARD"}, wf)["eligible"] is True
    assert prospective_eligibility({"tour": "WTA", "surface": "hard"}, wf)["eligible"] is False
    assert prospective_eligibility({"tour": "atp", "surface": "grass"}, wf)["eligible"] is False


def test_snapshot_is_only_created_before_match_and_before_result_exists():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    future = _current_row(scheduled=now + timedelta(hours=1))
    report = build_report(
        {"version": "sim", "matches": [future]},
        _walk_forward(),
        [],
        {},
        now=now,
    )
    assert report["counts"]["snapshots"] == 1
    snap = report["snapshots"][0]
    assert snap["captured_pre_match"] is True
    assert snap["settled"] is False

    too_late = _current_row(match_id="2", scheduled=now + timedelta(minutes=2))
    report_late = build_report(
        {"version": "sim", "matches": [too_late]},
        _walk_forward(),
        [],
        {},
        now=now,
    )
    assert report_late["counts"]["snapshots"] == 0

    already_settled = _current_row(match_id="3", scheduled=now + timedelta(hours=1))
    report_settled = build_report(
        {"version": "sim", "matches": [already_settled]},
        _walk_forward(),
        _point_rows_for_settled("3"),
        {},
        now=now,
    )
    assert report_settled["counts"]["snapshots"] == 0


def test_existing_snapshot_settles_later_without_rewriting_prediction():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    first = build_report(
        {"version": "sim", "matches": [_current_row(scheduled=now + timedelta(hours=1))]},
        _walk_forward(),
        [],
        {},
        now=now,
    )
    original_raw = dict(first["snapshots"][0]["raw_probabilities"])
    second = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        _point_rows_for_settled("1"),
        first,
        now=now + timedelta(hours=3),
    )
    assert second["counts"]["settled_snapshots"] == 1
    assert second["snapshots"][0]["raw_probabilities"] == original_raw
    assert second["snapshots"][0]["actual"]["first_set_over_8.5"] is True
    assert second["snapshots"][0]["actual"]["first_set_over_10.5"] is False
    assert second["production_influence"] is False
    assert second["symphony2_influence"] is False
    assert second["superbet_playable_influence"] is False
    assert second["auto_integrate"] is False
    integrity = second["ledger_integrity"]
    assert integrity["status"] == "LEDGER_INTEGRITY_OK"
    assert integrity["previous_snapshot_count"] == 1
    assert integrity["preserved_snapshots"] == 1
    assert integrity["new_snapshots"] == 0
    assert integrity["newly_settled"] == 1
    assert integrity["rewritten_predictions"] == 0
    assert integrity["settlement_regressions"] == 0
    assert integrity["settled_actual_rewrites"] == 0
    assert integrity["settled_at_rewrites"] == 0
    assert second["snapshots"][0]["settled_at"] == (now + timedelta(hours=3)).isoformat()
    latency = second["settlement_observability"]["settlement_latency"]
    assert latency["n"] == 1
    assert latency["median_hours"] == 2.0
    assert latency["p90_hours"] == 2.0
    assert latency["max_hours"] == 2.0
    assert latency["negative_latency_count"] == 0


def test_unsettled_observability_exposes_age_without_guessing_cancellation():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    first = build_report(
        {"version": "sim", "matches": [_current_row("1", scheduled=now + timedelta(hours=1))]},
        _walk_forward(),
        [],
        {},
        now=now,
    )
    later = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        first,
        now=now + timedelta(hours=8),
    )
    unsettled = later["settlement_observability"]["unsettled"]
    assert unsettled["buckets"]["overdue_6_24h"] == 1
    assert unsettled["buckets"]["upcoming"] == 0
    assert "does not imply cancellation" in unsettled["meaning"]
    assert unsettled["overdue_samples"][0]["match_id"] == "1"
    assert unsettled["overdue_samples"][0]["hours_since_scheduled"] == 7.0


def test_schedule_drift_is_reported_without_rewriting_frozen_schedule():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    original_schedule = now + timedelta(hours=2)
    first = build_report(
        {"version": "sim", "matches": [_current_row("1", scheduled=original_schedule)]},
        _walk_forward(),
        [],
        {},
        now=now,
    )
    shifted_schedule = original_schedule + timedelta(minutes=45)
    second = build_report(
        {"version": "sim", "matches": [_current_row("1", scheduled=shifted_schedule)]},
        _walk_forward(),
        [],
        first,
        now=now + timedelta(minutes=10),
    )
    drift = second["settlement_observability"]["schedule_drift"]
    assert drift["count"] == 1
    assert drift["samples"][0]["match_id"] == "1"
    assert drift["samples"][0]["drift_minutes"] == 45.0
    assert second["snapshots"][0]["scheduled_time"] == original_schedule.isoformat()
    assert second["ledger_integrity"]["rewritten_predictions"] == 0


def test_ledger_grows_without_dropping_previous_snapshot():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    first = build_report(
        {"version": "sim", "matches": [_current_row("1", scheduled=now + timedelta(hours=2))]},
        _walk_forward(),
        [],
        {},
        now=now,
    )
    second = build_report(
        {
            "version": "sim",
            "matches": [
                _current_row("1", scheduled=now + timedelta(hours=2)),
                _current_row("2", scheduled=now + timedelta(hours=3)),
            ],
        },
        _walk_forward(),
        [],
        first,
        now=now + timedelta(minutes=5),
    )
    integrity = second["ledger_integrity"]
    assert integrity["status"] == "LEDGER_INTEGRITY_OK"
    assert integrity["previous_snapshot_count"] == 1
    assert integrity["current_snapshot_count_before_retention"] == 2
    assert integrity["current_snapshot_count_after_retention"] == 2
    assert integrity["preserved_snapshots"] == 1
    assert integrity["new_snapshots"] == 1
    assert integrity["missing_previous_snapshots"] == 0
    assert integrity["pruned_by_retention"] == 0


def test_ledger_integrity_detects_prediction_rewrite_and_settlement_regression():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    report = build_report(
        {"version": "sim", "matches": [_current_row("1", scheduled=now + timedelta(hours=2))]},
        _walk_forward(),
        [],
        {},
        now=now,
    )
    old = dict(report["snapshots"][0])
    old["settled"] = True
    old["actual"] = {market: False for market in DURATION_MARKETS}

    new = dict(old)
    new["raw_probabilities"] = dict(old["raw_probabilities"])
    new["raw_probabilities"]["first_set_over_8.5"] = 0.99
    new["settled"] = False
    new["actual"] = None

    integrity = _ledger_integrity([old], [new])
    assert integrity["status"] == "LEDGER_INTEGRITY_VIOLATION"
    assert integrity["rewritten_predictions"] == 1
    assert integrity["settlement_regressions"] == 1


def test_duplicate_previous_snapshot_fails_closed():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    first = build_report(
        {"version": "sim", "matches": [_current_row("1", scheduled=now + timedelta(hours=2))]},
        _walk_forward(),
        [],
        {},
        now=now,
    )
    corrupted_previous = dict(first)
    corrupted_previous["snapshots"] = [first["snapshots"][0], dict(first["snapshots"][0])]

    with pytest.raises(RuntimeError, match="ledger integrity violation"):
        build_report(
            {"version": "sim", "matches": []},
            _walk_forward(),
            [],
            corrupted_previous,
            now=now + timedelta(minutes=10),
        )


def test_performance_verdict_waits_for_every_supported_segment_minimum():
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        *[_settled_snapshot(i, "atp", "hard") for i in range(1, 122)],
        *[_settled_snapshot(i, "challenger", "clay") for i in range(122, 151)],
    ]
    report = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {"snapshots": snapshots},
        now=now,
    )

    readiness = report["evidence_readiness"]
    assert readiness["overall"]["settled"] == 150
    assert readiness["overall"]["support_sufficient"] is True
    assert readiness["segments"]["tour"]["challenger"]["settled"] == 29
    assert readiness["segments"]["tour"]["challenger"]["remaining"] == 1
    assert readiness["segments"]["surface"]["clay"]["settled"] == 29
    assert readiness["segment_support_ready"] is False
    assert readiness["ready_for_performance_verdict"] is False
    assert report["signal"] == "COLLECTING_PROSPECTIVE_EVIDENCE"


def test_performance_verdict_unlocks_only_after_overall_and_segment_support():
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        *[_settled_snapshot(i, "atp", "hard") for i in range(1, 122)],
        *[_settled_snapshot(i, "challenger", "clay") for i in range(122, 152)],
    ]
    report = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {"snapshots": snapshots},
        now=now,
    )

    readiness = report["evidence_readiness"]
    assert readiness["overall"]["settled"] == 151
    assert readiness["segments"]["tour"]["challenger"]["settled"] == 30
    assert readiness["segments"]["surface"]["clay"]["settled"] == 30
    assert readiness["segment_support_ready"] is True
    assert readiness["ready_for_performance_verdict"] is True
    assert all(row["support_sufficient"] is True for row in readiness["markets"].values())
    assert report["evaluation"]["duration_markets_improved"] == 4
    assert report["signal"] == "PROSPECTIVE_DURATION_ROBUST_SHADOW"


def test_duration_market_scope_is_exact_and_candidate_only():
    assert DURATION_MARKETS == (
        "first_set_tiebreak",
        "first_set_over_8.5",
        "first_set_over_9.5",
        "first_set_over_10.5",
    )


DYNAMIC_POLICY_SOURCE_FP = "a" * 64
DYNAMIC_POLICY_CONTRACT_FP = "c" * 64
DYNAMIC_POLICY_CONTRACT_ID = "strict-marginal-agreement-mean-direction-v1"


def _dynamic_current(match_id="dyn-1", scheduled=None, decision="CONSENSUS_DYNAMIC_CANDIDATE"):
    scheduled = scheduled or datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    markets = {
        market: {
            "decision": "INSUFFICIENT_OR_MIXED",
            "profile_reference_probability": 0.50,
            "dynamic_candidate_probability": 0.50,
            "production_influence": False,
        }
        for market in (
            "match_p1_win",
            "first_set_p1_win",
            "first_set_tiebreak",
            "first_set_over_8.5",
            "first_set_over_9.5",
            "first_set_over_10.5",
            "first_set_over_11.5",
            "first_set_over_12.5",
            "early_1:1",
            "early_2:2",
            "early_3:3",
        )
    }
    markets["match_p1_win"] = {
        "decision": decision,
        "profile_reference_probability": 0.55,
        "dynamic_candidate_probability": 0.65,
        "production_influence": False,
    }
    markets["first_set_p1_win"] = {
        "decision": "CONFLICT",
        "profile_reference_probability": 0.58,
        "dynamic_candidate_probability": 0.62,
        "production_influence": False,
    }
    return {
        "version": "player-dna-current-dynamic-shadow-v1",
        "mode": "SHADOW_CURRENT_DYNAMIC_LEAN_ONLY",
        "production_influence": False,
        "runtime_switch_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "candidate_only": True,
        "prospective_validation_required": True,
        "market_policy_source": "segment_consensus_shadow_policy",
        "market_policy_source_path": "backend/player_dna_market_walk_forward.py",
        "market_policy_source_fingerprint_sha256": DYNAMIC_POLICY_SOURCE_FP,
        "market_policy_contract_id": DYNAMIC_POLICY_CONTRACT_ID,
        "market_policy_contract_fingerprint_sha256": DYNAMIC_POLICY_CONTRACT_FP,
        "market_policy_provenance_required_for_prospective_verdict": True,
        "matches": [{
            "match_id": match_id,
            "scheduled_time": scheduled.isoformat(),
            "tour": "challenger",
            "surface": "hard",
            "p1": "A",
            "p2": "B",
            "status": "DYNAMIC_SHADOW_SCORED",
            "production_influence": False,
            "runtime_switch_enabled": False,
            "model_fingerprint_sha256": "lean-fingerprint",
            "market_segment_key": "challenger|hard",
            "markets": markets,
        }],
    }


def test_dynamic_lean_prospective_ledger_freezes_only_consensus_candidate_markets_and_settles_later():
    now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
    first = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {},
        current_dynamic=_dynamic_current(scheduled=now + timedelta(hours=2)),
        now=now,
    )

    dynamic_evidence = first["dynamic_lean_evidence"]
    assert dynamic_evidence["mode"] == "SHADOW_DYNAMIC_LEAN_PROSPECTIVE_LEDGER_ONLY"
    assert dynamic_evidence["signal"] == "COLLECTING_DYNAMIC_LEAN_PROSPECTIVE_EVIDENCE"
    assert dynamic_evidence["production_influence"] is False
    assert dynamic_evidence["runtime_switch_enabled"] is False
    assert dynamic_evidence["auto_integrate"] is False
    assert dynamic_evidence["performance_verdict_emitted"] is False
    assert dynamic_evidence["counts"]["snapshots"] == 1

    snapshot = dynamic_evidence["snapshots"][0]
    assert snapshot["captured_pre_match"] is True
    assert snapshot["market_policy_source_fingerprint_sha256"] == DYNAMIC_POLICY_SOURCE_FP
    assert snapshot["market_policy_contract_id"] == DYNAMIC_POLICY_CONTRACT_ID
    assert snapshot["market_policy_contract_fingerprint_sha256"] == DYNAMIC_POLICY_CONTRACT_FP
    assert set(snapshot["candidate_markets"]) == {"match_p1_win"}
    assert snapshot["candidate_markets"]["match_p1_win"]["profile_reference_probability"] == 0.55
    assert snapshot["candidate_markets"]["match_p1_win"]["dynamic_candidate_probability"] == 0.65
    assert "first_set_p1_win" not in snapshot["candidate_markets"]

    second = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        _point_rows_for_settled("dyn-1"),
        first,
        current_dynamic={
            **_dynamic_current(
                match_id="dyn-settled-contract",
                scheduled=now - timedelta(hours=1),
            ),
            "matches": [],
        },
        now=now + timedelta(hours=4),
    )
    dynamic_second = second["dynamic_lean_evidence"]
    assert dynamic_second["ledger_integrity"]["status"] == "LEDGER_INTEGRITY_OK"
    assert dynamic_second["ledger_integrity"]["newly_settled"] == 1
    assert dynamic_second["ledger_integrity"]["rewritten_predictions"] == 0
    assert dynamic_second["counts"]["settled_snapshots"] == 1
    assert dynamic_second["counts"]["settled_market_observations"] == 1
    assert dynamic_second["snapshots"][0]["actual"]["match_p1_win"] is True

    metrics = dynamic_second["evaluation"]["markets"]["match_p1_win"]
    assert metrics["n"] == 1
    assert metrics["profile_reference_brier"] is not None
    assert metrics["dynamic_candidate_brier"] is not None
    assert metrics["brier_gain_dynamic_vs_profile"] is not None
    assert metrics["log_loss_gain_dynamic_vs_profile"] is not None


def test_dynamic_lean_prospective_ledger_excludes_conflict_and_non_candidate_markets():
    now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
    current_dynamic = _dynamic_current(
        match_id="dyn-conflict",
        scheduled=now + timedelta(hours=2),
        decision="CONFLICT",
    )
    report = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {},
        current_dynamic=current_dynamic,
        now=now,
    )
    dynamic_evidence = report["dynamic_lean_evidence"]
    assert dynamic_evidence["counts"]["snapshots"] == 0
    assert dynamic_evidence["counts"]["current_rows_with_dynamic_candidates"] == 0
    assert dynamic_evidence["eligibility_policy"]["conflict_excluded"] is True
    assert dynamic_evidence["eligibility_policy"]["insufficient_excluded"] is True
    assert dynamic_evidence["eligibility_policy"]["profile_reference_excluded"] is True


def test_dynamic_readiness_requires_support_for_candidate_market_seen_before_settlement():
    now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
    report = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {},
        current_dynamic=_dynamic_current(scheduled=now + timedelta(hours=2)),
        now=now,
    )

    dynamic_evidence = report["dynamic_lean_evidence"]
    evaluation = dynamic_evidence["evaluation"]
    readiness = dynamic_evidence["evidence_readiness"]
    assert evaluation["candidate_markets_seen"] == ["match_p1_win"]
    assert evaluation["markets_with_observations"] == []
    market = readiness["observed_candidate_markets"]["match_p1_win"]
    assert market["settled"] == 0
    assert market["required"] == 30
    assert market["remaining"] == 30
    assert market["support_sufficient"] is False
    assert readiness["ready_for_performance_verdict"] is False



def _dynamic_settled_snapshot(
    match_id,
    segment="challenger|hard",
    *,
    market="match_p1_win",
    actual=True,
    profile_probability=0.55,
    dynamic_probability=0.75,
    policy_fingerprint=DYNAMIC_POLICY_CONTRACT_FP,
):
    tour, surface = segment.split("|", 1)
    return {
        "match_id": str(match_id),
        "scheduled_time": "2026-09-06T10:00:00+00:00",
        "captured_at": "2026-09-06T09:00:00+00:00",
        "captured_pre_match": True,
        "tour": tour,
        "surface": surface,
        "p1": f"A{match_id}",
        "p2": f"B{match_id}",
        "source_model_fingerprint_sha256": "lean-fingerprint",
        "market_policy_source_fingerprint_sha256": DYNAMIC_POLICY_SOURCE_FP,
        "market_policy_contract_id": DYNAMIC_POLICY_CONTRACT_ID,
        "market_policy_contract_fingerprint_sha256": policy_fingerprint,
        "market_segment_key": segment,
        "candidate_markets": {
            market: {
                "profile_reference_probability": profile_probability,
                "dynamic_candidate_probability": dynamic_probability,
            }
        },
        "settled": True,
        "actual": {market: bool(actual)},
        "settled_at": "2026-09-06T13:00:00+00:00",
    }


def test_dynamic_performance_verdict_waits_for_direct_tour_surface_market_support():
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        *[
            _dynamic_settled_snapshot(i, "challenger|hard")
            for i in range(1, 122)
        ],
        *[
            _dynamic_settled_snapshot(i, "challenger|clay")
            for i in range(122, 151)
        ],
    ]
    report = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {"dynamic_lean_evidence": {"snapshots": snapshots}},
        current_dynamic={
            **_dynamic_current(
                match_id="dyn-contract-only",
                scheduled=now - timedelta(hours=1),
            ),
            "matches": [],
        },
        now=now,
    )

    dynamic = report["dynamic_lean_evidence"]
    assert dynamic["evidence_readiness"]["ready_for_performance_verdict"] is True
    direct = dynamic["direct_segment_readiness"]
    assert direct["ready_for_performance_verdict"] is False
    assert direct["tour_surface"]["challenger|hard"]["candidate_markets"][
        "match_p1_win"
    ]["support_sufficient"] is True
    clay = direct["tour_surface"]["challenger|clay"]["candidate_markets"][
        "match_p1_win"
    ]
    assert clay["settled"] == 29
    assert clay["required"] == 30
    assert clay["support_sufficient"] is False

    verdict = dynamic["performance_verdict"]
    assert verdict["emitted"] is False
    assert verdict["signal"] == "DYNAMIC_LEAN_PROSPECTIVE_VERDICT_NOT_READY"
    assert verdict["reason"] == "DIRECT_TOUR_SURFACE_SUPPORT_INSUFFICIENT"
    assert dynamic["performance_verdict_emitted"] is False


def test_dynamic_performance_verdict_emits_robust_only_after_global_and_direct_joint_gain():
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        *[
            _dynamic_settled_snapshot(i, "challenger|hard")
            for i in range(1, 121)
        ],
        *[
            _dynamic_settled_snapshot(i, "challenger|clay")
            for i in range(121, 151)
        ],
    ]
    report = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {"dynamic_lean_evidence": {"snapshots": snapshots}},
        current_dynamic={
            **_dynamic_current(
                match_id="dyn-contract-only",
                scheduled=now - timedelta(hours=1),
            ),
            "matches": [],
        },
        now=now,
    )

    dynamic = report["dynamic_lean_evidence"]
    assert dynamic["signal"] == "DYNAMIC_LEAN_PROSPECTIVE_EVIDENCE_READY_SHADOW"
    assert dynamic["evidence_readiness"]["ready_for_performance_verdict"] is True
    assert dynamic["direct_segment_readiness"]["ready_for_performance_verdict"] is True

    verdict = dynamic["performance_verdict"]
    assert verdict["emitted"] is True
    assert verdict["signal"] == "DYNAMIC_LEAN_PROSPECTIVE_ROBUST_SHADOW"
    assert verdict["reason"] == "GLOBAL_AND_DIRECT_TOUR_SURFACE_GAIN_CONFIRMED"
    assert verdict[
        "all_observed_candidate_markets_better_on_brier_and_log_loss"
    ] is True
    assert verdict[
        "all_direct_tour_surface_market_cells_better_on_brier_and_log_loss"
    ] is True
    assert verdict["production_influence"] is False
    assert verdict["runtime_switch_enabled"] is False
    assert verdict["symphony2_influence"] is False
    assert verdict["superbet_playable_influence"] is False
    assert verdict["auto_promote"] is False
    assert verdict["promotion_gate"] is False
    assert dynamic["performance_verdict_emitted"] is True


def test_dynamic_performance_verdict_is_not_proven_when_supported_joint_segment_loses():
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        *[
            _dynamic_settled_snapshot(i, "challenger|hard")
            for i in range(1, 121)
        ],
        *[
            _dynamic_settled_snapshot(
                i,
                "challenger|clay",
                profile_probability=0.90,
                dynamic_probability=0.60,
            )
            for i in range(121, 151)
        ],
    ]
    report = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {"dynamic_lean_evidence": {"snapshots": snapshots}},
        current_dynamic={
            **_dynamic_current(
                match_id="dyn-contract-only",
                scheduled=now - timedelta(hours=1),
            ),
            "matches": [],
        },
        now=now,
    )

    dynamic = report["dynamic_lean_evidence"]
    assert dynamic["evidence_readiness"]["ready_for_performance_verdict"] is True
    assert dynamic["direct_segment_readiness"]["ready_for_performance_verdict"] is True

    verdict = dynamic["performance_verdict"]
    assert verdict["emitted"] is True
    assert verdict["signal"] == "DYNAMIC_LEAN_PROSPECTIVE_NOT_PROVEN"
    assert verdict["reason"] == "ONE_OR_MORE_SUPPORTED_MARKETS_FAILED_BOTH_METRICS"
    assert verdict[
        "all_observed_candidate_markets_better_on_brier_and_log_loss"
    ] is True
    assert verdict[
        "all_direct_tour_surface_market_cells_better_on_brier_and_log_loss"
    ] is False
    assert verdict["tour_surface_failures"][0]["segment"] == "challenger|clay"
    assert verdict["tour_surface_failures"][0]["market"] == "match_p1_win"



def _trajectory_simulation_row(match_id="traj-1", scheduled=None):
    scheduled = scheduled or datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)

    def branch():
        return {
            "first_set_top_game_paths": [
                {
                    "progression": ["1:0", "1:1", "2:1", "2:2", "3:2", "4:2", "5:2", "6:2"],
                    "final_score": "6:2",
                    "probability": 0.20,
                },
                {
                    "progression": ["1:0", "1:1", "2:1", "2:2", "3:2", "3:3", "4:3", "5:3", "6:3"],
                    "final_score": "6:3",
                    "probability": 0.15,
                },
            ],
            "match_top_set_paths": [
                {"set_scores": ["6:2", "6:3"], "probability": 0.22},
                {"set_scores": ["6:3", "4:6", "6:4"], "probability": 0.12},
            ],
            "match_storylines": [
                {"match_score": "2:0", "probability": 0.60},
                {"match_score": "2:1", "probability": 0.25},
                {"match_score": "1:2", "probability": 0.10},
            ],
            "full_match_top_game_paths": [
                {
                    "sets": [
                        {"progression": ["1:0", "1:1", "2:1", "2:2", "3:2", "4:2", "5:2", "6:2"]},
                        {"progression": ["1:0", "1:1", "2:1", "2:2", "3:2", "3:3", "4:3", "5:3", "6:3"]},
                    ],
                    "probability": 0.05,
                },
                {
                    "sets": [
                        {"progression": ["1:0", "1:1", "2:1", "2:2", "3:2", "3:3", "4:3", "5:3", "6:3"]},
                        {"progression": ["1:0", "1:1", "2:1", "2:2", "3:2", "4:2", "5:2", "6:2"]},
                    ],
                    "probability": 0.04,
                },
            ],
        }

    simulation = {
        "mode": "SHADOW_SIMULATION_ONLY",
        "validation_status": "UNVALIDATED_MATCH_LEVEL",
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "trajectory": {
            "status": "SHADOW_TRAJECTORY_FOUNDATION",
            "validation_status": "UNVALIDATED_MATCH_LEVEL",
            "checkpoints_neutral_start_server": {
                "after_2_games": [
                    {"score": "1:1", "probability": 0.70},
                    {"score": "2:0", "probability": 0.20},
                    {"score": "0:2", "probability": 0.10},
                ],
                "after_4_games": [
                    {"score": "2:2", "probability": 0.60},
                    {"score": "3:1", "probability": 0.25},
                    {"score": "1:3", "probability": 0.15},
                ],
                "after_6_games": [
                    {"score": "3:3", "probability": 0.50},
                    {"score": "4:2", "probability": 0.30},
                    {"score": "2:4", "probability": 0.20},
                ],
            },
            "serve_order_conditioned": {
                "p1_serves_first": branch(),
                "p2_serves_first": branch(),
            },
            "contract": {
                "production_influence": False,
                "symphony2_influence": False,
                "superbet_playable_influence": False,
            },
        },
    }
    return {
        "version": "player-dna-current-simulation-v1",
        "mode": "SHADOW_SIMULATION_ONLY",
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "match_level_validation_required": True,
        "auto_promote": False,
        "matches": [{
            "match_id": match_id,
            "scheduled_time": scheduled.isoformat(),
            "tour": "challenger",
            "surface": "hard",
            "p1": "A",
            "p2": "B",
            "source_model_fingerprint_sha256": "trajectory-fingerprint",
            "production_influence": False,
            "validation_status": "UNVALIDATED_MATCH_LEVEL",
            "simulation": simulation,
        }],
    }


def _trajectory_actual():
    first_set = ["1:0", "1:1", "2:1", "2:2", "3:2", "4:2", "5:2", "6:2"]
    second_set = ["1:0", "1:1", "2:1", "2:2", "3:2", "3:3", "4:3", "5:3", "6:3"]
    return {
        "first_server": 1,
        "checkpoint_scores": {"2": "1:1", "4": "2:2", "6": "4:2"},
        "first_set_progression": first_set,
        "set_score_sequence": ["6:2", "6:3"],
        "set_progressions": [first_set, second_set],
        "full_match_progression_complete": True,
    }


def test_trajectory_prospective_ledger_freezes_pre_match_ranked_paths_without_claiming_validation():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    current = _trajectory_simulation_row(scheduled=now + timedelta(hours=2))
    report = build_report(
        current,
        _walk_forward(),
        [],
        {},
        current_dynamic={
            **_dynamic_current(
                match_id="dyn-contract-only",
                scheduled=now - timedelta(hours=1),
            ),
            "matches": [],
        },
        now=now,
    )

    trajectory = report["trajectory_evidence"]
    assert trajectory["mode"] == "SHADOW_TRAJECTORY_PROSPECTIVE_LEDGER_ONLY"
    assert trajectory["status"] == "TRAJECTORY_PROSPECTIVE_COLLECTION_ACTIVE"
    assert trajectory["signal"] == "COLLECTING_TRAJECTORY_PROSPECTIVE_EVIDENCE"
    assert trajectory["production_influence"] is False
    assert trajectory["runtime_switch_enabled"] is False
    assert trajectory["symphony2_influence"] is False
    assert trajectory["superbet_playable_influence"] is False
    assert trajectory["auto_integrate"] is False
    assert trajectory["performance_verdict_emitted"] is False
    assert trajectory["validation_scope"]["no_trajectory_performance_threshold_invented_yet"] is True
    assert trajectory["counts"]["snapshots"] == 1
    assert trajectory["counts"]["settled_snapshots"] == 0

    snapshot = trajectory["snapshots"][0]
    assert snapshot["captured_pre_match"] is True
    predictions = snapshot["trajectory_predictions"]
    assert predictions["checkpoints_neutral_start_server"]["after_2_games"][0]["score"] == "1:1"
    assert predictions["serve_order_conditioned"]["p1_serves_first"]["match_storylines"][0]["match_score"] == "2:0"


def test_trajectory_prospective_settlement_and_metrics_use_observed_first_server_only_after_match():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    current = _trajectory_simulation_row(scheduled=now + timedelta(hours=2))
    first = _build_trajectory_evidence(current, {}, {}, now)
    snapshots = [dict(row) for row in first["snapshots"]]

    labels = {
        "traj-1": {
            "match_exact_score": "2:0",
            "trajectory_actual": _trajectory_actual(),
        }
    }
    _settle_trajectory_snapshots(snapshots, labels, now + timedelta(hours=5))
    evaluation = _trajectory_evaluation(snapshots)

    assert snapshots[0]["settled"] is True
    assert snapshots[0]["actual"]["first_server"] == 1
    assert evaluation["settled_matches"] == 1
    assert evaluation["checkpoint_neutral_start_server"]["after_2_games"]["top1"] == 1.0
    assert evaluation["checkpoint_neutral_start_server"]["after_4_games"]["top1"] == 1.0
    assert evaluation["checkpoint_neutral_start_server"]["after_6_games"]["top1"] == 0.0
    assert evaluation["checkpoint_neutral_start_server"]["after_6_games"]["top3"] == 1.0
    storyline = evaluation[
        "primary_storyline_match_score_conditioned_on_observed_first_server"
    ]
    assert storyline["top1"] == 1.0
    first_set = evaluation[
        "first_set_complete_path_conditioned_on_observed_first_server"
    ]
    assert first_set["top1"] == 1.0
    match_sets = evaluation[
        "match_set_sequence_conditioned_on_observed_first_server"
    ]
    assert match_sets["top1"] == 1.0
    full_match = evaluation[
        "full_match_game_path_conditioned_on_observed_first_server"
    ]
    assert full_match["top1"] == 1.0
    assert full_match["mean_best_prefix_fraction_top4"] == 1.0


def test_trajectory_prospective_ledger_never_rewrites_frozen_prediction():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    first_current = _trajectory_simulation_row(scheduled=now + timedelta(hours=2))
    first = _build_trajectory_evidence(first_current, {}, {}, now)
    original = first["snapshots"][0]["trajectory_predictions"]

    changed_current = _trajectory_simulation_row(scheduled=now + timedelta(hours=2))
    changed_current["matches"][0]["simulation"]["trajectory"][
        "checkpoints_neutral_start_server"
    ]["after_2_games"][0]["score"] = "2:0"

    second = _build_trajectory_evidence(
        changed_current,
        {},
        {"trajectory_evidence": first},
        now + timedelta(minutes=10),
    )
    assert second["ledger_integrity"]["status"] == "LEDGER_INTEGRITY_OK"
    assert second["ledger_integrity"]["rewritten_predictions"] == 0
    assert second["snapshots"][0]["trajectory_predictions"] == original



def test_trajectory_segment_diagnostics_keep_direct_tour_surface_separate_from_marginals():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    first = _trajectory_simulation_row(
        match_id="traj-hard",
        scheduled=now + timedelta(hours=2),
    )
    second = _trajectory_simulation_row(
        match_id="traj-clay",
        scheduled=now + timedelta(hours=2),
    )
    second["matches"][0]["surface"] = "clay"
    first["matches"].extend(second["matches"])

    initial = _build_trajectory_evidence(first, {}, {}, now)
    snapshots = [dict(row) for row in initial["snapshots"]]
    labels = {
        "traj-hard": {
            "match_exact_score": "2:0",
            "trajectory_actual": _trajectory_actual(),
        },
        "traj-clay": {
            "match_exact_score": "2:0",
            "trajectory_actual": _trajectory_actual(),
        },
    }
    _settle_trajectory_snapshots(
        snapshots,
        labels,
        now + timedelta(hours=5),
    )

    report = _build_trajectory_evidence(
        {"mode": "SHADOW_SIMULATION_ONLY", "matches": []},
        labels,
        {"trajectory_evidence": {"snapshots": snapshots}},
        now + timedelta(hours=6),
    )
    diagnostics = report["segment_diagnostics"]

    assert diagnostics["tour"]["challenger"]["settled"] == 2
    assert diagnostics["surface"]["hard"]["settled"] == 1
    assert diagnostics["surface"]["clay"]["settled"] == 1
    assert diagnostics["tour_surface"]["challenger|hard"]["settled"] == 1
    assert diagnostics["tour_surface"]["challenger|clay"]["settled"] == 1
    assert diagnostics["coverage"]["tour_surface_segments_seen"] == 2
    assert diagnostics["coverage"]["tour_surface_segments_with_settled"] == 2

    policy = diagnostics["policy"]
    assert policy["diagnostic_only"] is True
    assert policy[
        "direct_tour_surface_rows_are_built_from_same_match_snapshots"
    ] is True
    assert policy[
        "marginal_tour_and_surface_results_never_imply_joint_validation"
    ] is True
    assert policy["minimum_segment_sample_not_defined_yet"] is True
    assert policy["performance_verdict_forbidden"] is True


def test_trajectory_segment_diagnostics_do_not_invent_sample_threshold_or_verdict():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    current = _trajectory_simulation_row(
        match_id="traj-one",
        scheduled=now + timedelta(hours=2),
    )
    evidence = _build_trajectory_evidence(current, {}, {}, now)

    diagnostics = evidence["segment_diagnostics"]
    assert diagnostics["tour"]["challenger"]["snapshots"] == 1
    assert diagnostics["tour"]["challenger"]["settled"] == 0
    assert diagnostics["surface"]["hard"]["snapshots"] == 1
    assert diagnostics["tour_surface"]["challenger|hard"]["snapshots"] == 1
    assert evidence["performance_verdict_emitted"] is False
    assert evidence["validation_scope"][
        "no_trajectory_performance_threshold_invented_yet"
    ] is True



def test_trajectory_settlement_observability_distinguishes_upcoming_from_overdue_and_reports_latency():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    current = _trajectory_simulation_row(
        match_id="traj-health",
        scheduled=now + timedelta(hours=2),
    )
    first = _build_trajectory_evidence(current, {}, {}, now)
    observability = first["settlement_observability"]

    assert observability["unsettled"]["buckets"]["upcoming"] == 1
    assert observability["unsettled"]["buckets"]["due_within_6h"] == 0
    assert observability["unsettled"]["buckets"]["overdue_gt_72h"] == 0
    assert observability["settlement_latency"]["n"] == 0
    assert observability["schedule_drift"]["count"] == 0

    labels = {
        "traj-health": {
            "match_exact_score": "2:0",
            "trajectory_actual": _trajectory_actual(),
        }
    }
    settled = _build_trajectory_evidence(
        {},
        labels,
        {"trajectory_evidence": first},
        now + timedelta(hours=5),
    )
    settled_obs = settled["settlement_observability"]
    assert settled["counts"]["settled_snapshots"] == 1
    assert settled_obs["unsettled"]["buckets"]["upcoming"] == 0
    assert settled_obs["settlement_latency"]["n"] == 1
    assert settled_obs["settlement_latency"]["median_hours"] == 3.0
    assert settled_obs["settlement_latency"]["negative_latency_count"] == 0


def test_trajectory_schedule_drift_is_observed_without_rewriting_frozen_schedule():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    first_current = _trajectory_simulation_row(
        match_id="traj-drift",
        scheduled=now + timedelta(hours=3),
    )
    first = _build_trajectory_evidence(first_current, {}, {}, now)
    frozen_time = first["snapshots"][0]["scheduled_time"]

    shifted = _trajectory_simulation_row(
        match_id="traj-drift",
        scheduled=now + timedelta(hours=3, minutes=20),
    )
    second = _build_trajectory_evidence(
        shifted,
        {},
        {"trajectory_evidence": first},
        now + timedelta(minutes=15),
    )

    drift = second["settlement_observability"]["schedule_drift"]
    assert drift["count"] == 1
    assert drift["samples"][0]["match_id"] == "traj-drift"
    assert drift["samples"][0]["drift_minutes"] == 20.0
    assert second["snapshots"][0]["scheduled_time"] == frozen_time
    assert second["ledger_integrity"]["rewritten_predictions"] == 0



def test_trajectory_new_snapshot_freezes_source_audit_and_semantic_simulator_contract():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    current = _trajectory_simulation_row(
        match_id="traj-provenance",
        scheduled=now + timedelta(hours=2),
    )
    evidence = _build_trajectory_evidence(current, {}, {}, now)

    source_fingerprint = _sha256_file(SIMULATOR_SOURCE)
    contract = trajectory_simulator_contract()
    contract_fingerprint = trajectory_simulator_contract_fingerprint()
    assert source_fingerprint is not None

    snapshot = evidence["snapshots"][0]
    assert snapshot["source_simulator_fingerprint_sha256"] == source_fingerprint
    assert snapshot["simulator_contract_id"] == contract["contract_id"]
    assert snapshot["simulator_contract_fingerprint_sha256"] == contract_fingerprint

    provenance = evidence["provenance"]
    assert provenance["current_simulator_contract_id"] == contract["contract_id"]
    assert (
        provenance["current_simulator_contract_fingerprint_sha256"]
        == contract_fingerprint
    )
    assert (
        provenance["current_simulator_source_fingerprint_sha256"]
        == source_fingerprint
    )
    assert provenance["known_generation_count"] == 1
    assert provenance["legacy_unknown_snapshots"] == 0
    assert provenance["current_generation_snapshots"] == 1
    assert provenance["mixed_known_generations"] is False
    assert provenance["policy"][
        "new_snapshots_require_semantic_simulator_contract_fingerprint"
    ] is True
    assert provenance["policy"][
        "source_file_fingerprint_is_audit_only_not_generation_identity"
    ] is True
    assert provenance["policy"][
        "future_trajectory_verdict_must_not_mix_simulator_generations"
    ] is True


def test_trajectory_provenance_never_rewrites_legacy_snapshot_to_backfill_semantic_contract():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    current = _trajectory_simulation_row(
        match_id="traj-legacy",
        scheduled=now + timedelta(hours=2),
    )
    first = _build_trajectory_evidence(current, {}, {}, now)
    legacy = dict(first["snapshots"][0])
    source_fingerprint = legacy["source_simulator_fingerprint_sha256"]
    legacy.pop("simulator_contract_id", None)
    legacy.pop("simulator_contract_fingerprint_sha256", None)

    second = _build_trajectory_evidence(
        {},
        {},
        {"trajectory_evidence": {"snapshots": [legacy]}},
        now + timedelta(minutes=20),
    )

    assert "simulator_contract_fingerprint_sha256" not in second["snapshots"][0]
    assert (
        second["snapshots"][0]["source_simulator_fingerprint_sha256"]
        == source_fingerprint
    )
    assert second["ledger_integrity"]["rewritten_predictions"] == 0
    provenance = second["provenance"]
    assert provenance["legacy_unknown_snapshots"] == 1
    assert provenance["current_generation_snapshots"] == 0
    assert provenance["policy"][
        "legacy_snapshots_are_never_rewritten_to_add_provenance"
    ] is True


def test_trajectory_provenance_marks_mixed_semantic_generations_without_merging_claims():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    current = _trajectory_simulation_row(
        match_id="traj-mixed",
        scheduled=now + timedelta(hours=2),
    )
    first = _build_trajectory_evidence(current, {}, {}, now)
    current_snapshot = dict(first["snapshots"][0])
    historical = dict(current_snapshot)
    historical["match_id"] = "traj-old-generation"
    historical["simulator_contract_id"] = "player-dna-trajectory-dp-old"
    historical["simulator_contract_fingerprint_sha256"] = "0" * 64

    report = _build_trajectory_evidence(
        {},
        {},
        {"trajectory_evidence": {"snapshots": [historical, current_snapshot]}},
        now + timedelta(minutes=20),
    )
    provenance = report["provenance"]

    assert provenance["known_generation_count"] == 2
    assert provenance["mixed_known_generations"] is True
    assert provenance["generations"]["0" * 64]["snapshots"] == 1
    assert provenance["policy"][
        "current_generation_should_be_evaluated_separately"
    ] is True


def _trajectory_backtest_fixture(
    semantic_fingerprint,
    *,
    contract_id=None,
    source_fingerprint="f" * 64,
):
    contract_id = contract_id or trajectory_simulator_contract()["contract_id"]
    return {
        "version": "player-dna-market-backtest-v1",
        "signal": "MIXED_OR_NO_MATCH_LEVEL_SIGNAL",
        "trajectory_simulator_provenance": {
            "source_sha256": source_fingerprint,
            "semantic_contract_id": contract_id,
            "semantic_contract_fingerprint_sha256": semantic_fingerprint,
            "source_sha256_is_audit_only": True,
            "semantic_contract_fingerprint_is_generation_identity": True,
        },
        "trajectory_validation": {
            "coverage": {"settled_predictions": 369},
            "checkpoint_neutral_start_server": {
                "after_2_games": {
                    "n": 368,
                    "top1_accuracy": 0.589674,
                    "top3_accuracy": 1.0,
                },
                "after_4_games": {
                    "n": 368,
                    "top1_accuracy": 0.407609,
                    "top3_accuracy": 0.894022,
                },
                "after_6_games": {
                    "n": 368,
                    "top1_accuracy": 0.326087,
                    "top3_accuracy": 0.8125,
                },
            },
            "first_set_conditioned_on_observed_first_server": {
                "n": 368,
                "hit_at_1": 0.019022,
                "hit_at_3": 0.100543,
                "hit_at_8": 0.203804,
            },
            "primary_storyline_match_score_conditioned_on_observed_first_server": {
                "n": 369,
                "hit_at_1": 0.349593,
                "hit_at_3": 0.666667,
            },
            "match_set_sequence_conditioned_on_observed_first_server": {
                "n": 369,
                "hit_at_1": 0.02168,
                "hit_at_3": 0.078591,
                "hit_at_12": 0.189702,
            },
            "full_match_game_path_conditioned_on_observed_first_server": {
                "n": 362,
                "hit_at_1": 0.0,
                "hit_at_2": 0.0,
                "hit_at_4": 0.0,
                "mean_top1_prefix_fraction": 0.097088,
            },
        },
    }


def test_trajectory_historical_benchmark_requires_same_semantic_simulator_contract():
    source_fingerprint = _sha256_file(SIMULATOR_SOURCE)
    contract = trajectory_simulator_contract()
    semantic_fingerprint = trajectory_simulator_contract_fingerprint()
    assert source_fingerprint is not None

    benchmark = _trajectory_historical_benchmark(
        _trajectory_backtest_fixture(
            semantic_fingerprint,
            source_fingerprint=source_fingerprint,
        ),
        contract["contract_id"],
        semantic_fingerprint,
        source_fingerprint,
    )

    assert benchmark["status"] == "COMPATIBLE_HISTORICAL_TRAJECTORY_BENCHMARK"
    assert benchmark["compatible_with_current_simulator_generation"] is True
    assert benchmark["historical_sample"]["settled_predictions"] == 369
    assert benchmark["historical_sample"]["full_match_game_path_n"] == 362
    assert benchmark["metrics"]["checkpoint_after_2_games_top1"] == 0.589674
    assert benchmark["metrics"]["storyline_match_score_top3"] == 0.666667
    assert benchmark["metrics"]["full_match_game_path_top4"] == 0.0
    assert benchmark["policy"][
        "benchmark_is_historical_reference_not_performance_verdict"
    ] is True
    assert benchmark["policy"][
        "semantic_contract_match_required_for_comparison"
    ] is True
    assert benchmark["policy"][
        "source_file_fingerprint_is_audit_only_not_compatibility_gate"
    ] is True
    assert benchmark["policy"][
        "prospective_evidence_remains_primary_for_future_verdict"
    ] is True


def test_trajectory_historical_benchmark_accepts_source_sha_change_when_semantics_match():
    source_fingerprint = _sha256_file(SIMULATOR_SOURCE)
    contract = trajectory_simulator_contract()
    semantic_fingerprint = trajectory_simulator_contract_fingerprint()
    assert source_fingerprint is not None

    benchmark = _trajectory_historical_benchmark(
        _trajectory_backtest_fixture(
            semantic_fingerprint,
            source_fingerprint="1" * 64,
        ),
        contract["contract_id"],
        semantic_fingerprint,
        source_fingerprint,
    )

    assert benchmark["compatible_with_current_simulator_generation"] is True
    assert (
        benchmark["benchmark_simulator_source_fingerprint_sha256"]
        != benchmark["current_simulator_source_fingerprint_sha256"]
    )


def test_trajectory_historical_benchmark_rejects_different_semantic_simulator_generation():
    source_fingerprint = _sha256_file(SIMULATOR_SOURCE)
    contract = trajectory_simulator_contract()
    semantic_fingerprint = trajectory_simulator_contract_fingerprint()
    assert source_fingerprint is not None

    benchmark = _trajectory_historical_benchmark(
        _trajectory_backtest_fixture("0" * 64),
        contract["contract_id"],
        semantic_fingerprint,
        source_fingerprint,
    )

    assert (
        benchmark["status"]
        == "HISTORICAL_TRAJECTORY_BENCHMARK_NOT_COMPATIBLE"
    )
    assert benchmark["compatible_with_current_simulator_generation"] is False
    assert benchmark["policy"][
        "semantic_contract_match_required_for_comparison"
    ] is True
    assert benchmark["policy"][
        "incompatible_benchmark_must_not_be_used_for_claims"
    ] is True


def test_trajectory_evidence_exposes_compatible_historical_reference_without_verdict():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    semantic_fingerprint = trajectory_simulator_contract_fingerprint()
    current = _trajectory_simulation_row(
        match_id="traj-benchmark",
        scheduled=now + timedelta(hours=2),
    )
    evidence = _build_trajectory_evidence(
        current,
        {},
        {},
        now,
        market_backtest=_trajectory_backtest_fixture(semantic_fingerprint),
    )

    benchmark = evidence["historical_benchmark"]
    assert benchmark["compatible_with_current_simulator_generation"] is True
    assert evidence["performance_verdict_emitted"] is False
    assert evidence["validation_scope"][
        "no_trajectory_performance_threshold_invented_yet"
    ] is True



def test_dynamic_policy_provenance_marks_new_snapshot_as_current_generation():
    now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
    report = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {},
        current_dynamic=_dynamic_current(scheduled=now + timedelta(hours=2)),
        now=now,
    )

    dynamic = report["dynamic_lean_evidence"]
    provenance = dynamic["market_policy_provenance"]
    assert provenance["current_market_policy_contract_id"] == DYNAMIC_POLICY_CONTRACT_ID
    assert provenance["current_market_policy_contract_fingerprint_sha256"] == DYNAMIC_POLICY_CONTRACT_FP
    assert provenance["current_market_policy_source_fingerprint_sha256"] == DYNAMIC_POLICY_SOURCE_FP
    assert provenance["known_generation_count"] == 1
    assert provenance["legacy_unknown_snapshots"] == 0
    assert provenance["current_generation_snapshots"] == 1
    assert provenance["other_known_generation_snapshots"] == 0
    assert provenance["verdict_excluded_snapshots"] == 0
    assert provenance["policy"][
        "new_snapshots_require_market_policy_contract_fingerprint"
    ] is True
    assert provenance["policy"][
        "future_verdict_uses_current_policy_generation_only"
    ] is True


def test_dynamic_legacy_policy_unknown_snapshots_remain_immutable_but_do_not_count_for_verdict():
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    legacy = _dynamic_settled_snapshot("legacy-1")
    legacy.pop("market_policy_contract_id", None)
    legacy.pop("market_policy_contract_fingerprint_sha256", None)

    report = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {"dynamic_lean_evidence": {"snapshots": [legacy]}},
        current_dynamic={
            **_dynamic_current(
                match_id="dyn-contract-only",
                scheduled=now - timedelta(hours=1),
            ),
            "matches": [],
        },
        now=now,
    )

    dynamic = report["dynamic_lean_evidence"]
    assert "market_policy_contract_fingerprint_sha256" not in dynamic["snapshots"][0]
    assert dynamic["snapshots"][0]["market_policy_source_fingerprint_sha256"] == DYNAMIC_POLICY_SOURCE_FP
    assert dynamic["ledger_integrity"]["rewritten_predictions"] == 0
    assert dynamic["ledger_evaluation"]["settled_market_observations"] == 1
    assert dynamic["evaluation"]["settled_market_observations"] == 0
    assert dynamic["evidence_readiness"]["ready_for_performance_verdict"] is False
    provenance = dynamic["market_policy_provenance"]
    assert provenance["legacy_unknown_snapshots"] == 1
    assert provenance["current_generation_snapshots"] == 0
    assert provenance["verdict_excluded_snapshots"] == 1
    assert provenance["policy"]["legacy_unknown_snapshots_remain_immutable"] is True
    assert provenance["policy"]["legacy_unknown_snapshots_are_diagnostic_only"] is True


def test_dynamic_old_known_policy_generation_cannot_satisfy_current_verdict_threshold():
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    old_policy = "b" * 64
    snapshots = [
        _dynamic_settled_snapshot(
            i,
            policy_fingerprint=old_policy,
        )
        for i in range(1, 151)
    ]

    report = build_report(
        {"version": "sim", "matches": []},
        _walk_forward(),
        [],
        {"dynamic_lean_evidence": {"snapshots": snapshots}},
        current_dynamic={
            **_dynamic_current(
                match_id="dyn-contract-only",
                scheduled=now - timedelta(hours=1),
            ),
            "matches": [],
        },
        now=now,
    )

    dynamic = report["dynamic_lean_evidence"]
    assert dynamic["ledger_evaluation"]["settled_market_observations"] == 150
    assert dynamic["evaluation"]["settled_market_observations"] == 0
    assert dynamic["counts"]["verdict_eligible_snapshots"] == 0
    assert dynamic["counts"]["verdict_excluded_snapshots"] == 150
    assert dynamic["evidence_readiness"]["ready_for_performance_verdict"] is False
    assert dynamic["performance_verdict"]["emitted"] is False
    assert dynamic["performance_verdict"]["signal"] == "DYNAMIC_LEAN_PROSPECTIVE_VERDICT_NOT_READY"
    provenance = dynamic["market_policy_provenance"]
    assert provenance["known_generation_count"] == 1
    assert provenance["other_known_generation_snapshots"] == 150
    assert provenance["policy"][
        "other_known_policy_generations_are_not_mixed_into_current_verdict"
    ] is True



def test_trajectory_legacy_unknown_snapshot_stays_in_ledger_but_not_primary_metrics():
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    current = _trajectory_simulation_row(
        match_id="traj-current-generation",
        scheduled=now - timedelta(hours=4),
    )
    first = _build_trajectory_evidence(current, {}, {}, now - timedelta(hours=6))
    snapshot = dict(first["snapshots"][0])
    snapshot.pop("source_simulator_fingerprint_sha256", None)

    labels = {
        "traj-current-generation": {
            "match_exact_score": "2:0",
            "trajectory_actual": _trajectory_actual(),
        }
    }
    _settle_trajectory_snapshots([snapshot], labels, now)

    report = _build_trajectory_evidence(
        {},
        labels,
        {"trajectory_evidence": {"snapshots": [snapshot]}},
        now,
    )

    assert report["ledger_evaluation"]["settled_matches"] == 1
    assert report["evaluation"]["settled_matches"] == 0
    assert report["counts"]["ledger_settled_snapshots"] == 1
    assert report["counts"]["settled_snapshots"] == 0
    assert report["counts"]["current_generation_snapshots"] == 0
    assert report["counts"]["evaluation_excluded_snapshots"] == 1
    provenance = report["provenance"]
    assert provenance["legacy_unknown_snapshots"] == 1
    assert provenance["evaluation_excluded_snapshots"] == 1
    assert provenance["policy"]["legacy_unknown_snapshots_are_diagnostic_only"] is True
    assert provenance["policy"][
        "current_generation_only_for_primary_prospective_metrics"
    ] is True


def test_trajectory_other_known_generation_cannot_contaminate_current_generation_metrics():
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    current = _trajectory_simulation_row(
        match_id="traj-current",
        scheduled=now - timedelta(hours=4),
    )
    first = _build_trajectory_evidence(current, {}, {}, now - timedelta(hours=6))
    current_snapshot = dict(first["snapshots"][0])
    old_snapshot = dict(current_snapshot)
    old_snapshot["match_id"] = "traj-old"
    old_snapshot["source_simulator_fingerprint_sha256"] = "0" * 64

    labels = {
        "traj-current": {
            "match_exact_score": "2:0",
            "trajectory_actual": _trajectory_actual(),
        },
        "traj-old": {
            "match_exact_score": "2:0",
            "trajectory_actual": _trajectory_actual(),
        },
    }
    snapshots = [current_snapshot, old_snapshot]
    _settle_trajectory_snapshots(snapshots, labels, now)

    report = _build_trajectory_evidence(
        {},
        labels,
        {"trajectory_evidence": {"snapshots": snapshots}},
        now,
    )

    assert report["ledger_evaluation"]["settled_matches"] == 2
    assert report["evaluation"]["settled_matches"] == 1
    assert report["counts"]["current_generation_snapshots"] == 1
    assert report["counts"]["evaluation_excluded_snapshots"] == 1
    assert report["segment_diagnostics"]["tour"]["challenger"]["settled"] == 1
    assert report["ledger_segment_diagnostics"]["tour"]["challenger"]["settled"] == 2
    provenance = report["provenance"]
    assert provenance["known_generation_count"] == 2
    assert provenance["other_known_generation_snapshots"] == 1
    assert provenance["evaluation_excluded_snapshots"] == 1
    assert provenance["policy"]["other_known_generations_are_diagnostic_only"] is True


def test_trajectory_generation_isolation_scope_and_accounting_are_explicit():
    now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
    current = _trajectory_simulation_row(
        match_id="traj-generation-scope",
        scheduled=now + timedelta(hours=2),
    )
    report = _build_trajectory_evidence(current, {}, {}, now)

    counts = report["counts"]
    assert counts["current_generation_snapshots"] + counts["evaluation_excluded_snapshots"] == counts["snapshots"]
    scope = report["validation_scope"]
    assert scope["primary_metrics_use_current_simulator_generation_only"] is True
    assert scope["legacy_and_other_simulator_generations_are_diagnostic_only"] is True
    assert isinstance(report["ledger_evaluation"], dict)
    assert isinstance(report["ledger_segment_diagnostics"], dict)
    assert report["performance_verdict_emitted"] is False
