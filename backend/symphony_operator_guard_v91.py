from __future__ import annotations

"""Tenis AI v9.3.0 — operator availability guard for Tennis Symphony.

Runs after the existing v9.0C/C.4 evidence adapter. When a fresh verified
Superbet market context exists, the ready-to-bet Symphony pool is restricted to
markets/selections that are actually present at Superbet. The full model
analysis remains untouched upstream.

v9.3.0 aligns the backend selection signature with the frontend PLAYABLE gate:
player-scoped markets now include the normalized player identity in the
signature. This prevents a line for one player from validating the same line for
the opponent and then being rejected only later by the UI.
"""

import math
from copy import deepcopy

VERSION = "v9.3.0"
STRICT_MARKETS = {
    "match_winner", "set1_winner", "set2_winner", "set3_winner",
    "match_total", "set1_total", "set2_total", "set3_total", "total_sets",
    "set1_exact_score", "exact_match_score", "game_state", "set1_tiebreak",
    "match_game_handicap", "set1_game_handicap", "set2_game_handicap",
    "player_total_games", "match_total_aces", "most_aces",
    "player_aces", "player_double_faults", "most_double_faults", "most_aces_plus_df",
}
PLAYER_SCOPED_MARKETS = {"player_total_games", "player_aces", "player_double_faults"}
ALIASES = {
    "match_win": "match_winner",
    "first_set_win": "set1_winner",
    "set1_win": "set1_winner",
    "second_set_win": "set2_winner",
    "third_set_win": "set3_winner",
    "state2": "game_state", "state4": "game_state", "state6": "game_state",
}


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _norm(value):
    return " ".join(str(value or "").strip().casefold().split())


def _name_key(value):
    return " ".join(sorted(_norm(value).replace(",", " ").split()))


def _market(value):
    raw = _norm(value)
    return ALIASES.get(raw, raw)


def _checkpoint(signal):
    cp = _num(signal.get("checkpoint"))
    if cp is not None:
        return int(cp)
    market = _norm(signal.get("market"))
    if market.startswith("state"):
        tail = "".join(ch for ch in market if ch.isdigit())
        if tail:
            return int(tail)
    key = str(signal.get("key") or "")
    for part in key.replace(":", "|").split("|"):
        if part.strip() in {"2", "4", "6"} and "state" in key.casefold():
            return int(part.strip())
    return 0


def _signature(signal):
    market = _market(signal.get("market"))
    player = _name_key(signal.get("player")) if market in PLAYER_SCOPED_MARKETS else ""
    return (
        market,
        _norm(signal.get("pick")),
        round(float(_num(signal.get("line"), -999999.0)), 6),
        _checkpoint(signal),
        player,
    )


def _context(match):
    ctx = match.get("superbet_market_v91") or {}
    if not isinstance(ctx, dict):
        return {}, False
    active = bool(
        ctx.get("operator_verified") is True
        and ctx.get("status") == "VERIFIED"
        and isinstance(ctx.get("canonical_selections"), list)
    )
    return ctx, active


def _availability(ctx):
    by_sig = {}
    for row in ctx.get("canonical_selections") or []:
        if not isinstance(row, dict) or row.get("operator_available") is False:
            continue
        by_sig[_signature(row)] = row
    return by_sig


def _model_signals(ctx):
    out = {}
    for row in ctx.get("model_signals") or []:
        if not isinstance(row, dict) or row.get("operator_line_verified") is not True:
            continue
        out[_signature(row)] = row
    return out


def _operator_meta(signal, available):
    out = dict(signal)
    out.update({
        "operator": "superbet",
        "operator_available": True,
        "operator_line_verified": True,
        "operator_line_source": "oddspapi_superbet_pl",
        "symphony_actionable": True,
    })
    if isinstance(available, dict):
        out["operator_market_id"] = available.get("market_id")
        out["operator_outcome_id"] = available.get("outcome_id")
        out["operator_main_line"] = bool(available.get("main_line", False))
    return out


def _merge_verified(base, verified, available):
    out = dict(base)
    # v9.1 evaluates the exact real line using existing model distributions.
    # This changes only Symphony evidence for this market, never the core score.
    for key in ("score", "symphony_raw_probability", "label", "symphony_source", "exact_path_supported"):
        if verified.get(key) is not None:
            out[key] = verified.get(key)
    if verified.get("key"):
        out["key"] = verified["key"]
    if verified.get("player"):
        out["player"] = verified["player"]
    return _operator_meta(out, available)


def apply_superbet_market_guard(augmented: dict, evidence_meta: dict, original_match: dict):
    ctx, active = _context(original_match)
    meta = dict(evidence_meta or {})
    meta.update({
        "operator_market_context_version": VERSION,
        "operator_market_feed_active": active,
        "operator_prices_used": False,
    })
    if not active:
        return augmented, meta

    available = _availability(ctx)
    verified = _model_signals(ctx)
    cloned = deepcopy(augmented)
    auto = dict(cloned.get("autolearn_v84") or {})
    rows = [dict(x) for x in (auto.get("signals") or []) if isinstance(x, dict)]

    kept = []
    suppressed = 0
    seen = set()
    for row in rows:
        sig = _signature(row)
        market = sig[0]
        if market in STRICT_MARKETS:
            if sig not in available:
                suppressed += 1
                continue
            if sig in verified:
                row = _merge_verified(row, verified[sig], available[sig])
            else:
                row = _operator_meta(row, available[sig])
        kept.append(row)
        seen.add(sig)

    added = 0
    for sig, row in verified.items():
        if sig in seen:
            continue
        kept.append(_operator_meta(row, available.get(sig)))
        seen.add(sig)
        added += 1

    auto["signals"] = kept
    cloned["autolearn_v84"] = auto

    by_key = dict(meta.get("by_key") or {})
    for row in kept:
        key = str(row.get("key") or "")
        if key and row.get("operator_line_verified") is True:
            by_key[key] = row
    meta["by_key"] = by_key
    meta["operator_available_signatures"] = len(available)
    meta["operator_model_signals"] = len(verified)
    meta["operator_suppressed_unavailable"] = suppressed
    meta["operator_verified_added"] = added
    meta["composer_added"] = int(meta.get("composer_added") or 0) + added
    meta["operator_strict_actionable_markets"] = sorted(STRICT_MARKETS)
    meta["operator_contract"] = {
        "ready_to_bet_pool_requires_real_superbet_availability": True,
        "player_scoped_signature_matches_frontend": True,
        "bookmaker_prices_not_used": True,
        "core_model_scores_unchanged": True,
        "unavailable_model_markets_remain_analysis_only_upstream": True,
    }
    return cloned, meta
