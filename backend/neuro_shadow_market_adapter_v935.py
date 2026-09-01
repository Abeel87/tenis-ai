from __future__ import annotations

"""Strict canonical Superbet -> NEURO SHADOW adapter.

Consumes only already-canonical, currently available Superbet selections. It
never changes PLAYABLE/Symphony PROD and never invents a line or probability.
"""

from typing import Any

from backend.neuro_shadow_state_v935 import (
    CANDIDATE_CAPTURE_READY_MARKETS,
    build_shadow_outcomes,
    shadow_probability,
)

VERSION = "neuro-shadow-market-adapter-v9.3.5"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

YES_NO_MARKETS = frozenset({
    "set1_tiebreak",
    "p1_exactly_1_set",
    "p1_exactly_2_sets",
    "p2_exactly_1_set",
    "p2_exactly_2_sets",
    "p1_wins_a_set",
    "p2_wins_a_set",
})


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


def adapt_canonical_selection(
    match: dict[str, Any],
    selection: dict[str, Any],
    *,
    outcomes: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
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
    elif market == "set2_exact_score":
        if not pick or ":" not in pick.replace("-", ":"):
            return None
        kwargs["pick"] = pick
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
    elif market == "exact_sets":
        try:
            int(float(pick))
        except (TypeError, ValueError):
            return None
        kwargs["pick"] = pick
    elif market in YES_NO_MARKETS:
        if pick not in {"yes", "no", "tak", "nie", "true", "false", "1", "0"}:
            return None
        kwargs["pick"] = pick
    else:
        return None

    probability = shadow_probability(match, market, outcomes=outcomes, **kwargs)
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
    """Adapt all canonical selections while building the costly state only once."""
    if not isinstance(market_context, dict):
        return []
    selections = [
        row for row in (market_context.get("canonical_selections") or [])
        if isinstance(row, dict) and row.get("operator_available") is True
        and str(row.get("market") or "") in CANDIDATE_CAPTURE_READY_MARKETS
    ]
    if not selections:
        return []
    outcomes = build_shadow_outcomes(match)
    if not outcomes:
        return []
    out = []
    for selection in selections:
        adapted = adapt_canonical_selection(match, selection, outcomes=outcomes)
        if adapted is not None:
            out.append(adapted)
    return out
