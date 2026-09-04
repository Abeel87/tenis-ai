from backend.player_dna_ordering_authority_audit import audit_payloads


def _base_payload(times):
    return {
        "match": {
            "id": 123,
            "scheduled_time": "2026-09-04T10:00:00Z",
            "players": {"p1": {"id": 1}, "p2": {"id": 2}},
        },
        "tape": [
            {"sets": [0, 0], "games": [0, 0], "points": ["0", "0"], "server": 1, "timestamp": times[0]},
            {"sets": [0, 0], "games": [0, 0], "points": ["15", "0"], "server": 1, "point_winner": 1, "timestamp": times[1]},
            {"sets": [0, 0], "games": [0, 0], "points": ["30", "0"], "server": 1, "point_winner": 1, "timestamp": times[2]},
            {"sets": [0, 0], "games": [0, 0], "points": ["40", "0"], "server": 1, "point_winner": 1, "timestamp": times[3]},
        ],
        "meta": {"point_source": "observed"},
    }


def test_provider_order_wins_when_timestamp_sort_breaks_atomic_score_progression():
    payload = _base_payload([
        "2026-09-04T10:00:00Z",
        "2026-09-04T10:00:30Z",
        "2026-09-04T10:00:10Z",
        "2026-09-04T10:00:40Z",
    ])
    report = audit_payloads([("m1", payload)])
    assert report["gate"] == "AUDIT_ONLY_NO_ORDERING_ACTIVATION"
    assert report["training_join_enabled"] is False
    assert report["profile_aggregation_enabled"] is False
    assert report["ordering_activation_enabled"] is False
    assert report["timestamp_sort"]["matches_whose_row_order_changes"] == 1
    assert report["provider_sequence"]["trainable_point"] == 3
    assert report["timestamp_sorted_sequence"]["trainable_point"] < 3
    assert report["per_match_comparison"]["provider_more_atomic_matches"] == 1
    assert report["ordering_authority_candidate"] == "PROVIDER_SEQUENCE_CLEAN_CANDIDATE"


def test_equal_order_stays_unresolved_for_single_clean_example():
    payload = _base_payload([
        "2026-09-04T10:00:00Z",
        "2026-09-04T10:00:10Z",
        "2026-09-04T10:00:20Z",
        "2026-09-04T10:00:30Z",
    ])
    report = audit_payloads([("m1", payload)])
    assert report["timestamp_sort"]["matches_whose_row_order_changes"] == 0
    assert report["provider_sequence"]["trainable_point"] == 3
    assert report["timestamp_sorted_sequence"]["trainable_point"] == 3
    assert report["ordering_authority_candidate"] == "UNRESOLVED"


def test_invalid_timestamp_is_counted_without_activating_repair():
    payload = _base_payload([
        "2026-09-04T10:00:00Z",
        "not-a-date",
        "2026-09-04T10:00:20Z",
        "2026-09-04T10:00:30Z",
    ])
    report = audit_payloads([("m1", payload)])
    assert report["invalid_timestamp_rows"] == 1
    assert report["ordering_activation_enabled"] is False
