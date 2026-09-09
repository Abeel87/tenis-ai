from backend.symphony2_engine import _current_offer


def _match(
    selections,
    *,
    operator="superbet.pl",
    operator_verified=True,
    status="VERIFIED",
    suspended=False,
):
    return {
        "superbet_market_v91": {
            "operator": operator,
            "operator_verified": operator_verified,
            "status": status,
            "suspended": suspended,
            "canonical_selections": selections,
        }
    }


def _line(line, *, verified, available=True, **extra):
    return {
        "market": "match_total",
        "pick": "over",
        "line": line,
        "operator_available": available,
        "operator_line_verified": verified,
        "fixture_line_verified": verified,
        **extra,
    }


def test_only_exact_fixture_verified_line_enters_symphony_offer():
    match = _match([
        _line(20.5, verified=True),
        _line(21.5, verified=False),
    ])

    offer = _current_offer(match)

    assert len(offer) == 1
    assert offer[0]["market"] == "match_total"
    assert offer[0]["line"] == 20.5
    assert offer[0]["fixture_line_verified"] is True


def test_nearby_verified_line_never_authorizes_an_unverified_line():
    match = _match([
        _line(20.5, verified=True),
        _line(
            21.5,
            verified=False,
            operator_line_verified=True,
            operator_line_source="model_or_nearest_line_should_not_count",
        ),
    ])

    offer = _current_offer(match)

    assert [row["line"] for row in offer] == [20.5]


def test_line_market_without_real_numeric_line_is_fail_closed():
    match = _match([
        {
            "market": "set1_total",
            "pick": "over",
            "line": None,
            "operator_available": True,
            "fixture_line_verified": True,
        },
        {
            "market": "set1_total",
            "pick": "under",
            "line": "not-a-line",
            "operator_available": True,
            "fixture_line_verified": True,
        },
    ])

    assert _current_offer(match) == []


def test_operator_unavailable_selection_is_never_actionable_even_if_verified():
    match = _match([
        _line(20.5, verified=True, available=False),
    ])

    assert _current_offer(match) == []


def test_unverified_operator_context_is_fail_closed():
    selection = _line(20.5, verified=True)

    assert _current_offer(_match([selection], operator_verified=False)) == []
    assert _current_offer(_match([selection], status="STALE")) == []


def test_wrong_or_suspended_operator_context_is_fail_closed():
    selection = _line(20.5, verified=True, operator_line_verified=True)

    assert _current_offer(_match([selection], operator="other.example")) == []
    assert _current_offer(_match([selection], suspended=True)) == []


def test_non_line_market_can_pass_without_fixture_line_flag_but_only_from_verified_offer():
    winner = {
        "market": "match_winner",
        "pick": "Player A",
        "operator_available": True,
    }

    offer = _current_offer(_match([winner]))

    assert len(offer) == 1
    assert offer[0]["market"] == "match_winner"
    assert offer[0].get("line") is None


def test_model_only_line_flag_cannot_replace_fixture_line_proof():
    match = _match([
        {
            "market": "player_total_games",
            "player": "Player A",
            "pick": "over",
            "line": 10.5,
            "operator_available": True,
            "operator_line_verified": True,
            "fixture_line_verified": False,
        }
    ])

    assert _current_offer(match) == []


def test_set3_game_handicap_is_treated_as_numeric_line_market():
    malformed = {
        "market": "set3_game_handicap",
        "pick": "Player A",
        "line": None,
        "operator_available": True,
        "operator_line_verified": True,
        "fixture_line_verified": True,
    }
    valid = {
        **malformed,
        "line": -1.5,
    }

    assert _current_offer(_match([malformed])) == []
    offer = _current_offer(_match([valid]))
    assert len(offer) == 1
    assert offer[0]["market"] == "set3_game_handicap"
    assert offer[0]["line"] == -1.5
