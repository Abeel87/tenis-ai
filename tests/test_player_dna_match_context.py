from backend.player_dna_match_context import resolve_match_context


def _payload():
    return {
        "match": {
            "id": 123,
            "scheduled_time": "2026-09-04T10:08:00Z",
            "surface": " Hard ",
            "tour": "atp",
            "format": "bo3",
            "round_code": "qf",
            "indoor": False,
            "is_qualifying": True,
            "players": {
                "p1": {"id": 11, "ranking": 25},
                "p2": {"id": 22, "ranking": None},
            },
        }
    }


def test_context_uses_only_explicit_provider_fields():
    context = resolve_match_context(_payload())
    assert context == {
        "version": "player-dna-match-context-v1",
        "match_id": 123,
        "scheduled_time": "2026-09-04T10:08:00Z",
        "surface": "hard",
        "tour": "ATP",
        "format": "BO3",
        "round_code": "QF",
        "indoor": False,
        "is_qualifying": True,
        "p1": {"id": 11, "ranking": 25},
        "p2": {"id": 22, "ranking": None},
        "provider_backed": True,
        "training_join_enabled": False,
    }


def test_context_rejects_unparseable_or_naive_match_time():
    payload = _payload()
    payload["match"]["scheduled_time"] = "not-a-date"
    assert resolve_match_context(payload) is None
    payload["match"]["scheduled_time"] = "2026-09-04T10:08:00"
    assert resolve_match_context(payload) is None


def test_context_does_not_coerce_player_ids_or_rankings():
    payload = _payload()
    payload["match"]["players"]["p1"]["id"] = "11"
    assert resolve_match_context(payload) is None

    payload = _payload()
    payload["match"]["players"]["p1"]["ranking"] = "25"
    context = resolve_match_context(payload)
    assert context["p1"]["ranking"] is None


def test_optional_context_stays_missing_instead_of_being_invented():
    payload = _payload()
    for key in ("surface", "tour", "format", "round_code", "indoor", "is_qualifying"):
        payload["match"][key] = None
    context = resolve_match_context(payload)
    assert context["surface"] is None
    assert context["tour"] is None
    assert context["format"] is None
    assert context["round_code"] is None
    assert context["indoor"] is None
    assert context["is_qualifying"] is None
    assert context["training_join_enabled"] is False
