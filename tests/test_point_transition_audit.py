from backend.point_transition_audit import audit_payload


def test_transition_audit_reports_shapes_and_changes_without_interpreting_direction():
    payload = {
        "tape": [
            {"sets": [[0], [0]], "games": [[0], [0]], "points": [0, 0], "server": 1, "point_winner": 1, "is_tiebreak": False},
            {"sets": [[0], [0]], "games": [[0], [0]], "points": [15, 0], "server": 1, "point_winner": 1, "is_tiebreak": False},
            {"sets": [[0], [0]], "games": [[1], [0]], "points": [0, 0], "server": 2, "point_winner": 1, "is_tiebreak": False},
        ]
    }
    report = audit_payload(payload)
    assert report["rows"] == 3
    assert report["transition_kinds"]["point_score_changed"] == 1
    assert report["transition_kinds"]["game_score_changed"] == 1
    assert report["samples"]
    assert "kind" in report["samples"][0]


def test_transition_audit_keeps_missing_winner_visible():
    payload = {
        "tape": [
            {"sets": [0, 0], "games": [0, 0], "points": [0, 0], "server": 1, "point_winner": None, "is_tiebreak": False},
            {"sets": [0, 0], "games": [0, 0], "points": [0, 15], "server": 1, "is_tiebreak": False},
        ]
    }
    report = audit_payload(payload)
    assert report["winner_values"]["None"] == 2
    assert report["transition_kinds"]["point_score_changed"] == 1
