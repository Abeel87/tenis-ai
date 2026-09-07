import math

import pytest

from backend.player_dna_tennis_simulator import (
    dynamic_set_outcomes,
    neutral_tiebreak_win_probability,
    set_outcomes,
)
from backend.player_dna_tennis_state_engine import (
    MODE,
    TennisState,
    evaluate_phase5_gate,
    initial_state,
    legal_completed_set_score,
    other_player,
    set_score_is_terminal,
    state_dict,
    tiebreak_server,
    tiebreak_should_start,
    transition_point,
    validate_state,
)


def test_standard_game_point_ladder_and_service_rotation_are_legal():
    state = initial_state(best_of=3, start_server=1)
    assert state.points == ("0", "0")
    assert state.server == 1

    state = transition_point(state, 1)
    assert state.points == ("15", "0")
    state = transition_point(state, 1)
    assert state.points == ("30", "0")
    state = transition_point(state, 1)
    assert state.points == ("40", "0")
    state = transition_point(state, 1)

    assert state.games == (1, 0)
    assert state.points == ("0", "0")
    assert state.server == 2
    assert state.set_start_server == 1
    assert state.is_tiebreak is False


def test_deuce_advantage_round_trip_and_game_finish():
    state = TennisState(
        best_of=3,
        sets=(0, 0),
        games=(2, 2),
        points=("40", "40"),
        server=1,
        set_start_server=1,
    )
    validate_state(state)

    state = transition_point(state, 1)
    assert state.points == ("A", "40")
    state = transition_point(state, 2)
    assert state.points == ("40", "40")
    state = transition_point(state, 2)
    assert state.points == ("40", "A")
    state = transition_point(state, 2)

    assert state.games == (2, 3)
    assert state.points == ("0", "0")
    assert state.server == 2


def test_regular_set_finish_records_score_and_preserves_continuous_serve_order():
    state = TennisState(
        best_of=3,
        sets=(0, 0),
        games=(5, 4),
        points=("40", "0"),
        server=2,
        set_start_server=1,
    )
    validate_state(state)

    state = transition_point(state, 1)

    assert state.sets == (1, 0)
    assert state.completed_sets == ((6, 4),)
    assert state.games == (0, 0)
    assert state.points == ("0", "0")
    # 6:4 is 10 games, so the first server of the previous set serves first again.
    assert state.server == 1
    assert state.set_start_server == 1


def test_six_all_enters_tiebreak_and_uses_official_service_rotation():
    state = TennisState(
        best_of=3,
        sets=(0, 0),
        games=(5, 6),
        points=("40", "0"),
        server=2,
        set_start_server=1,
    )
    state = transition_point(state, 1)

    assert state.games == (6, 6)
    assert state.is_tiebreak is True
    assert state.tiebreak_first_server == 1
    assert state.server == 1

    # First server serves one point; opponent then serves two; then two back.
    state = transition_point(state, 1)
    assert state.points == ("1", "0")
    assert state.server == 2
    state = transition_point(state, 2)
    assert state.points == ("1", "1")
    assert state.server == 2
    state = transition_point(state, 2)
    assert state.points == ("1", "2")
    assert state.server == 1
    state = transition_point(state, 1)
    assert state.server == 1
    state = transition_point(state, 1)
    assert state.server == 2


def test_extended_tiebreak_finishes_by_two_and_next_set_server_is_receiver_of_first_tb_point():
    state = TennisState(
        best_of=3,
        sets=(0, 0),
        games=(6, 6),
        points=("10", "10"),
        server=tiebreak_server(1, 20),
        set_start_server=1,
        is_tiebreak=True,
        tiebreak_first_server=1,
    )
    validate_state(state)

    state = transition_point(state, 1)
    assert state.points == ("11", "10")
    assert state.is_tiebreak is True
    state = transition_point(state, 1)

    assert state.sets == (1, 0)
    assert state.completed_sets == ((7, 6),)
    assert state.games == (0, 0)
    assert state.is_tiebreak is False
    assert state.server == 2
    assert state.set_start_server == 2


def test_bo3_terminal_match_rejects_any_further_point():
    state = TennisState(
        best_of=3,
        sets=(1, 0),
        games=(5, 0),
        points=("40", "0"),
        server=2,
        set_start_server=1,
        completed_sets=((6, 4),),
    )
    state = transition_point(state, 1)

    assert state.sets == (2, 0)
    assert state.completed_sets == ((6, 4), (6, 0))
    assert state.match_winner == 1
    assert state.terminal is True
    assert state.games == (0, 0)

    with pytest.raises(ValueError, match="terminal"):
        transition_point(state, 2)


def test_bo5_requires_three_sets_not_two():
    state = TennisState(
        best_of=5,
        sets=(2, 0),
        games=(5, 0),
        points=("40", "0"),
        server=2,
        set_start_server=1,
        completed_sets=((6, 4), (7, 5)),
    )
    state = transition_point(state, 1)

    assert state.sets == (3, 0)
    assert state.match_winner == 1
    assert state.terminal is True


@pytest.mark.parametrize(
    "state",
    [
        TennisState(
            best_of=3,
            sets=(0, 0),
            games=(6, 6),
            points=("0", "0"),
            server=1,
            set_start_server=1,
        ),
        TennisState(
            best_of=3,
            sets=(0, 0),
            games=(7, 5),
            points=("0", "0"),
            server=1,
            set_start_server=1,
        ),
        TennisState(
            best_of=3,
            sets=(0, 0),
            games=(0, 0),
            points=("A", "30"),
            server=1,
            set_start_server=1,
        ),
        TennisState(
            best_of=3,
            sets=(0, 0),
            games=(1, 0),
            points=("0", "0"),
            server=1,
            set_start_server=1,
        ),
    ],
)
def test_impossible_live_states_fail_closed(state):
    with pytest.raises(ValueError):
        validate_state(state)


def test_tiebreak_server_sequence_is_exact_for_first_thirteen_points():
    assert [tiebreak_server(1, n) for n in range(13)] == [
        1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1, 1
    ]
    assert [tiebreak_server(2, n) for n in range(7)] == [2, 1, 1, 2, 2, 1, 1]


@pytest.mark.parametrize(
    ("score", "legal"),
    [
        ((6, 0), True),
        ((6, 4), True),
        ((7, 5), True),
        ((7, 6), True),
        ((6, 7), True),
        ((6, 5), False),
        ((5, 5), False),
        ((8, 6), False),
        ((7, 4), False),
    ],
)
def test_completed_set_score_contract(score, legal):
    assert legal_completed_set_score(score) is legal


def test_simulator_set_outcomes_use_only_phase5_legal_scores_and_serve_order():
    for start_server in (1, 2):
        rows = set_outcomes(0.63, 0.59, start_server)
        assert math.isclose(sum(float(row["probability"]) for row in rows), 1.0, abs_tol=1e-10)
        for row in rows:
            score = tuple(int(x) for x in str(row["score"]).split(":"))
            assert legal_completed_set_score(score)
            assert set_score_is_terminal(score)
            assert tiebreak_should_start(score) is False
            expected_next = (
                start_server
                if int(row["games"]) % 2 == 0
                else other_player(start_server)
            )
            assert int(row["next_set_server"]) == expected_next


def test_dynamic_simulator_set_outcomes_share_same_phase5_legality_contract():
    p1_serve = 0.63
    p2_serve = 0.59

    def point_probability(state):
        return p1_serve if state["server"] == 1 else p2_serve

    p1_tb = neutral_tiebreak_win_probability(p1_serve, p2_serve)

    def tiebreak_probability(_state):
        return p1_tb

    for start_server in (1, 2):
        rows = dynamic_set_outcomes(
            point_probability,
            tiebreak_probability,
            start_server=start_server,
            sets_before=(0, 0),
            best_of=3,
        )
        assert math.isclose(sum(float(row["probability"]) for row in rows), 1.0, abs_tol=1e-10)
        for row in rows:
            score = tuple(int(x) for x in str(row["score"]).split(":"))
            assert legal_completed_set_score(score)
            expected_next = (
                start_server
                if int(row["games"]) % 2 == 0
                else other_player(start_server)
            )
            assert int(row["next_set_server"]) == expected_next


def test_state_dict_is_explicit_and_validated():
    payload = state_dict(initial_state(best_of=5, start_server=2))
    assert payload["best_of"] == 5
    assert payload["sets"] == [0, 0]
    assert payload["games"] == [0, 0]
    assert payload["points"] == ["0", "0"]
    assert payload["server"] == 2
    assert payload["terminal"] is False


def test_phase5_gate_closes_only_after_phase4_and_internal_legality_checks():
    report = evaluate_phase5_gate({
        "phase4_complete": True,
        "phase5_ready": True,
    })

    assert report["mode"] == MODE
    assert report["phase5_complete"] is True
    assert report["phase6_ready"] is True
    assert report["status"] == "PHASE5_COMPLETE_LEGAL_TENNIS_STATE_ENGINE"
    assert all(report["internal_contract_checks"].values())
    assert report["production_influence"] is False
    assert report["runtime_switch_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False


def test_phase5_gate_fails_closed_without_phase4():
    report = evaluate_phase5_gate({
        "phase4_complete": False,
        "phase5_ready": False,
    })
    assert report["phase5_complete"] is False
    assert report["phase6_ready"] is False
    assert report["status"] == "PHASE5_GATE_NOT_COMPLETE"
