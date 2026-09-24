from __future__ import annotations

"""iNeed$ market-scope contract.

This module only limits which already-final Symphony PLAYABLE signals may enter
the iNeed$ SHADOW bankroll layer. It does not alter model probability, Symphony,
PLAYABLE, settlement, risk, Kelly, thresholds, or stake calculations.
"""

from typing import Any

ALLOWED_MARKET_SCOPE = ({"market": "match_winner"},)
BUILDER_MARKET_SCOPE = (
    {"market": "set1_winner"},
    {"market": "set1_total", "pick": "over"},
    {"market": "game_state", "checkpoint": 6, "condition": "leader_after_6_games"},
)


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def signal_allowed(signal: dict) -> bool:
    if not isinstance(signal, dict):
        return False
    return _norm(signal.get("market")) == "match_winner" and bool(_norm(signal.get("pick")))


def _builder_signal_allowed(signal: dict) -> bool:
    market = _norm(signal.get("market"))
    if market == "set1_winner":
        return True
    if market == "set1_total":
        return _norm(signal.get("pick")) == "over"
    if market != "game_state":
        return False
    try:
        checkpoint = int(signal.get("checkpoint") or 0)
        left, right = (int(x) for x in _norm(signal.get("pick")).split(":"))
    except (TypeError, ValueError):
        return False
    return checkpoint == 6 and left >= 0 and right >= 0 and left + right == 6 and left != right


def filter_results(results: list[dict], *, economic_unit: str = "V1_SINGLE_BET") -> tuple[list[dict], dict]:
    """Return iNeed-only shallow copies with out-of-scope signals removed.

    Final PLAYABLE metadata (including ``playable_count``) is preserved verbatim.
    The count of signals actually admitted to iNeed$ lives only in the returned
    diagnostics, so the adapter never rewrites Symphony's final composition
    semantics.
    """
    filtered: list[dict] = []
    matches_seen = 0
    matches_kept = 0
    signals_seen = 0
    signals_kept = 0
    if economic_unit == "V1_SINGLE_BET":
        allowed = signal_allowed
        market_scope = ALLOWED_MARKET_SCOPE
        contract = "INEED_SCOPE_MATCH_WINNER_ONLY"
    elif economic_unit == "BET_BUILDER_COMPOSITION":
        allowed = _builder_signal_allowed
        market_scope = BUILDER_MARKET_SCOPE
        contract = "INEED_BUILDER_SCOPE_SET1_WINNER_SET1_OVER_LEADER_AFTER_6"
    else:
        raise ValueError("Unknown iNeed economic unit")

    for match in results if isinstance(results, list) else []:
        if not isinstance(match, dict):
            continue
        layer = match.get("symphony2_playable")
        if not isinstance(layer, dict):
            continue
        matches_seen += 1
        signals = [row for row in (layer.get("signals") or []) if isinstance(row, dict)]
        signals_seen += len(signals)
        kept = [row for row in signals if allowed(row)]
        signals_kept += len(kept)
        if not kept:
            continue
        matches_kept += 1
        copied = dict(match)
        copied_layer = dict(layer)
        copied_layer["signals"] = kept
        copied["symphony2_playable"] = copied_layer
        filtered.append(copied)

    return filtered, {
        "contract": contract,
        "matches_seen": matches_seen,
        "matches_kept": matches_kept,
        "signals_seen": signals_seen,
        "signals_kept": signals_kept,
        "signals_filtered": max(0, signals_seen - signals_kept),
        "allowed_market_scope": [dict(row) for row in market_scope],
    }
