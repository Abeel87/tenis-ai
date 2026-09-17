from backend import pbp_history_schema_audit as audit


def _stats():
    return {
        "p1": {
            "firstServePointsAccuracy": "20/30 (66.7%)",
            "secondServePointsAccuracy": "10/20 (50%)",
            "firstReturnPoints": "12/30 (40%)",
            "secondReturnPoints": "8/20 (40%)",
        },
        "p2": {
            "firstServePointsAccuracy": "18/30 (60%)",
            "secondServePointsAccuracy": "8/20 (40%)",
            "firstReturnPoints": "10/30 (33.3%)",
            "secondReturnPoints": "10/20 (50%)",
        },
    }


def _event(server, winner, *, tiebreak=False):
    return {
        "transition_kind": "game_score_changed",
        "server": server,
        "point_winner": winner,
        "is_tiebreak_before": tiebreak,
        "is_tiebreak_after": tiebreak,
        "quality": {"trainable_point": True},
    }


def _complete_events():
    rows = []
    for index in range(20):
        server = 1 if index % 2 == 0 else 2
        winner = server
        if index == 3:
            winner = 1  # p1 breaks p2 once
        if index == 8:
            winner = 2  # p2 breaks p1 once
        rows.append(_event(server, winner))
    return rows


def _payload():
    score = {"sets": [2, 0], "games": [[6, 6], [4, 4]]}
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
        "profiles": [{
            "created_at": "2026-09-10T12:00:00+00:00",
            "input_state": {"score": score, "stats": _stats()},
        }],
    }


def test_service_split_projects_exact_raw_ratios():
    row = audit._service_split_metrics(_stats(), "p1")
    assert row["first_serve_won"] == 20 / 30
    assert row["second_serve_won"] == 10 / 20
    assert row["serve_points_won"] == 30 / 50
    assert row["return_points_won"] == 20 / 50


def test_complete_game_boundary_projection_derives_hold_and_break_rates():
    metrics = audit._game_metrics_from_events(_complete_events(), ((6, 4), (6, 4)))
    assert metrics["complete_game_boundary_coverage"] is True
    assert metrics["observed_non_tiebreak_game_events"] == 20
    assert metrics["p1_service_games"] == 10
    assert metrics["p2_service_games"] == 10
    assert metrics["p1_hold_rate"] == 9 / 10
    assert metrics["p2_hold_rate"] == 9 / 10
    assert metrics["p1_break_rate"] == 1 / 10
    assert metrics["p2_break_rate"] == 1 / 10


def test_incomplete_game_boundary_coverage_fails_closed():
    metrics = audit._game_metrics_from_events(_complete_events()[:-1], ((6, 4), (6, 4)))
    assert metrics["complete_game_boundary_coverage"] is False
    assert metrics["p1_hold_rate"] is None
    assert metrics["p2_break_rate"] is None


def test_tiebreak_is_not_counted_as_service_game():
    assert audit._expected_non_tiebreak_games(((7, 6), (6, 4))) == 22
    events = [_event(1 if i % 2 == 0 else 2, 1 if i % 2 == 0 else 2) for i in range(22)]
    events.append(_event(1, 1, tiebreak=True))
    metrics = audit._game_metrics_from_events(events, ((7, 6), (6, 4)))
    assert metrics["complete_game_boundary_coverage"] is True
    assert metrics["observed_non_tiebreak_game_events"] == 22


def test_project_payload_requires_complete_core_fields(monkeypatch):
    monkeypatch.setattr(audit, "canonical_point_events", lambda payload, match_id=None: _complete_events())
    result = audit.project_payload(_payload(), match_id=101)
    assert result["ready"] is True
    alice = result["rows"]["alice smith"]
    assert alice["core_fields_ready"] is True
    assert alice["aux_fields_ready"] is True
    assert alice["first_set_won"] == 1
    assert alice["won"] == 1


def test_project_payload_fails_closed_when_game_boundaries_are_incomplete(monkeypatch):
    monkeypatch.setattr(audit, "canonical_point_events", lambda payload, match_id=None: _complete_events()[:-2])
    result = audit.project_payload(_payload(), match_id=101)
    assert result["ready"] is False
    assert result["rows"]["alice smith"]["hold_rate"] is None
    assert result["rows"]["alice smith"]["core_fields_ready"] is False


def test_duplicate_calibration_tolerance_is_explicit():
    pbp = {field: 0.50 for field in (*audit.CORE_MODEL_FIELDS, *audit.AUX_MODEL_FIELDS)}
    tml = dict(pbp)
    tml["hold_rate"] = 0.519
    result = audit._compare_rows(pbp, tml)
    assert result["all_comparable_within_tolerance"] is True
    tml["hold_rate"] = 0.521
    result = audit._compare_rows(pbp, tml)
    assert result["all_comparable_within_tolerance"] is False


def test_task008_never_authorizes_runtime_by_sample_size_constant():
    assert audit.MIN_CALIBRATION_OBSERVATIONS_FOR_PROOF >= 20
    assert audit.CALIBRATION_TOLERANCE == 0.02
