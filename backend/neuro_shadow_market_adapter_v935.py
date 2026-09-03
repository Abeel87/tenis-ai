from __future__ import annotations

"""Strict canonical Superbet -> NEURO SHADOW adapter.

Consumes only already-canonical, currently available Superbet selections. It
never changes PLAYABLE/Symphony PROD and never invents a line or probability.
"""

from typing import Any

from backend.neuro_shadow_features_v935 import (
    _name_key,
    extract_feature_snapshot,
    model_signal_index,
    selection_signature,
)
from backend.neuro_shadow_state_v935 import (
    CANDIDATE_CAPTURE_READY_MARKETS,
    build_shadow_outcomes,
    shadow_probability,
)

VERSION = "neuro-shadow-market-adapter-v9.3.6"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

YES_NO_MARKETS = frozenset({
    "set1_tiebreak",
    "any_set_to_nil",
    "p1_exactly_1_set",
    "p1_exactly_2_sets",
    "p2_exactly_1_set",
    "p2_exactly_2_sets",
    "p1_wins_a_set",
    "p2_wins_a_set",
})
HANDICAP_MARKETS = frozenset({
    "match_game_handicap",
    "set1_game_handicap",
    "set2_game_handicap",
    "set_handicap",
})
PARITY_MARKETS = frozenset({
    "match_games_parity",
    "set1_games_parity",
    "set2_games_parity",
})


def _side_for_player(selection: dict[str, Any], match: dict[str, Any]) -> int | None:
    player = _name_key(selection.get("player"))
    p1 = _name_key(match.get("p1") or match.get("participant1Name"))
    p2 = _name_key(match.get("p2") or match.get("participant2Name"))
    if player and p1 and player == p1:
        return 1
    if player and p2 and player == p2:
        return 2
    return None


def _side_for_pick(selection: dict[str, Any], match: dict[str, Any]) -> int | None:
    pick = _name_key(selection.get("pick"))
    p1 = _name_key(match.get("p1") or match.get("participant1Name"))
    p2 = _name_key(match.get("p2") or match.get("participant2Name"))
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
    model_signal: dict[str, Any] | None = None,
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
    elif market in HANDICAP_MARKETS:
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
    elif market in PARITY_MARKETS:
        if pick not in {"odd", "even", "nieparzyste", "nieparzysta", "parzyste", "parzysta"}:
            return None
        kwargs["pick"] = pick
    else:
        return None

    probability = shadow_probability(match, market, outcomes=outcomes, **kwargs)
    if probability is None:
        return None
    probability = float(probability)

    return {
        "market": market,
        "pick": selection.get("pick"),
        "line": line,
        "player": selection.get("player"),
        "probability": probability,
        "probability_kind": "SHADOW_STATE_P_HIT",
        "source_model": "state_distribution",
        "feature_snapshot": extract_feature_snapshot(
            match,
            selection,
            state_probability=probability,
            model_signal=model_signal,
        ),
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
    model_index = model_signal_index(market_context)
    out = []
    for selection in selections:
        adapted = adapt_canonical_selection(
            match,
            selection,
            outcomes=outcomes,
            model_signal=model_index.get(selection_signature(selection)),
        )
        if adapted is not None:
            out.append(adapted)
    return out