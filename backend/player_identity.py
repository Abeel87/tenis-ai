from __future__ import annotations

"""Canonical, provider-backed player identity mapping for cached PBP payloads.

The identity gate proved that restored payloads expose match.players.p1/p2 with
stable provider IDs. This module only accepts that explicit structure; it never
falls back to names, ordering heuristics, or fuzzy matching.
"""

from typing import Any

IDENTITY_SCHEMA_VERSION = "pbp-player-identity-v1"


def _player_record(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    player_id = value.get("id")
    name = value.get("name")
    if player_id is None:
        return None
    return {"id": player_id, "name": name if isinstance(name, str) and name.strip() else None}


def player_identity_map(payload: dict[str, Any]) -> dict[int, dict[str, Any]] | None:
    """Return explicit match-side -> stable identity, or None when not provable."""
    match = payload.get("match") if isinstance(payload, dict) else None
    players = match.get("players") if isinstance(match, dict) else None
    if not isinstance(players, dict):
        return None
    p1 = _player_record(players.get("p1"))
    p2 = _player_record(players.get("p2"))
    if p1 is None or p2 is None or p1["id"] == p2["id"]:
        return None
    return {1: p1, 2: p2}


def identity_for_side(payload: dict[str, Any], side: Any) -> dict[str, Any] | None:
    mapping = player_identity_map(payload)
    if mapping is None or side not in (1, 2):
        return None
    return mapping[int(side)]
