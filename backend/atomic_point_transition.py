from __future__ import annotations

"""Conservative validator for one observed tennis point between PBP snapshots.

The validator is intentionally strict.  It accepts only transitions that can be
proved to represent exactly one point from the observed score states.  Compressed,
ambiguous, missing-winner and not-yet-proven set-boundary transitions stay out of
point-level training.
"""

from typing import Any

VALIDATOR_VERSION = "atomic-point-transition-v1"


def _winner(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value in (1, 2):
        return value
    return None


def point_token(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    token = str(value).strip().upper()
    if token == "AD":
        token = "A"
    return token or None


def standard_point_stage(token: str | None) -> int | None:
    return {"0": 0, "15": 1, "30": 2, "40": 3, "A": 4}.get(token or "")


def game_point_flags(
    server_token: str | None,
    receiver_token: str | None,
    is_tiebreak: bool,
) -> tuple[int | None, int | None, int | None, int | None, int | None]:
    """Return server game-point, receiver game-point, deuce and advantage flags."""
    if is_tiebreak:
        try:
            server_score = int(server_token) if server_token is not None else None
            receiver_score = int(receiver_token) if receiver_token is not None else None
        except ValueError:
            server_score = receiver_score = None
        if server_score is None or receiver_score is None:
            return None, None, None, None, None
        server_gp = int(server_score >= 6 and server_score - receiver_score >= 1)
        receiver_gp = int(receiver_score >= 6 and receiver_score - server_score >= 1)
        return server_gp, receiver_gp, 0, 0, 0

    if server_token is None or receiver_token is None:
        return None, None, None, None, None
    server_gp = int(
        (server_token == "40" and receiver_token in {"0", "15", "30"})
        or (server_token == "A" and receiver_token == "40")
    )
    receiver_gp = int(
        (receiver_token == "40" and server_token in {"0", "15", "30"})
        or (receiver_token == "A" and server_token == "40")
    )
    deuce = int(server_token == "40" and receiver_token == "40")
    server_adv = int(server_token == "A" and receiver_token == "40")
    receiver_adv = int(receiver_token == "A" and server_token == "40")
    return server_gp, receiver_gp, deuce, server_adv, receiver_adv


def _point_pair(row: dict[str, Any]) -> tuple[str, str] | None:
    value = row.get("points")
    if not isinstance(value, list) or len(value) != 2:
        return None
    a, b = point_token(value[0]), point_token(value[1])
    return (a, b) if a is not None and b is not None else None


def _number(token: str | None) -> int | None:
    if token is None:
        return None
    try:
        return int(token)
    except (TypeError, ValueError):
        return None


def _current_score_pair(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    out: list[int] = []
    for side in value:
        candidate = side[-1] if isinstance(side, list) and side else side
        if isinstance(candidate, bool):
            return None
        try:
            out.append(int(candidate))
        except (TypeError, ValueError):
            return None
    return out[0], out[1]


def _standard_next(points: tuple[str, str], winner: int) -> tuple[str, str] | None:
    w = winner - 1
    l = 1 - w
    p = [points[0], points[1]]
    wp, lp = p[w], p[l]
    ladder = {"0": "15", "15": "30", "30": "40"}

    if wp in ladder:
        p[w] = ladder[wp]
        return p[0], p[1]
    if wp == "40" and lp == "40":
        p[w] = "A"
        return p[0], p[1]
    if wp == "40" and lp == "A":
        p[l] = "40"
        return p[0], p[1]
    # 40 vs <=30 or A vs 40 means the game ends on this point.
    return None


def _standard_game_winning_state(points: tuple[str, str], winner: int) -> bool:
    winner_index = winner - 1
    loser_index = 1 - winner_index
    server_gp, _, _, _, _ = game_point_flags(
        points[winner_index],
        points[loser_index],
        False,
    )
    return server_gp == 1


def _tiebreak_next(points: tuple[str, str], winner: int) -> tuple[str, str] | None:
    nums = [_number(points[0]), _number(points[1])]
    if nums[0] is None or nums[1] is None:
        return None
    nums[winner - 1] += 1
    return str(nums[0]), str(nums[1])


def _tiebreak_winning_state(points: tuple[str, str], winner: int) -> bool:
    nums = [_number(points[0]), _number(points[1])]
    if nums[0] is None or nums[1] is None:
        return False
    nums[winner - 1] += 1
    return nums[winner - 1] >= 7 and nums[winner - 1] - nums[2 - winner] >= 2


def classify_atomic_transition(prev: dict[str, Any], cur: dict[str, Any], point_winner: Any = None) -> dict[str, Any]:
    """Return a strict atomicity decision and diagnostic reason."""
    winner = _winner(point_winner if point_winner is not None else cur.get("point_winner"))
    if winner is None:
        return {"atomic_transition": False, "reason": "winner_missing_or_invalid", "validator_version": VALIDATOR_VERSION}

    before = _point_pair(prev)
    after = _point_pair(cur)
    if before is None or after is None:
        return {"atomic_transition": False, "reason": "point_score_missing_or_invalid", "validator_version": VALIDATOR_VERSION}

    sets_changed = prev.get("sets") != cur.get("sets")
    games_changed = prev.get("games") != cur.get("games")
    tiebreak = bool(prev.get("is_tiebreak")) or bool(cur.get("is_tiebreak"))

    if sets_changed:
        return {"atomic_transition": False, "reason": "set_boundary_not_yet_proven", "validator_version": VALIDATOR_VERSION}

    if games_changed:
        before_games = _current_score_pair(prev.get("games"))
        after_games = _current_score_pair(cur.get("games"))
        if before_games is None or after_games is None:
            return {"atomic_transition": False, "reason": "game_score_shape_unproven", "validator_version": VALIDATOR_VERSION}
        expected_games = list(before_games)
        expected_games[winner - 1] += 1
        if tuple(expected_games) != after_games:
            return {"atomic_transition": False, "reason": "game_score_jump_or_wrong_winner", "validator_version": VALIDATOR_VERSION}
        if after != ("0", "0"):
            return {"atomic_transition": False, "reason": "game_boundary_points_not_reset", "validator_version": VALIDATOR_VERSION}
        won_game = _tiebreak_winning_state(before, winner) if tiebreak else _standard_game_winning_state(before, winner)
        return {
            "atomic_transition": bool(won_game),
            "reason": "atomic_game_boundary" if won_game else "game_boundary_requires_missing_points",
            "validator_version": VALIDATOR_VERSION,
        }

    expected = _tiebreak_next(before, winner) if tiebreak else _standard_next(before, winner)
    if expected is None:
        return {"atomic_transition": False, "reason": "transition_should_end_game_or_is_invalid", "validator_version": VALIDATOR_VERSION}
    if expected != after:
        return {"atomic_transition": False, "reason": "compressed_or_wrong_point_step", "validator_version": VALIDATOR_VERSION}
    return {"atomic_transition": True, "reason": "atomic_point_step", "validator_version": VALIDATOR_VERSION}
