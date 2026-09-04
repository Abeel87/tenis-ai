from datetime import datetime, timedelta, timezone

import pytest

from backend.player_dna_prospective_validation import (
    DURATION_MARKETS,
    _ledger_integrity,
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
