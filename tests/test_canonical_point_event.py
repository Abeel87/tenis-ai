from backend.canonical_point_event import canonical_point_events


def test_current_row_is_post_point_and_winner_belongs_to_transition():
    payload = {
        "tape": [
            {"sets": [0, 0], "games": [[0], [0]], "points": ["0", "0"], "server": 1, "point_winner": None, "is_tiebreak": False},
            {"sets": [0, 0], "games": [[0], [0]], "points": ["15", "0"], "server": 1, "point_winner": 1, "is_tiebreak": False},
        ]
    }
    events = canonical_point_events(payload, match_id="m1")
    assert len(events) == 1
    event = events[0]
    assert event["score_before"]["points"] == ["0", "0"]
    assert event["score_after"]["points"] == ["15", "0"]
    assert event["point_winner"] == 1
    assert event["server"] == 1
    assert event["receiver"] == 2


def test_game_boundary_uses_previous_row_server_not_next_game_server():
    payload = {
        "tape": [
            {"sets": [0, 0], "games": [[0], [3]], "points": ["30", "40"], "server": 1, "point_winner": 1, "is_tiebreak": False},
            {"sets": [0, 0], "games": [[0], [4]], "points": ["0", "0"], "server": 2, "point_winner": 2, "is_tiebreak": False},
        ]
    }
    event = canonical_point_events(payload)[0]
    assert event["transition_kind"] == "game_score_changed"
    assert event["point_winner"] == 2
    assert event["server"] == 1
    assert event["server_source"] == "previous_row"


def test_missing_winner_is_not_reconstructed_or_marked_trainable():
    payload = {
        "tape": [
            {"sets": [0, 0], "games": [[0], [0]], "points": ["15", "0"], "server": 2, "point_winner": 1, "is_tiebreak": False},
            {"sets": [0, 0], "games": [[0], [0]], "points": ["30", "15"], "server": 2, "point_winner": None, "is_tiebreak": False},
        ]
    }
    event = canonical_point_events(payload)[0]
    assert event["point_winner"] is None
    assert event["quality"]["winner_reconstructed"] is False
    assert event["quality"]["trainable_basic"] is False


def test_same_score_rows_do_not_create_fake_point_events():
    payload = {
        "tape": [
            {"sets": [0, 0], "games": [[0], [0]], "points": ["0", "0"], "server": 1, "point_winner": None, "is_tiebreak": False},
            {"sets": [0, 0], "games": [[0], [0]], "points": ["0", "0"], "server": 1, "point_winner": 1, "is_tiebreak": False},
        ]
    }
    assert canonical_point_events(payload) == []
