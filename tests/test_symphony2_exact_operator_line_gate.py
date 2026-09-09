from copy import deepcopy

from backend.symphony2_engine import _current_offer, _project_final_playable


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



def test_final_playable_projection_comes_only_from_recommended_symphony_composition():
    legacy_signal = {
        "market": "match_winner",
        "pick": "Player A",
        "score": 99.0,
        "operator_playable": True,
    }
    results = [
        {
            "id": 101,
            "p1": "Player A",
            "p2": "Player B",
            "scheduled_time": "2099-01-01T12:00:00Z",
            "match_win": {"Player A": 99.0},
            "superbet_playable_v912": {
                "playable": True,
                "signals": [legacy_signal],
            },
        },
        {
            "id": 202,
            "p1": "Player C",
            "p2": "Player D",
            "scheduled_time": "2099-01-01T13:00:00Z",
            "superbet_playable_v912": {
                "playable": True,
                "signals": [legacy_signal],
            },
        },
    ]
    before = deepcopy(results)
    leg1 = {
        "selection_id": "match_winner|player a|None|0|",
        "market": "match_winner",
        "pick": "Player A",
        "operator_model_probability": 71.0,
        "fixture_line_verified": True,
    }
    leg2 = {
        "selection_id": "set1_total|over|9.5|0|",
        "market": "set1_total",
        "pick": "over",
        "line": 9.5,
        "operator_model_probability": 68.0,
        "fixture_line_verified": True,
    }
    current = {
        "version": "symphony2-runtime-test",
        "generated_at": "2099-01-01T10:00:00+00:00",
        "matches": [
            {
                "id": 101,
                "match_key": "101",
                "recommended_leg_count": 2,
                "compositions": {
                    "2": {
                        "legs": 2,
                        "score": 81.2,
                        "joint_probability": 54.321,
                        "joint_status": "EXACT_SHARED_STATE",
                        "selection": [leg1, leg2],
                    }
                },
            },
            {
                "id": 202,
                "match_key": "202",
                "recommended_leg_count": None,
                "compositions": {},
            },
        ],
    }

    projected = _project_final_playable(results, current)

    assert results == before
    final = projected[0]["symphony2_playable"]
    assert final["authority"] == "SYMPHONY2_FINAL_PLAYABLE"
    assert final["final_playable_authority"] is True
    assert final["playable"] is True
    assert final["playable_count"] == 2
    assert final["recommended_leg_count"] == 2
    assert final["joint_probability"] == 54.321
    assert final["signals"] == [leg1, leg2]
    assert projected[0]["match_win"] == before[0]["match_win"]
    assert projected[0]["superbet_playable_v912"] == before[0]["superbet_playable_v912"]

    no_composition = projected[1]["symphony2_playable"]
    assert no_composition["playable"] is False
    assert no_composition["signals"] == []
    assert no_composition["status"] == "NO_RECOMMENDED_COMPOSITION"


def test_final_playable_projection_fails_closed_without_current_symphony_row():
    results = [{
        "id": 303,
        "p1": "Player E",
        "p2": "Player F",
        "scheduled_time": "2099-01-01T14:00:00Z",
        "superbet_playable_v912": {
            "playable": True,
            "signals": [{"market": "match_winner", "pick": "Player E", "score": 95.0}],
        },
    }]

    projected = _project_final_playable(
        results,
        {"generated_at": "2099-01-01T10:00:00+00:00", "matches": []},
    )

    layer = projected[0]["symphony2_playable"]
    assert layer["playable"] is False
    assert layer["playable_count"] == 0
    assert layer["signals"] == []
    assert layer["status"] == "NOT_CURRENT_PREMATCH"
