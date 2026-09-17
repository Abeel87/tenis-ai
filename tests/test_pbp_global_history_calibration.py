from collections import Counter

from backend import pbp_global_history_calibration as audit


def _stats(full=True):
    p1 = {
        "firstServePointsAccuracy": "20/30 (66.7%)",
        "secondServePointsAccuracy": "10/20 (50%)",
        "firstReturnPoints": "12/30 (40%)",
        "secondReturnPoints": "8/20 (40%)",
    }
    p2 = {
        "firstServePointsAccuracy": "18/30 (60%)",
        "secondServePointsAccuracy": "8/20 (40%)",
        "firstReturnPoints": "10/30 (33.3%)",
        "secondReturnPoints": "10/20 (50%)",
    }
    if not full:
        p1.pop("firstServePointsAccuracy")
        p2.pop("secondServePointsAccuracy")
    return {"p1": p1, "p2": p2}


def _score():
    return {"sets": [2, 0], "games": [[6, 6], [4, 4]]}


def _payload():
    score = _score()
    return {
        "match": {
            "id": 101,
            "scheduled_time": "2026-09-10T10:00:00+00:00",
            "surface": "hard",
            "winner": 1,
            "players": {
                "p1": {"id": 11, "name": "Alice Smith"},
                "p2": {"id": 22, "name": "Bob Jones"},
            },
            "score": score,
        },
        "tape": [{**score, "points": [0, 0]}],
        "profiles": [
            {
                "created_at": "2026-09-10T12:10:00+00:00",
                "input_state": {"score": score, "stats": _stats(full=False)},
            },
            {
                "created_at": "2026-09-10T12:00:00+00:00",
                "input_state": {"score": score, "stats": _stats(full=True)},
            },
        ],
    }


def _boundary(server, winner, atomic=False):
    return {
        "transition_kind": "game_score_changed",
        "server": server,
        "point_winner": winner,
        "is_tiebreak_before": False,
        "is_tiebreak_after": False,
        "quality": {"atomic_transition": atomic},
    }


def _complete_boundaries():
    rows = []
    for i in range(20):
        server = 1 if i % 2 == 0 else 2
        winner = server
        if i == 3:
            winner = 1
        if i == 8:
            winner = 2
        rows.append(_boundary(server, winner, atomic=False))
    return rows


def test_best_terminal_profile_prefers_more_raw_evidence_not_latest_timestamp():
    stats, evidence = audit.best_terminal_stats(_payload())
    assert stats == _stats(full=True)
    assert evidence["terminal_profiles"] == 2
    assert evidence["best_raw_split_slots"] == 8
    assert evidence["selected_profile_index"] == 1
    assert evidence["cross_profile_field_merge"] is False


def test_boundary_game_metrics_do_not_require_atomic_points(monkeypatch):
    monkeypatch.setattr(audit, "canonical_point_events", lambda payload, match_id=None: _complete_boundaries())
    result = audit.boundary_game_metrics({}, ((6, 4), (6, 4)), match_id=101)
    assert result["complete_observed_game_boundaries"] is True
    assert result["boundary_events"] == 20
    assert result["atomic_boundary_events"] == 0
    assert result["p1_hold_rate"] == 0.9
    assert result["p2_hold_rate"] == 0.9
    assert result["p1_break_rate"] == 0.1
    assert result["p2_break_rate"] == 0.1


def test_boundary_game_metrics_fail_closed_if_one_game_boundary_missing(monkeypatch):
    monkeypatch.setattr(audit, "canonical_point_events", lambda payload, match_id=None: _complete_boundaries()[:-1])
    result = audit.boundary_game_metrics({}, ((6, 4), (6, 4)), match_id=101)
    assert result["complete_observed_game_boundaries"] is False
    assert result["p1_hold_rate"] is None
    assert result["p2_break_rate"] is None


def test_relaxed_projection_can_be_ready_without_atomic_boundaries(monkeypatch):
    monkeypatch.setattr(audit, "canonical_point_events", lambda payload, match_id=None: _complete_boundaries())
    result = audit.project_payload_relaxed(_payload(), match_id=101)
    assert result["ready"] is True
    assert result["profile_evidence"]["best_raw_split_slots"] == 8
    assert result["game_evidence"]["atomic_boundary_events"] == 0
    assert result["rows"]["alice smith"]["core_fields_ready"] is True
    assert result["rows"]["alice smith"]["aux_fields_ready"] is True


def test_full_row_comparison_requires_every_required_field():
    left = {field: 0.5 for field in audit.REQUIRED_FIELDS}
    right = dict(left)
    result = audit.compare_full_player_row(left, right)
    assert result["complete_required_field_comparison"] is True
    assert result["all_required_within_2pp"] is True
    del right["break_rate"]
    result = audit.compare_full_player_row(left, right)
    assert result["complete_required_field_comparison"] is False
    assert result["all_required_within_2pp"] is False


def test_calibration_gate_requires_sample_and_each_field_rate():
    good = {
        field: Counter(comparable=25, within=25)
        for field in audit.REQUIRED_FIELDS
    }
    passed, detail = audit._calibration_gate(good, 25)
    assert passed is True
    assert detail["sample_sufficient"] is True

    weak = {field: Counter(comparable=25, within=25) for field in audit.REQUIRED_FIELDS}
    weak["hold_rate"] = Counter(comparable=25, within=24)
    passed, _ = audit._calibration_gate(weak, 25)
    assert passed is False

    passed, detail = audit._calibration_gate(good, 10)
    assert passed is False
    assert detail["sample_sufficient"] is False


def test_policy_constants_are_conservative():
    assert audit.MIN_FULL_DUPLICATE_PLAYER_ROWS >= 20
    assert audit.MIN_PER_FIELD_AGREEMENT_RATE >= 0.97
    assert audit.RATE_TOLERANCE == 0.02
