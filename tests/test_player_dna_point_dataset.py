from backend.player_dna_point_dataset import compact_observation, observations_from_payload


def _row(points, games=(0, 0), sets=(0, 0), server=1, winner=None):
    return {
        "points": list(points),
        "games": list(games),
        "sets": list(sets),
        "server": server,
        "point_winner": winner,
        "is_tiebreak": False,
    }


def test_builder_uses_canonical_event_and_basic_trainability():
    payload = {
        "meta": {"point_source": "observed"},
        "tape": [
            _row((0, 0), server=1),
            _row((15, 0), server=1, winner=1),
            _row((15, 15), server=1, winner=2),
        ],
    }
    rows = observations_from_payload(payload, "m1")
    assert len(rows) == 2
    assert rows[0]["server"] == 1
    assert rows[0]["receiver"] == 2
    assert rows[0]["server_won"] is True
    assert rows[1]["server_won"] is False
    assert all(row["trainable_basic"] for row in rows)
    assert all(row["point_source"] == "observed" for row in rows)


def test_missing_winner_is_never_silently_trainable():
    event = {
        "schema_version": "canonical-point-event-v1",
        "match_id": "m2",
        "event_index": 0,
        "transition_kind": "point_score_changed",
        "score_before": {"sets": [0, 0], "games": [0, 0], "points": [0, 0]},
        "score_after": {"sets": [0, 0], "games": [0, 0], "points": [15, 0]},
        "server": 1,
        "receiver": 2,
        "point_winner": None,
        "server_source": "previous_row",
        "quality": {"trainable_basic": False},
    }
    row = compact_observation(event)
    assert row["server_won"] is None
    assert row["receiver_won"] is None
    assert row["trainable_basic"] is False


def test_game_boundary_keeps_previous_server_from_canonical_layer():
    payload = {
        "meta": {"point_source": "observed"},
        "tape": [
            _row((40, 0), games=(0, 0), server=1),
            _row((0, 0), games=(1, 0), server=2, winner=1),
        ],
    }
    row = observations_from_payload(payload, "m3")[0]
    assert row["transition_kind"] == "game_score_changed"
    assert row["server"] == 1
    assert row["server_source"] == "previous_row"
    assert row["server_won"] is True
