from backend.player_dna_point_dataset import compact_observation, observations_from_payload


def _row(points, games=(0, 0), sets=(0, 0), server=1, winner=None):
    return {"points": list(points), "games": list(games), "sets": list(sets), "server": server, "point_winner": winner, "is_tiebreak": False}


def _players():
    return {"p1": {"id": 921, "name": "A"}, "p2": {"id": 4808, "name": "B"}}


def test_atomic_points_attach_explicit_stable_player_ids():
    payload = {"match": {"players": _players()}, "meta": {"point_source": "observed"}, "tape": [_row((0, 0), server=1), _row((15, 0), server=1, winner=1), _row((15, 15), server=1, winner=2)]}
    rows = observations_from_payload(payload, "m1")
    assert len(rows) == 2
    assert all(row["trainable_point"] for row in rows)
    assert all(row["identity_valid"] for row in rows)
    assert all(row["p1_player_id"] == 921 and row["p2_player_id"] == 4808 for row in rows)
    assert all(row["server_player_id"] == 921 and row["receiver_player_id"] == 4808 for row in rows)
    assert all(row["trainable_player_point"] for row in rows)


def test_missing_identity_never_guesses_from_names_or_sides():
    payload = {"match": {"players": {"p1": {"name": "A"}, "p2": {"name": "B"}}}, "tape": [_row((0, 0), server=1), _row((15, 0), server=1, winner=1)]}
    row = observations_from_payload(payload, "no-id")[0]
    assert row["trainable_point"] is True
    assert row["identity_valid"] is False
    assert row["server_player_id"] is None
    assert row["receiver_player_id"] is None
    assert row["trainable_player_point"] is False


def test_compressed_transition_is_not_player_trainable_even_with_identity():
    payload = {"match": {"players": _players()}, "tape": [_row((0, 0), server=1), _row((30, 0), server=1, winner=1)]}
    row = observations_from_payload(payload, "compressed")[0]
    assert row["identity_valid"] is True
    assert row["trainable_basic"] is True
    assert row["trainable_point"] is False
    assert row["trainable_player_point"] is False
    assert row["atomic_reason"] == "compressed_or_wrong_point_step"


def test_missing_winner_is_never_silently_trainable():
    event = {"schema_version": "canonical-point-event-v2", "match_id": "m2", "event_index": 0, "transition_kind": "point_score_changed", "score_before": {"sets": [0, 0], "games": [0, 0], "points": [0, 0]}, "score_after": {"sets": [0, 0], "games": [0, 0], "points": [15, 0]}, "server": 1, "receiver": 2, "point_winner": None, "server_source": "previous_row", "quality": {"trainable_basic": False, "atomic_transition": False, "trainable_point": False}}
    row = compact_observation(event, {1: {"id": 921}, 2: {"id": 4808}})
    assert row["server_won"] is None
    assert row["trainable_point"] is False
    assert row["trainable_player_point"] is False


def test_game_boundary_maps_previous_server_to_stable_id():
    payload = {"match": {"players": _players()}, "tape": [_row((40, 0), games=(0, 0), server=1), _row((0, 0), games=(1, 0), server=2, winner=1)]}
    row = observations_from_payload(payload, "m3")[0]
    assert row["transition_kind"] == "game_score_changed"
    assert row["server"] == 1
    assert row["server_source"] == "previous_row"
    assert row["server_player_id"] == 921
    assert row["receiver_player_id"] == 4808
    assert row["trainable_player_point"] is True


def test_dataset_carries_provider_ordering_contract_without_timestamp_reorder():
    payload = {
        "match": {"players": _players()},
        "tape": [
            {**_row((0, 0), server=1), "timestamp": "2026-09-04T10:00:00Z"},
            {**_row((15, 0), server=1, winner=1), "timestamp": "2026-09-04T10:00:30Z"},
            {**_row((30, 0), server=1, winner=1), "timestamp": "2026-09-04T10:00:10Z"},
        ],
    }
    rows = observations_from_payload(payload, "ordering")
    assert [row["event_index"] for row in rows] == [0, 1]
    assert [row["timestamp_after"] for row in rows] == [
        "2026-09-04T10:00:30Z",
        "2026-09-04T10:00:10Z",
    ]
    assert all(row["ordering_authority"] == "provider_sequence_clean" for row in rows)
    assert all(row["timestamp_role"] == "metadata_only_no_reordering" for row in rows)
    assert all(row["provider_row_order_preserved"] is True for row in rows)


def test_provider_backed_context_is_attached_only_when_identity_agrees():
    payload = {
        "match": {
            "id": 77,
            "scheduled_time": "2026-09-04T10:00:00Z",
            "surface": "Hard",
            "tour": "atp",
            "format": "bo3",
            "round_code": "qf",
            "indoor": False,
            "is_qualifying": False,
            "players": {
                "p1": {"id": 921, "name": "A", "ranking": 12},
                "p2": {"id": 4808, "name": "B", "ranking": 33},
            },
        },
        "tape": [
            _row((0, 0), server=1),
            _row((15, 0), server=1, winner=1),
        ],
    }
    row = observations_from_payload(payload, "ctx")[0]
    assert row["context_valid"] is True
    assert row["context_provider_backed"] is True
    assert row["context_training_join_enabled"] is False
    assert row["match_scheduled_time"] == "2026-09-04T10:00:00Z"
    assert row["surface"] == "hard"
    assert row["tour"] == "ATP"
    assert row["match_format"] == "BO3"
    assert row["round_code"] == "QF"
    assert row["indoor"] is False
    assert row["is_qualifying"] is False
    assert row["p1_ranking"] == 12
    assert row["p2_ranking"] == 33
    assert row["server_ranking"] == 12
    assert row["receiver_ranking"] == 33
    assert row["context_ready_player_point"] is True


def test_invalid_or_missing_context_never_invents_shadow_features():
    payload = {
        "match": {"players": _players()},
        "tape": [
            _row((0, 0), server=1),
            _row((15, 0), server=1, winner=1),
        ],
    }
    row = observations_from_payload(payload, "no-context")[0]
    assert row["trainable_player_point"] is True
    assert row["context_valid"] is False
    assert row["context_provider_backed"] is False
    assert row["context_training_join_enabled"] is False
    assert row["match_scheduled_time"] is None
    assert row["surface"] is None
    assert row["server_ranking"] is None
    assert row["context_ready_player_point"] is False
