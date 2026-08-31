from __future__ import annotations

"""Strict canonical Superbet -> NEURO SHADOW adapter.

Consumes only already-canonical, currently available Superbet selections. It
never changes PLAYABLE/Symphony PROD and never invents a line or probability.
"""

from typing import Any

from backend.neuro_shadow_state_v935 import (
    CANDIDATE_CAPTURE_READY_MARKETS,
    shadow_probability,
)

VERSION = "neuro-shadow-market-adapter-v9.3.5"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False


def _side_for_player(selection: dict[str, Any], match: dict[str, Any]) -> int | None:
    player = str(selection.get("player") or "").strip().casefold()
    p1 = str(match.get("p1") or match.get("participant1Name") or "").strip().casefold()
    p2 = str(match.get("p2") or match.get("participant2Name") or "").strip().casefold()
    if player and p1 and player == p1:
        return 1
    if player and p2 and player == p2:
        return 2
    return None


def _side_for_pick(selection: dict[str, Any], match: dict[str, Any]) -> int | None:
    pick = str(selection.get("pick") or "").strip().casefold()
    p1 = str(match.get("p1") or match.get("participant1Name") or "").strip().casefold()
    p2 = str(match.get("p2") or match.get("participant2Name") or "").strip().casefold()
    if pick and p1 and pick == p1:
        return 1
    if pick and p2 and pick == p2:
        return 2
    return None


def adapt_canonical_selection(match: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any] | None:
    """Return one SHADOW assessment or None when semantics are not exact."""
    if not isinstance(selection, dict):
        return None
    if selection.get("operator_available") is not True:
        return None

    market = str(selection.get("market") or "")
    if market not in CANDIDATE_CAPTURE_READY_MARKETS:
        return None

    pick = str(selection.get("pick") or "").strip().casefold()
    line = selection.get("line")
    kwargs: dict[str, Any] = {}

    if market in {"set2_winner", "set3_winner"}:
        side = _side_for_pick(selection, match)
        if side is None:
            return None
        kwargs["side"] = side
    elif market in {"set2_total", "set3_total"}:
        if selection.get("operator_line_verified") is not True or line is None or pick not in {"over", "under"}:
            return None
        kwargs.update(line=float(line), pick=pick)
    elif market == "player_total_games":
        side = _side_for_player(selection, match)
        if side is None or selection.get("operator_line_verified") is not True or line is None or pick not in {"over", "under"}:
            return None
        kwargs.update(side=side, line=float(line), pick=pick)
    elif market == "match_game_handicap":
        side = _side_for_pick(selection, match)
        if side is None or selection.get("operator_line_verified") is not True or line is None:
            return None
        kwargs.update(side=side, line=float(line))
    else:
        return None

    probability = shadow_probability(match, market, **kwargs)
    if probability is None:
        return None

    return {
        "market": market,
        "pick": selection.get("pick"),
        "line": line,
        "player": selection.get("player"),
        "probability": float(probability),
        "mode": "SHADOW",
        "operator": "Superbet",
        "operator_available": True,
        "operator_playable": False,
        "production_influence": False,
        "playable_influence": False,
        "source_market_id": selection.get("market_id"),
        "source_outcome_id": selection.get("outcome_id"),
        "adapter_version": VERSION,
    }


def adapt_market_context(match: dict[str, Any], market_context: dict[str, Any]) -> list[dict[str, Any]]:
    """Adapt canonical_selections from the existing Superbet market context."""
    if not isinstance(market_context, dict):
        return []
    out = []
    for selection in market_context.get("canonical_selections") or []:
        adapted = adapt_canonical_selection(match, selection)
        if adapted is not None:
            out.append(adapted)
    return out
