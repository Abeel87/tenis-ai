from __future__ import annotations

"""iNeed$ market-scope contract.

This module only limits which already-final Symphony PLAYABLE signals may enter
the iNeed$ SHADOW bankroll layer. It does not alter model probability, Symphony,
PLAYABLE, settlement, risk, Kelly, thresholds, or stake calculations.
"""

from typing import Any

ALLOWED_MARKET_SCOPE = (
    {"market": "set1_winner"},
    {"market": "set1_total", "pick": "over"},
    {"market": "game_state", "checkpoint": 6},
)


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def signal_allowed(signal: dict) -> bool:
    if not isinstance(signal, dict):
        return False
    market = _norm(signal.get("market"))
    if market == "set1_winner":
        return True
    if market == "set1_total":
        return _norm(signal.get("pick")) == "over"
    if market == "game_state":
        try:
            return int(signal.get("checkpoint") or 0) == 6
        except (TypeError, ValueError):
            return False
    return False


def filter_results(results: list[dict]) -> tuple[list[dict], dict]:
    """Return shallow-copied PLAYABLE rows containing only in-scope signals."""
    filtered: list[dict] = []
    matches_seen = 0
    matches_kept = 0
    signals_seen = 0
    signals_kept = 0

    for match in results if isinstance(results, list) else []:
        if not isinstance(match, dict):
            continue
        layer = match.get("symphony2_playable")
        if not isinstance(layer, dict):
            continue
        matches_seen += 1
        signals = [row for row in (layer.get("signals") or []) if isinstance(row, dict)]
        signals_seen += len(signals)
        kept = [row for row in signals if signal_allowed(row)]
        signals_kept += len(kept)
        if not kept:
            continue
        matches_kept += 1
        copied = dict(match)
        copied_layer = dict(layer)
        copied_layer["signals"] = kept
        copied_layer["playable_count"] = len(kept)
        copied["symphony2_playable"] = copied_layer
        filtered.append(copied)

    return filtered, {
        "contract": "INEED_SCOPE_SET1_WINNER_SET1_OVER_GAME_STATE_6",
        "matches_seen": matches_seen,
        "matches_kept": matches_kept,
        "signals_seen": signals_seen,
        "signals_kept": signals_kept,
        "signals_filtered": max(0, signals_seen - signals_kept),
        "allowed_market_scope": [dict(row) for row in ALLOWED_MARKET_SCOPE],
    }
