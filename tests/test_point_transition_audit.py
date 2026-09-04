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
    assert report["point_tokens"]["int:0"] == 5
    assert report["point_tokens"]["int:15"] == 1
    assert report["standard_point_transition_pairs"]["[0, 0]->[15, 0]"] == 1
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


def test_transition_audit_separates_tiebreak_point_transitions():
    payload = {
        "tape": [
            {"sets": [1, 0], "games": [6, 6], "points": ["3", "2"], "server": 1, "point_winner": 1, "is_tiebreak": True},
            {"sets": [1, 0], "games": [6, 6], "points": ["4", "2"], "server": 1, "point_winner": 1, "is_tiebreak": True},
        ]
    }
    report = audit_payload(payload)
    assert report["is_tiebreak_values"]["True"] == 2
    assert report["point_tokens"]["str:'3'"] == 1
    assert report["point_tokens"]["str:'4'"] == 1
    assert report["tiebreak_point_transition_pairs"]["['3', '2']->['4', '2']"] == 1
    assert report["standard_point_transition_pairs"] == {}
