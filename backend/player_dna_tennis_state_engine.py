from __future__ import annotations

"""Canonical legal tennis state machine for Player DNA Phase 5.

The engine is probability-free. It answers only one question: given a legal
pre-point tennis state and the side that wins the next point, what is the unique
legal next state?

Current format contract:
- standard advantage games;
- 7-point tiebreak at 6:6 in every set, win by two;
- BO3 / BO5;
- continuous service order across games and sets;
- official tiebreak service order: first server serves one point, then service
  alternates every two points; the tiebreak first server receives in the first
  game of the next set.

This module is SHADOW infrastructure. It does not alter PROD, Symfonia 2 or
Superbet PLAYABLE by itself.
"""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_phase5_tennis_state_engine.json"
PHASE4_REPORT = ROOT / "frontend" / "data" / "player_dna_phase4_point_probability_engine.json"

VERSION = "player-dna-tennis-state-engine-v1"
MODE = "SHADOW_PHASE5_LEGAL_TENNIS_STATE_ENGINE"
STANDARD_POINTS = ("0", "15", "30", "40", "A")


def other_player(player: int) -> int:
    if player not in (1, 2):
        raise ValueError("player must be 1 or 2")
    return 2 if player == 1 else 1


def sets_needed(best_of: int) -> int:
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    return best_of // 2 + 1


def tiebreak_should_start(games: tuple[int, int]) -> bool:
    return games == (6, 6)


def set_score_is_terminal(games: tuple[int, int]) -> bool:
    g1, g2 = games
    if min(g1, g2) < 0:
        return False
    if games in ((7, 6), (6, 7)):
        return True
    return (g1 >= 6 or g2 >= 6) and abs(g1 - g2) >= 2


def legal_completed_set_score(score: tuple[int, int]) -> bool:
    g1, g2 = score
    if min(g1, g2) < 0 or g1 == g2:
        return False
    if score in ((7, 6), (6, 7)):
        return True
    winner = max(g1, g2)
    loser = min(g1, g2)
    if winner == 6:
        return loser <= 4
    if winner == 7:
        return loser == 5
    return False


def tiebreak_server(first_server: int, points_played: int) -> int:
    """Server for the next tiebreak point after points_played completed points."""
    if first_server not in (1, 2):
        raise ValueError("first_server must be 1 or 2")
    if isinstance(points_played, bool) or not isinstance(points_played, int) or points_played < 0:
        raise ValueError("points_played must be a non-negative integer")
    if points_played == 0:
        return first_server
    block = (points_played - 1) // 2
    return other_player(first_server) if block % 2 == 0 else first_server


def _standard_points_valid(points: tuple[str, str]) -> bool:
    if len(points) != 2 or any(value not in STANDARD_POINTS for value in points):
        return False
    a, b = points
    if a == "A" or b == "A":
        return (a == "A" and b == "40") or (b == "A" and a == "40")
    return True


def _tiebreak_points(points: tuple[str, str]) -> tuple[int, int] | None:
    if len(points) != 2:
        return None
    try:
        a, b = int(points[0]), int(points[1])
    except (TypeError, ValueError):
        return None
    if a < 0 or b < 0:
        return None
    return a, b


@dataclass(frozen=True)
class TennisState:
    best_of: int
    sets: tuple[int, int]
    games: tuple[int, int]
    points: tuple[str, str]
    server: int
    set_start_server: int
    is_tiebreak: bool = False
    tiebreak_first_server: int | None = None
    completed_sets: tuple[tuple[int, int], ...] = ()
    match_winner: int | None = None

    @property
    def terminal(self) -> bool:
        return self.match_winner in (1, 2)


def initial_state(*, best_of: int, start_server: int) -> TennisState:
    state = TennisState(
        best_of=best_of,
        sets=(0, 0),
        games=(0, 0),
        points=("0", "0"),
        server=start_server,
        set_start_server=start_server,
    )
    validate_state(state)
    return state


def validate_state(state: TennisState) -> None:
    needed = sets_needed(state.best_of)
    if state.server not in (1, 2) or state.set_start_server not in (1, 2):
        raise ValueError("server fields must be player 1 or 2")

    s1, s2 = state.sets
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in state.sets):
        raise ValueError("sets must contain non-negative integers")
    if s1 > needed or s2 > needed or (s1 == needed and s2 == needed):
        raise ValueError("impossible match set score")

    if len(state.completed_sets) != s1 + s2:
        raise ValueError("completed set history length must equal sets won")
    p1_completed = 0
    p2_completed = 0
    for score in state.completed_sets:
        if not legal_completed_set_score(score):
            raise ValueError(f"illegal completed set score: {score}")
        if score[0] > score[1]:
            p1_completed += 1
        else:
            p2_completed += 1
    if (p1_completed, p2_completed) != state.sets:
        raise ValueError("completed set winners disagree with match set score")

    if state.match_winner is None:
        if s1 >= needed or s2 >= needed:
            raise ValueError("terminal set score requires match_winner")
    else:
        if state.match_winner not in (1, 2):
            raise ValueError("match_winner must be 1, 2 or None")
        expected = 1 if s1 == needed and s2 < needed else 2 if s2 == needed and s1 < needed else None
        if expected != state.match_winner:
            raise ValueError("match_winner disagrees with terminal set score")
        if state.games != (0, 0) or state.points != ("0", "0") or state.is_tiebreak:
            raise ValueError("terminal match must have reset in-set state")

    g1, g2 = state.games
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in state.games):
        raise ValueError("games must contain non-negative integers")

    if state.terminal:
        if state.tiebreak_first_server is not None:
            raise ValueError("terminal match cannot retain tiebreak marker")
        return

    if state.is_tiebreak:
        if state.games != (6, 6):
            raise ValueError("tiebreak state requires 6:6 games")
        if state.tiebreak_first_server not in (1, 2):
            raise ValueError("tiebreak state requires first server")
        if state.tiebreak_first_server != state.set_start_server:
            raise ValueError("6:6 tiebreak first server must equal set first server")
        numeric = _tiebreak_points(state.points)
        if numeric is None:
            raise ValueError("tiebreak points must be non-negative integers")
        if max(numeric) >= 7 and abs(numeric[0] - numeric[1]) >= 2:
            raise ValueError("completed tiebreak cannot remain live")
        expected_server = tiebreak_server(
            state.tiebreak_first_server,
            numeric[0] + numeric[1],
        )
        if state.server != expected_server:
            raise ValueError("tiebreak server order is impossible")
        return

    if state.tiebreak_first_server is not None:
        raise ValueError("non-tiebreak state cannot retain tiebreak first server")
    if tiebreak_should_start(state.games):
        raise ValueError("6:6 must be represented as a live tiebreak")
    if g1 > 6 or g2 > 6 or set_score_is_terminal(state.games):
        raise ValueError("completed set score cannot remain live")
    if not _standard_points_valid(state.points):
        raise ValueError("illegal standard-game point score")

    expected_server = (
        state.set_start_server
        if (g1 + g2) % 2 == 0
        else other_player(state.set_start_server)
    )
    if state.server != expected_server:
        raise ValueError("standard-game server order is impossible")


def _advance_standard_points(
    points: tuple[str, str],
    winner: int,
) -> tuple[tuple[str, str] | None, bool]:
    if not _standard_points_valid(points):
        raise ValueError("illegal standard point state")
    if winner not in (1, 2):
        raise ValueError("winner must be 1 or 2")

    w = winner - 1
    l = 1 - w
    values = [points[0], points[1]]
    wp = values[w]
    lp = values[l]
    ladder = {"0": "15", "15": "30", "30": "40"}

    if wp in ladder:
        values[w] = ladder[wp]
        return (values[0], values[1]), False
    if wp == "A":
        return None, True
    if wp == "40":
        if lp in ("0", "15", "30"):
            return None, True
        if lp == "40":
            values[w] = "A"
            return (values[0], values[1]), False
        if lp == "A":
            values[l] = "40"
            return (values[0], values[1]), False
    raise ValueError("standard point transition is impossible")


def _finish_set(
    state: TennisState,
    *,
    set_winner: int,
    final_games: tuple[int, int],
    next_set_server: int,
) -> TennisState:
    if not legal_completed_set_score(final_games):
        raise ValueError(f"cannot finish set with illegal score {final_games}")
    new_sets = list(state.sets)
    new_sets[set_winner - 1] += 1
    completed = (*state.completed_sets, final_games)
    needed = sets_needed(state.best_of)
    match_winner = set_winner if new_sets[set_winner - 1] == needed else None

    out = TennisState(
        best_of=state.best_of,
        sets=(new_sets[0], new_sets[1]),
        games=(0, 0),
        points=("0", "0"),
        server=next_set_server,
        set_start_server=next_set_server,
        is_tiebreak=False,
        tiebreak_first_server=None,
        completed_sets=completed,
        match_winner=match_winner,
    )
    validate_state(out)
    return out


def transition_point(state: TennisState, winner: int) -> TennisState:
    """Apply exactly one point winner to a legal state."""
    validate_state(state)
    if state.terminal:
        raise ValueError("cannot transition a terminal match")
    if winner not in (1, 2):
        raise ValueError("winner must be 1 or 2")

    if state.is_tiebreak:
        numeric = _tiebreak_points(state.points)
        assert numeric is not None
        points = [numeric[0], numeric[1]]
        points[winner - 1] += 1
        if points[winner - 1] >= 7 and points[winner - 1] - points[other_player(winner) - 1] >= 2:
            final_games = (7, 6) if winner == 1 else (6, 7)
            assert state.tiebreak_first_server in (1, 2)
            return _finish_set(
                state,
                set_winner=winner,
                final_games=final_games,
                next_set_server=other_player(state.tiebreak_first_server),
            )

        assert state.tiebreak_first_server in (1, 2)
        out = replace(
            state,
            points=(str(points[0]), str(points[1])),
            server=tiebreak_server(
                state.tiebreak_first_server,
                points[0] + points[1],
            ),
        )
        validate_state(out)
        return out

    next_points, game_won = _advance_standard_points(state.points, winner)
    if not game_won:
        assert next_points is not None
        out = replace(state, points=next_points)
        validate_state(out)
        return out

    games = [state.games[0], state.games[1]]
    games[winner - 1] += 1
    next_server = other_player(state.server)
    new_games = (games[0], games[1])

    if set_score_is_terminal(new_games):
        return _finish_set(
            state,
            set_winner=winner,
            final_games=new_games,
            next_set_server=next_server,
        )

    if tiebreak_should_start(new_games):
        out = replace(
            state,
            games=new_games,
            points=("0", "0"),
            server=next_server,
            is_tiebreak=True,
            tiebreak_first_server=next_server,
        )
        validate_state(out)
        return out

    out = replace(
        state,
        games=new_games,
        points=("0", "0"),
        server=next_server,
    )
    validate_state(out)
    return out


def state_dict(state: TennisState) -> dict[str, Any]:
    validate_state(state)
    payload = asdict(state)
    payload["sets"] = list(state.sets)
    payload["games"] = list(state.games)
    payload["points"] = list(state.points)
    payload["completed_sets"] = [list(score) for score in state.completed_sets]
    payload["terminal"] = state.terminal
    return payload


def _internal_contract_checks() -> dict[str, bool]:
    # Standard deuce/advantage.
    deuce = TennisState(
        best_of=3,
        sets=(0, 0),
        games=(0, 0),
        points=("40", "40"),
        server=1,
        set_start_server=1,
    )
    advantage = transition_point(deuce, 1)
    deuce_again = transition_point(advantage, 2)

    # Game -> 6:6 -> tiebreak.
    at_5_6 = TennisState(
        best_of=3,
        sets=(0, 0),
        games=(5, 6),
        points=("40", "0"),
        server=2,
        set_start_server=1,
    )
    tiebreak = transition_point(at_5_6, 1)

    # Tiebreak finish and next-set first server.
    tb_6_5 = replace(
        tiebreak,
        points=("6", "5"),
        server=tiebreak_server(tiebreak.tiebreak_first_server or 1, 11),
    )
    tb_6_6 = transition_point(tb_6_5, 2)
    tb_7_6 = transition_point(tb_6_6, 1)
    set_finished = transition_point(tb_7_6, 1)

    # BO5 terminality.
    bo5 = TennisState(
        best_of=5,
        sets=(2, 0),
        games=(5, 0),
        points=("40", "0"),
        server=2,
        set_start_server=1,
        completed_sets=((6, 4), (7, 5)),
    )
    terminal = transition_point(bo5, 1)

    return {
        "deuce_advantage_round_trip": advantage.points == ("A", "40")
        and deuce_again.points == ("40", "40"),
        "six_all_enters_tiebreak": tiebreak.is_tiebreak
        and tiebreak.games == (6, 6),
        "tiebreak_next_set_server_correct": set_finished.completed_sets[-1] == (7, 6)
        and set_finished.set_start_server == other_player(tiebreak.tiebreak_first_server or 1),
        "bo5_terminates_at_three_sets": terminal.match_winner == 1
        and terminal.sets == (3, 0),
    }


def evaluate_phase5_gate(phase4: dict[str, Any]) -> dict[str, Any]:
    checks = _internal_contract_checks()
    phase4_ready = bool(
        phase4.get("phase4_complete") is True
        and phase4.get("phase5_ready") is True
    )
    phase5_complete = phase4_ready and all(checks.values())

    return {
        "version": VERSION,
        "mode": MODE,
        "phase": "PHASE_5_GAME_SET_MATCH_ENGINE",
        "status": (
            "PHASE5_COMPLETE_LEGAL_TENNIS_STATE_ENGINE"
            if phase5_complete
            else "PHASE5_GATE_NOT_COMPLETE"
        ),
        "phase5_complete": phase5_complete,
        "phase6_ready": phase5_complete,
        "phase4_ready": phase4_ready,
        "format_contract": {
            "best_of": [3, 5],
            "standard_advantage_games": True,
            "tiebreak_at_six_all_every_set": True,
            "tiebreak_first_to_7_win_by_2": True,
            "service_order_continuous_across_games_and_sets": True,
            "official_tiebreak_service_rotation": True,
            "tiebreak_first_server_receives_first_game_next_set": True,
        },
        "internal_contract_checks": checks,
        "production_influence": False,
        "runtime_switch_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "contract": {
            "probability_free_state_machine": True,
            "one_point_transition_only": True,
            "illegal_states_fail_closed": True,
            "terminal_match_rejects_further_points": True,
            "completed_set_scores_are_explicit": True,
            "serve_order_is_state_invariant": True,
            "simulator_legal_predicates_share_this_module": True,
            "phase5_completion_does_not_promote_runtime_or_prod": True,
        },
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def build() -> dict[str, Any]:
    report = evaluate_phase5_gate(_read_json(PHASE4_REPORT))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report["version"],
        "status": report["status"],
        "phase5_complete": report["phase5_complete"],
        "phase6_ready": report["phase6_ready"],
        "checks": report["internal_contract_checks"],
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
