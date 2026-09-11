from __future__ import annotations

"""iNeed$ V1 SHADOW bankroll/value/risk layer.

Consumes final Symphony PLAYABLE and current verified Superbet Direct odds.
It never writes or changes model/Symphony/PLAYABLE calculations.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any

try:
    from .superbet_playable import signal_signature
    from .signal_settlement import settle_signal_live
except ImportError:
    from superbet_playable import signal_signature
    from signal_settlement import settle_signal_live

OPERATOR = "superbet.pl"
FINAL_AUTHORITY = "SYMPHONY2_FINAL_PLAYABLE"
TERMINAL = {"WIN", "LOSS", "VOID", "CANCELLED", "SETTLED"}
OPEN = {"PENDING", "SHADOW_PLACED"}


def _num(value: Any, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _match_id(row: dict) -> str:
    value = row.get("match_id") if row.get("match_id") is not None else row.get("id")
    return str(value or "")


def _stable_fingerprint(match_id: str, signal: dict) -> str:
    body = json.dumps([OPERATOR, str(match_id), list(signal_signature(signal))], ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _direct_matches(direct: dict) -> dict[str, dict]:
    return {_match_id(row): row for row in (direct.get("matches") or []) if isinstance(row, dict) and _match_id(row)}


def _active_quote(row: dict) -> bool:
    return bool(
        isinstance(row, dict)
        and row.get("operator_available") is True
        and row.get("operator_price_verified") is True
        and _num(row.get("operator_price")) is not None
        and str(row.get("operator_selection_status") or "active").lower() == "active"
    )


def direct_quote(direct: dict, match_id: str, signal: dict) -> dict | None:
    match = _direct_matches(direct).get(str(match_id))
    if not match or match.get("direct_match_verified") is not True:
        return None
    wanted = signal_signature(signal)
    hits = [row for row in (match.get("canonical_selections") or []) if _active_quote(row) and signal_signature(row) == wanted]
    prices = {round(float(row["operator_price"]), 8) for row in hits}
    if len(hits) != 1 or len(prices) != 1:
        return None
    out = dict(hits[0])
    out["odds_timestamp"] = direct.get("generated_at") or match.get("generated_at")
    out["event_url"] = match.get("event_url")
    out["p1"] = match.get("p1")
    out["p2"] = match.get("p2")
    return out


def sibling_quotes(direct: dict, match_id: str, quote: dict) -> list[dict]:
    match = _direct_matches(direct).get(str(match_id)) or {}
    sig = signal_signature(quote)
    market, _, line, checkpoint, player = sig
    out = []
    for row in match.get("canonical_selections") or []:
        if not _active_quote(row):
            continue
        rsig = signal_signature(row)
        if (rsig[0], rsig[2], rsig[3], rsig[4]) == (market, line, checkpoint, player):
            out.append(row)
    return out


def payout_after_taxes(stake: float, odds: float, cfg: dict) -> float:
    stake = max(0.0, float(stake))
    odds = max(0.0, float(odds))
    stake_after_tax = stake * (1.0 - float(cfg.get("stake_tax_rate", 0.0)))
    gross = stake_after_tax * odds
    threshold = float(cfg.get("high_win_tax_threshold_pln", 0.0) or 0.0)
    tax_rate = float(cfg.get("high_win_tax_rate", 0.0) or 0.0)
    trigger = str(cfg.get("high_win_tax_trigger") or "above")
    if tax_rate > 0 and threshold > 0 and ((trigger == "above" and gross > threshold) or (trigger != "above" and gross >= threshold)):
        gross *= 1.0 - tax_rate
    return gross


def economics(model_probability_pct: float, odds: float, cfg: dict, siblings: list[dict] | None = None, stake: float = 1.0) -> dict:
    p = float(model_probability_pct) / 100.0
    odds = float(odds)
    raw_implied = 1.0 / odds
    implieds = [1.0 / float(x["operator_price"]) for x in (siblings or []) if _num(x.get("operator_price"), 0) and float(x["operator_price"]) > 1.0]
    overround = sum(implieds) if len(implieds) >= 2 else None
    no_vig = raw_implied / overround if overround and overround > 0 else None
    payout = payout_after_taxes(stake, odds, cfg)
    effective_odds = payout / stake if stake > 0 else 0.0
    break_even = 1.0 / effective_odds if effective_odds > 0 else float("inf")
    ev = p * payout - stake
    ev_rate = ev / stake if stake > 0 else -1.0
    edge_pp = (p - (no_vig if no_vig is not None else raw_implied)) * 100.0
    return {
        "model_probability": p,
        "raw_implied_probability": raw_implied,
        "no_vig_probability": no_vig,
        "break_even_probability": break_even,
        "fair_odds": 1.0 / p if p > 0 else None,
        "edge_probability_points": edge_pp,
        "expected_value_net": ev_rate,
        "estimated_bookmaker_margin": (overround - 1.0) if overround is not None else None,
        "potential_payout": payout,
        "effective_odds_after_tax": effective_odds,
    }


def risk_state(equity: float, peak: float, cfg: dict) -> tuple[str, float]:
    dd = 0.0 if peak <= 0 else max(0.0, (peak - equity) / peak)
    d = cfg.get("drawdown") or {}
    if dd >= float(d.get("halted", 0.30)):
        return "HALTED", dd
    if dd >= float(d.get("defensive", 0.20)):
        return "DEFENSIVE", dd
    if dd >= float(d.get("caution", 0.10)):
        return "CAUTION", dd
    return "NORMAL", dd


def _kelly(p: float, effective_odds: float) -> float:
    b = effective_odds - 1.0
    if b <= 0:
        return 0.0
    return max(0.0, (b * p - (1.0 - p)) / b)


def _round_down(value: float, step: float) -> float:
    if step <= 0:
        return value
    return math.floor((value + 1e-12) / step) * step


def _open_exposures(open_bets: list[dict]) -> dict:
    total = sum(float(x.get("stake") or 0) for x in open_bets if str(x.get("status")) in OPEN)
    return {"total": total}


def _overlap_player(bet: dict, p1: str, p2: str) -> bool:
    snap = bet.get("placement_snapshot") or bet.get("current_snapshot") or {}
    names = {str(snap.get("p1") or "").strip().casefold(), str(snap.get("p2") or "").strip().casefold()}
    return bool({p1.casefold(), p2.casefold()} & names)


def _reject(base: dict, reason: str, status: str = "REJECTED") -> dict:
    return {**base, "status": status, "reason_code": reason}


def evaluate(results: list[dict], direct: dict, cfg: dict, state: dict, now: datetime | None = None) -> list[dict]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    experiment = state.get("experiment") or {}
    available = float(state.get("available_capital") or 0.0)
    open_bets = list(state.get("open_bets") or [])
    exposure = _open_exposures(open_bets)["total"]
    equity = float(state.get("bankroll_equity") or (available + exposure))
    peak = float(state.get("peak_bankroll") or max(float(experiment.get("starting_bankroll") or equity), equity))
    rstate, drawdown = risk_state(equity, peak, cfg)
    profile = (cfg.get("risk_profiles") or {}).get(rstate) or {}
    min_ev = float(profile.get("minimum_net_ev", cfg.get("minimum_net_ev", 0.05)))
    min_edge = float(profile.get("minimum_edge_pp", cfg.get("minimum_edge_pp", 4.0)))
    stake_mult = float(profile.get("stake_multiplier", 1.0))
    exp_mult = float(profile.get("exposure_multiplier", 1.0))
    rows = []

    candidates = []
    for match in results or []:
        if not isinstance(match, dict):
            continue
        final = match.get("symphony2_playable") or {}
        if not (
            final.get("playable") is True
            and final.get("final_playable_authority") is True
            and final.get("authority") == FINAL_AUTHORITY
            and final.get("operator") == OPERATOR
        ):
            continue
        mid = _match_id(match)
        p1, p2 = str(match.get("p1") or ""), str(match.get("p2") or "")
        for signal in final.get("signals") or []:
            if not isinstance(signal, dict):
                continue
            fp = _stable_fingerprint(mid, signal)
            model_p = _num(signal.get("operator_model_probability"))
            base = {
                "fingerprint": fp, "match_id": mid, "market": signal.get("market") or "unknown",
                "selection": signal.get("pick"), "model_probability": None if model_p is None else model_p / 100.0,
            }
            quote = direct_quote(direct, mid, signal)
            if model_p is None:
                rows.append(_reject(base, "INSUFFICIENT_DATA")); continue
            if quote is None:
                rows.append(_reject(base, "MARKET_NOT_AVAILABLE")); continue
            odds = float(quote["operator_price"])
            ts = _iso(quote.get("odds_timestamp"))
            if ts is None or (now - ts).total_seconds() > float(cfg.get("odds_max_age_minutes", 108)) * 60:
                rows.append(_reject({**base, "odds": odds, "odds_timestamp": quote.get("odds_timestamp")}, "STALE_ODDS", "EXPIRED")); continue
            if odds < float(cfg.get("minimum_odds", 1.01)) or (cfg.get("maximum_odds") is not None and odds > float(cfg["maximum_odds"])):
                rows.append(_reject({**base, "odds": odds, "odds_timestamp": quote.get("odds_timestamp")}, "ODDS_OUT_OF_RANGE")); continue
            econ_unit = economics(model_p, odds, cfg, sibling_quotes(direct, mid, quote), 1.0)
            candidates.append((econ_unit["expected_value_net"], match, signal, quote, econ_unit, base, rstate, drawdown, p1, p2))

    candidates.sort(key=lambda x: x[0], reverse=True)
    allocated = list(open_bets)
    for _, match, signal, quote, econ_unit, base, rstate, drawdown, p1, p2 in candidates:
        odds = float(quote["operator_price"])
        if rstate == "HALTED":
            rows.append(_reject(base, "RISK_ENGINE_HALTED")); continue
        if econ_unit["expected_value_net"] < min_ev:
            rows.append(_reject({**base, **econ_unit, "odds": odds, "odds_timestamp": quote.get("odds_timestamp")}, "LOW_EV")); continue
        if econ_unit["edge_probability_points"] < min_edge:
            rows.append(_reject({**base, **econ_unit, "odds": odds, "odds_timestamp": quote.get("odds_timestamp")}, "LOW_EDGE")); continue
        confidence = _num(signal.get("learning_reliability"))
        minimum_conf = cfg.get("minimum_confidence")
        if minimum_conf is not None and (confidence is None or confidence < float(minimum_conf)):
            rows.append(_reject(base, "LOW_CONFIDENCE")); continue

        current_total = sum(float(b.get("stake") or 0) for b in allocated if str(b.get("status")) in OPEN)
        same_match = sum(float(b.get("stake") or 0) for b in allocated if str(b.get("status")) in OPEN and str(b.get("match_id")) == base["match_id"])
        same_market = sum(float(b.get("stake") or 0) for b in allocated if str(b.get("status")) in OPEN and str(b.get("market")) == base["market"])
        same_player = sum(float(b.get("stake") or 0) for b in allocated if str(b.get("status")) in OPEN and _overlap_player(b, p1, p2))

        k = _kelly(econ_unit["model_probability"], econ_unit["effective_odds_after_tax"])
        stake = equity * k * float(cfg.get("fractional_kelly", 0.25)) * stake_mult
        stake = min(stake, equity * float(cfg.get("max_single_bet_pct", 0.03)) * stake_mult)
        stake = min(stake, max(0.0, equity * float(cfg.get("max_match_exposure_pct", 0.03)) * exp_mult - same_match))
        stake = min(stake, max(0.0, equity * float(cfg.get("max_player_exposure_pct", 0.03)) * exp_mult - same_player))
        stake = min(stake, max(0.0, equity * float(cfg.get("max_market_exposure_pct", 0.15)) * exp_mult - same_market))
        stake = min(stake, max(0.0, equity * float(cfg.get("max_total_exposure_pct", 0.15)) * exp_mult - current_total), available)
        stake = _round_down(stake, float(cfg.get("stake_rounding", 0.01)))
        if same_player > 0 and stake < float(cfg.get("minimum_stake", 2.0)):
            rows.append(_reject(base, "CORRELATION_LIMIT")); continue
        if same_match > 0 and stake < float(cfg.get("minimum_stake", 2.0)):
            rows.append(_reject(base, "MATCH_EXPOSURE_LIMIT")); continue
        if current_total >= equity * float(cfg.get("max_total_exposure_pct", 0.15)) * exp_mult - 1e-9:
            rows.append(_reject(base, "TOTAL_EXPOSURE_LIMIT")); continue
        if available < float(cfg.get("minimum_stake", 2.0)):
            rows.append(_reject(base, "BANKROLL_TOO_LOW")); continue
        if stake < float(cfg.get("minimum_stake", 2.0)):
            rows.append(_reject(base, "STAKE_BELOW_MINIMUM")); continue

        econ = economics(model_p, odds, cfg, sibling_quotes(direct, base["match_id"], quote), stake)
        snapshot = {
            "timestamp": now.isoformat(), "operator": OPERATOR, "match_id": base["match_id"],
            "p1": p1, "p2": p2, "market": signal.get("market"), "pick": signal.get("pick"), "selection": signal.get("pick"),
            "line": signal.get("line"), "checkpoint": signal.get("checkpoint"), "player": signal.get("player"),
            "raw_odds": odds, "odds_timestamp": quote.get("odds_timestamp"), "event_url": quote.get("event_url"),
            "operator_market_id": quote.get("operator_market_id"), "operator_outcome_id": quote.get("operator_outcome_id"),
            "operator_model_probability": model_p, "raw_model_probability": signal.get("raw_model_probability"),
            "calibrated_model_probability": signal.get("calibrated_model_probability"), "learning_reliability": confidence,
            "learning_support_rows": signal.get("learning_support_rows"), "data_quality": "CURRENT_VERIFIED_SUPERBET_DIRECT",
            "bankroll_before": equity, "available_capital_before": available, "risk_state": rstate, "drawdown": drawdown,
            "kelly_full": k, "fractional_kelly": cfg.get("fractional_kelly"), "final_stake": stake,
            "potential_payout": econ["potential_payout"], "expected_value_net": econ["expected_value_net"],
            "edge_probability_points": econ["edge_probability_points"], "fair_odds": econ["fair_odds"],
            "break_even_probability": econ["break_even_probability"], "no_vig_probability": econ["no_vig_probability"],
            "raw_implied_probability": econ["raw_implied_probability"], "estimated_bookmaker_margin": econ["estimated_bookmaker_margin"],
            "config_version": cfg.get("version"), "automatic_real_betting": False,
        }
        row = {
            **base, **econ, "status": "QUALIFIED", "reason_code": None, "odds": odds,
            "odds_timestamp": quote.get("odds_timestamp"), "confidence": confidence,
            "data_quality": snapshot["data_quality"], "proposed_stake": stake, "final_stake": stake, "snapshot": snapshot,
        }
        rows.append(row)
        allocated.append({"status": "PENDING", "stake": stake, "match_id": base["match_id"], "market": base["market"], "placement_snapshot": snapshot})
        available -= stake
    return rows


def build_settlements(open_bets: list[dict], history: list[dict], cfg: dict) -> list[dict]:
    finals = {}
    for row in history or []:
        if not isinstance(row, dict):
            continue
        mid = _match_id(row)
        final = row.get("result") if isinstance(row.get("result"), dict) else row.get("final") if isinstance(row.get("final"), dict) else None
        if mid and final:
            finals[mid] = {**final, "p1": row.get("p1") or final.get("p1"), "p2": row.get("p2") or final.get("p2")}
    out = []
    for bet in open_bets or []:
        if str(bet.get("status")) not in OPEN:
            continue
        final = finals.get(str(bet.get("match_id")))
        if not final:
            continue
        snap = bet.get("placement_snapshot") or {}
        status = str(final.get("status") or "").lower()
        if status in {"cancelled", "canceled", "abandoned", "postponed"}:
            outcome = "CANCELLED"; payout = float(bet.get("stake") or 0)
        else:
            result = settle_signal_live(snap, final)
            if result == "unverifiable":
                continue
            outcome = {"hit": "WIN", "miss": "LOSS", "void": "VOID"}.get(result)
            if not outcome:
                continue
            payout = payout_after_taxes(float(bet.get("stake") or 0), float(bet.get("odds") or 0), cfg) if outcome == "WIN" else float(bet.get("stake") or 0) if outcome == "VOID" else 0.0
        out.append({"bet_id": bet.get("id"), "outcome": outcome, "payout": round(payout, 4), "settlement_snapshot": {"source": "existing_signal_settlement", "final": final}})
    return out
