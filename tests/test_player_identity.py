from backend.player_identity import identity_for_side, player_identity_map


def test_explicit_p1_p2_ids_are_accepted():
    payload = {"match": {"players": {"p1": {"id": 921, "name": "A"}, "p2": {"id": 4808, "name": "B"}}}}
    assert player_identity_map(payload) == {1: {"id": 921, "name": "A"}, 2: {"id": 4808, "name": "B"}}
    assert identity_for_side(payload, 2)["id"] == 4808


def test_names_without_ids_are_not_identity():
    payload = {"match": {"players": {"p1": {"name": "A"}, "p2": {"name": "B"}}}}
    assert player_identity_map(payload) is None


def test_duplicate_ids_are_rejected():
    payload = {"match": {"players": {"p1": {"id": 7}, "p2": {"id": 7}}}}
    assert player_identity_map(payload) is None


def test_non_integer_ids_are_rejected_without_coercion():
    for bad in ("921", 921.0, True, False, None):
        payload = {"match": {"players": {"p1": {"id": bad}, "p2": {"id": 4808}}}}
        assert player_identity_map(payload) is None


def test_no_fuzzy_or_top_level_fallback():
    payload = {"player1_id": 1, "player2_id": 2, "match": {}}
    assert player_identity_map(payload) is None
    assert identity_for_side(payload, 1) is None
