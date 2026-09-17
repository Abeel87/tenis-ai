from __future__ import annotations

from backend.provider_identity_evidence import build_provider_evidence


def _payload(p1_id, p1_name, p2_id, p2_name):
    return {
        "match": {
            "players": {
                "p1": {"id": p1_id, "name": p1_name},
                "p2": {"id": p2_id, "name": p2_name},
            }
        }
    }


def test_same_numeric_id_only_creates_unscoped_upper_bound_candidate():
    index = {"players": {"jan kowalski": {"player_id": 101, "player": "Jan Kowalski"}}}
    payloads = [
        ("m1", _payload(101, "Jan Kowalski", 201, "Opponent One")),
        ("m2", _payload(101, "J Kowalski", 202, "Opponent Two")),
    ]

    report = build_provider_evidence(
        players_index=index,
        match_payloads=payloads,
        current_players=["Jan Kowalski"],
        history_keys=["j kowalski"],
        existing_resolutions={"jan kowalski": (None, "none")},
    )

    assert report["summary"]["current_players_with_unscoped_numeric_id_history_candidate"] == 1
    assert report["summary"]["current_players_with_safe_provider_alias"] == 0
    assert report["safe_current_aliases"] == []
    assert report["unscoped_current_candidates"] == [{
        "current_key": "jan kowalski",
        "current_names": ["Jan Kowalski"],
        "numeric_provider_id": 101,
        "history_key": "j kowalski",
        "scope": "UPPER_BOUND_ONLY_NAMESPACE_NOT_PROVEN",
    }]
    assert report["policy"]["runtime_alias_authorized"] is False


def test_alias_key_seen_under_two_numeric_ids_is_rejected_even_as_candidate():
    index = {"players": {"jan kowalski": {"player_id": 101, "player": "Jan Kowalski"}}}
    payloads = [
        ("m1", _payload(101, "J Kowalski", 201, "Opponent One")),
        ("m2", _payload(999, "J Kowalski", 202, "Opponent Two")),
    ]

    report = build_provider_evidence(
        players_index=index,
        match_payloads=payloads,
        current_players=["Jan Kowalski"],
        history_keys=["j kowalski"],
        existing_resolutions={"jan kowalski": (None, "none")},
    )

    assert report["summary"]["normalized_key_numeric_id_collisions"] == 1
    assert report["summary"]["current_players_with_unscoped_numeric_id_history_candidate"] == 0
    assert report["normalized_keys"]["j kowalski"]["numeric_id_collision"] is True


def test_current_key_numeric_id_conflict_fails_closed():
    index = {"players": {"jan kowalski": {"player_id": 101, "player": "Jan Kowalski"}}}
    payloads = [
        ("m1", _payload(999, "Jan Kowalski", 202, "Opponent Two")),
        ("m2", _payload(101, "J Kowalski", 203, "Opponent Three")),
    ]

    report = build_provider_evidence(
        players_index=index,
        match_payloads=payloads,
        current_players=["Jan Kowalski"],
        history_keys=["j kowalski"],
        existing_resolutions={"jan kowalski": (None, "none")},
    )

    assert report["summary"]["current_player_numeric_id_conflicts"] == 1
    assert report["summary"]["current_players_with_unscoped_numeric_id_history_candidate"] == 0
    assert report["conflicting_current_keys"][0]["observed_numeric_provider_ids"] == [101, 999]


def test_non_integer_index_ids_are_not_identity():
    index = {
        "players": {
            "string id": {"player_id": "101", "player": "String Id"},
            "float id": {"player_id": 101.0, "player": "Float Id"},
            "bool id": {"player_id": True, "player": "Bool Id"},
            "missing id": {"player": "Missing Id"},
        }
    }

    report = build_provider_evidence(
        players_index=index,
        match_payloads=[],
        current_players=["String Id", "Float Id", "Bool Id", "Missing Id"],
        history_keys=[],
    )

    assert report["summary"]["distinct_numeric_provider_ids"] == 0
    assert report["summary"]["current_players_with_exact_index_numeric_provider_id"] == 0
    assert report["summary"]["invalid_non_integer_index_ids"] == 3


def test_non_integer_payload_id_is_rejected_by_canonical_identity_gate():
    payloads = [
        ("string", _payload("101", "A", 201, "B")),
        ("float", _payload(101.0, "A", 201, "B")),
        ("bool", _payload(True, "A", 201, "B")),
        ("missing", {"match": {"players": {"p1": {"name": "A"}, "p2": {"id": 201, "name": "B"}}}}),
    ]

    report = build_provider_evidence(players_index={"players": {}}, match_payloads=payloads)

    assert report["summary"]["cached_match_payloads_scanned"] == 4
    assert report["summary"]["cached_match_payloads_with_strict_integer_identity"] == 0
    assert report["summary"]["distinct_numeric_provider_ids"] == 0


def test_two_unscoped_history_keys_stay_ambiguous():
    index = {"players": {"jan kowalski": {"player_id": 101, "player": "Jan Kowalski"}}}
    payloads = [
        ("m1", _payload(101, "J Kowalski", 201, "Opponent One")),
        ("m2", _payload(101, "Jan K Kowalski", 202, "Opponent Two")),
    ]

    report = build_provider_evidence(
        players_index=index,
        match_payloads=payloads,
        current_players=["Jan Kowalski"],
        history_keys=["j kowalski", "jan k kowalski"],
        existing_resolutions={"jan kowalski": (None, "none")},
    )

    assert report["summary"]["current_players_with_unscoped_numeric_id_history_candidate"] == 0
    assert report["summary"]["current_players_with_ambiguous_unscoped_history_keys"] == 1
    assert report["ambiguous_unscoped_candidates"][0]["history_candidates_unscoped"] == [
        "j kowalski",
        "jan k kowalski",
    ]


def test_existing_exact_or_expanded_resolution_is_not_replaced():
    index = {"players": {"jan kowalski": {"player_id": 101, "player": "Jan Kowalski"}}}
    payloads = [("m1", _payload(101, "J Kowalski", 201, "Opponent One"))]

    report = build_provider_evidence(
        players_index=index,
        match_payloads=payloads,
        current_players=["Jan Kowalski"],
        history_keys=["j kowalski"],
        existing_resolutions={"jan kowalski": ("j kowalski", "expanded-name")},
    )

    assert report["summary"]["current_players_with_unscoped_numeric_id_history_candidate"] == 0
    assert report["current_players"][0]["status"] == "history_already_resolved"


def test_empty_cache_fails_closed_without_fabricated_aliases():
    report = build_provider_evidence(
        players_index={"players": {}},
        match_payloads=[],
        current_players=["Nobody Here"],
        history_keys=["different person"],
    )

    assert report["summary"]["distinct_numeric_provider_ids"] == 0
    assert report["summary"]["same_numeric_id_multi_key_pairs_unscoped"] == 0
    assert report["summary"]["safe_provider_alias_pairs"] == 0
    assert report["summary"]["current_players_with_safe_provider_alias"] == 0
    assert report["current_players"][0]["status"] == "no_exact_current_numeric_provider_id"
