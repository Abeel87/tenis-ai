from __future__ import annotations

"""Strict provider-backed match context for future Player DNA features.

This module only normalizes fields proven by the metadata audit. It does not
join them into training rows and has no PROD/Symfonia 2.0/PLAYABLE influence.
"""

from datetime import datetime, timezone
from typing import Any

VERSION = "player-dna-match-context-v1"


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _parse_utc(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _ranking(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _player_context(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    player_id = value.get("id")
    if isinstance(player_id, bool) or not isinstance(player_id, int):
        return None
    return {"id": player_id, "ranking": _ranking(value.get("ranking"))}


def resolve_match_context(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    match = payload.get("match")
    if not isinstance(match, dict):
        return None
    players = match.get("players")
    if not isinstance(players, dict):
        return None
    p1 = _player_context(players.get("p1"))
    p2 = _player_context(players.get("p2"))
    scheduled_time = _parse_utc(match.get("scheduled_time"))
    if p1 is None or p2 is None or scheduled_time is None:
        return None

    surface = _text(match.get("surface"))
    tour = _text(match.get("tour"))
    match_format = _text(match.get("format"))
    round_code = _text(match.get("round_code"))
    match_id = match.get("id")

    return {
        "version": VERSION,
        "match_id": match_id if isinstance(match_id, int) and not isinstance(match_id, bool) else None,
        "scheduled_time": scheduled_time,
        "surface": surface.casefold() if surface else None,
        "tour": tour.upper() if tour else None,
        "format": match_format.upper() if match_format else None,
        "round_code": round_code.upper() if round_code else None,
        "indoor": match.get("indoor") if isinstance(match.get("indoor"), bool) else None,
        "is_qualifying": match.get("is_qualifying") if isinstance(match.get("is_qualifying"), bool) else None,
        "p1": p1,
        "p2": p2,
        "provider_backed": True,
        "training_join_enabled": False,
    }
