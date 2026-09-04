from __future__ import annotations

"""Canonical point-event projection for cached PBP tapes.

Empirical audit of 2,974 cached matches shows provider rows behave as post-point
snapshots: score fields in the current row reflect the just-completed point and
``point_winner`` belongs to that transition.  At game boundaries ``server`` may
already switch to the next game's server, so the server for the completed point
must preferentially come from the previous row.

This module is SHADOW/data-foundation only.  It does not feed PROD, Symfonia or
Superbet PLAYABLE.
"""

from typing import Any

try:
    from backend.atomic_point_transition import classify_atomic_transition
except ModuleNotFoundError:  # direct execution compatibility
    from atomic_point_transition import classify_atomic_transition

SCHEMA_VERSION = "canonical-point-event-v2"
ORDERING_AUTHORITY = "provider_sequence_clean"
TIMESTAMP_ROLE = "metadata_only_no_reordering"


def _player(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value in (1, 2):
        return value
    return None


def _copy_score(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sets": row.get("sets"),
        "games": row.get("games"),
        "points": row.get("points"),
    }


def _score_signature(row: dict[str, Any]) -> tuple[str, str, str]:
    return (repr(row.get("sets")), repr(row.get("games")), repr(row.get("points")))


def _transition_kind(prev: dict[str, Any], cur: dict[str, Any]) -> str:
    if _score_signature(prev) == _score_signature(cur):
        return "same_score"
    if prev.get("sets") != cur.get("sets"):
        return "set_score_changed"
    if prev.get("games") != cur.get("games"):
        return "game_score_changed"
    return "point_score_changed"


def _server_for_completed_point(prev: dict[str, Any], cur: dict[str, Any], kind: str) -> tuple[int | None, str]:
    """Resolve server without using next-game server at a game boundary."""
    prev_server = _player(prev.get("server"))
    cur_server = _player(cur.get("server"))
    if prev_server is not None:
        return prev_server, "previous_row"
    if kind == "point_score_changed" and cur_server is not None:
        return cur_server, "current_row_fallback"
    return None, "unknown"


def canonical_point_events(payload: dict[str, Any] | None, match_id: Any = None) -> list[dict[str, Any]]:
    """Project consecutive provider snapshots into conservative point events.

    Only transitions with a changed tennis score become events.  The first raw
    row cannot become a canonical event because there is no observed pre-point
    state. Missing winners/servers remain missing and atomic trainability is
    granted only when the score transition proves exactly one point.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("tape"), list):
        return []
    rows = [row for row in payload["tape"] if isinstance(row, dict)]
    out: list[dict[str, Any]] = []

    for index in range(1, len(rows)):
        prev, cur = rows[index - 1], rows[index]
        kind = _transition_kind(prev, cur)
        if kind == "same_score":
            continue

        winner = _player(cur.get("point_winner"))
        server, server_source = _server_for_completed_point(prev, cur, kind)
        receiver = 3 - server if server in (1, 2) else None
        observed_winner = winner is not None
        observed_server = server is not None
        atomic = classify_atomic_transition(prev, cur, point_winner=winner)
        atomic_ok = bool(atomic.get("atomic_transition"))

        out.append({
            "schema_version": SCHEMA_VERSION,
            "match_id": match_id,
            "event_index": len(out),
            "ordering_authority": ORDERING_AUTHORITY,
            "timestamp_role": TIMESTAMP_ROLE,
            "provider_row_order_preserved": True,
            "row_index_before": index - 1,
            "row_index_after": index,
            "state_semantics": "before=previous_row; after=current_row; current_point_winner=completed_point",
            "transition_kind": kind,
            "score_before": _copy_score(prev),
            "score_after": _copy_score(cur),
            "point_winner": winner,
            "server": server,
            "receiver": receiver,
            "server_source": server_source,
            "is_tiebreak_before": bool(prev.get("is_tiebreak")),
            "is_tiebreak_after": bool(cur.get("is_tiebreak")),
            "timestamp_after": cur.get("timestamp"),
            "point_source": (payload.get("meta") or {}).get("point_source") if isinstance(payload.get("meta"), dict) else None,
            "quality": {
                "winner_observed": observed_winner,
                "server_observed": observed_server,
                "trainable_basic": observed_winner and observed_server,
                "atomic_transition": atomic_ok,
                "atomic_reason": atomic.get("reason"),
                "atomic_validator_version": atomic.get("validator_version"),
                "trainable_point": observed_winner and observed_server and atomic_ok,
                "winner_reconstructed": False,
                "server_reconstructed": False,
            },
            "raw_before": dict(prev),
            "raw_after": dict(cur),
        })
    return out
