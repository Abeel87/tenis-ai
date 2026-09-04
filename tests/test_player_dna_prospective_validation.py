from datetime import datetime, timedelta, timezone

from backend.player_dna_prospective_validation import (
    DURATION_MARKETS,
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


def test_duration_market_scope_is_exact_and_candidate_only():
    assert DURATION_MARKETS == (
        "first_set_tiebreak",
        "first_set_over_8.5",
        "first_set_over_9.5",
        "first_set_over_10.5",
    )
