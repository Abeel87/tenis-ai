from __future__ import annotations

"""Pure SHADOW contract for final same-match Bet Builder compositions.

This module is intentionally not wired into the production iNeed$ runner.
It consumes the already-published final Symphony composition and may attach
only an exact verified operator-provided combined quote. Phase 4 may compute
additive SHADOW-only builder economics/reservation proposals, but never runtime
persistence, settlement, probability, or real-money actions.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math

try:
    from .ineed_money import RISK_UNIT_BUILDER, direct_quote, economics, risk_exposure_overlaps_player, risk_exposure_state, risk_state
    from .superbet_direct import exact_combination_quote, parse_dynamic_sga_quote
except ImportError:
    from ineed_money import RISK_UNIT_BUILDER, direct_quote, economics, risk_exposure_overlaps_player, risk_exposure_state, risk_state
    from superbet_direct import exact_combination_quote, parse_dynamic_sga_quote

OPERATOR = "superbet.pl"
FINAL_AUTHORITY = "SYMPHONY2_FINAL_PLAYABLE"
QUOTE_KIND = "BET_BUILDER_COMBINED"


def _text(value) -> str:
    return str(value or "").strip()


def _canonical_match_id(match: dict) -> str | None:
    values = {_text(match.get(key)) for key in ("id", "match_id", "match_key") if _text(match.get(key))}
    return next(iter(values)) if len(values) == 1 else None


def _leg_identity(signal: dict) -> dict:
    return {
        "market": signal.get("market"),
        "pick": signal.get("pick"),
        "line": signal.get("line"),
        "checkpoint": signal.get("checkpoint"),
        "player": signal.get("player"),
        "operator_market_id": signal.get("operator_market_id"),
        "operator_outcome_id": signal.get("operator_outcome_id"),
    }


def _composition_id(match_id: str, legs: list[dict]) -> str:
    canonical = sorted(
        (_leg_identity(leg) for leg in legs),
        key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=True),
    )
    payload = json.dumps(
        {"match_id": match_id, "operator": OPERATOR, "legs": canonical},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "bb-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def build_shadow_composition(match: dict) -> dict | None:
    if not isinstance(match, dict):
        return None
    final = match.get("symphony2_playable") or {}
    if not (
        isinstance(final, dict)
        and final.get("playable") is True
        and final.get("final_playable_authority") is True
        and final.get("authority") == FINAL_AUTHORITY
        and final.get("operator") == OPERATOR
    ):
        return None

    match_id = _canonical_match_id(match)
    legs = [deepcopy(x) for x in (final.get("signals") or []) if isinstance(x, dict)]
    joint = final.get("joint_probability")
    if not match_id or len(legs) < 2:
        return None
    if final.get("recommended_leg_count") != len(legs):
        return None
    if any(leg.get("fixture_line_verified") is not True for leg in legs):
        return None
    if any(not _text(leg.get("operator_market_id")) or not _text(leg.get("operator_outcome_id")) for leg in legs):
        return None
    try:
        joint_value = float(joint)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= joint_value <= 100.0):
        return None

    composition_id = _composition_id(match_id, legs)
    return {
        "mode": "SHADOW",
        "operator": OPERATOR,
        "match_id": match_id,
        "p1": match.get("p1"),
        "p2": match.get("p2"),
        "composition_id": composition_id,
        "leg_count": len(legs),
        "legs": legs,
        "joint_probability": joint_value,
        "joint_status": final.get("joint_status"),
        "symphony_source_generated_at": final.get("source_generated_at"),
        "combined_odds": None,
        "combined_price_status": "NOT_AVAILABLE",
        "combined_price_reason": "NO_EXACT_OPERATOR_BUILDER_QUOTE",
        "combined_price_provenance": None,
        "economic_ready": False,
        "automatic_real_betting": False,
    }


def resolve_prepriced_combined_quote(composition: dict, direct: dict, catalog: dict) -> dict | None:
    if not all(isinstance(x, dict) for x in (composition, direct, catalog)):
        return None
    match_id = _text(composition.get("match_id"))
    direct_ts = _text(direct.get("generated_at"))
    catalog_ts = _text(catalog.get("observed_at"))
    if not match_id or not direct_ts or catalog_ts != direct_ts:
        return None

    matches = []
    for row in direct.get("matches") or []:
        if not isinstance(row, dict):
            continue
        row_id = row.get("match_id") if row.get("match_id") is not None else row.get("id")
        if _text(row_id) == match_id and row.get("direct_match_verified") is True:
            matches.append(row)
    if len(matches) != 1:
        return None
    event_id = _text(matches[0].get("event_id"))
    if not event_id or _text(catalog.get("source_event_id")) != event_id:
        return None

    component_ids = []
    for leg in composition.get("legs") or []:
        resolved = direct_quote(direct, match_id, leg)
        selection_id = _text((resolved or {}).get("operator_selection_id"))
        if not selection_id:
            return None
        component_ids.append(selection_id)
    if len(component_ids) < 2 or len(set(component_ids)) != len(component_ids):
        return None

    hit = exact_combination_quote(catalog.get("quotes") or [], component_ids, event_id=event_id)
    if not hit or _text(hit.get("odds_timestamp")) != catalog_ts:
        return None
    return {
        "composition_id": composition.get("composition_id"),
        "operator": OPERATOR,
        "quote_kind": QUOTE_KIND,
        "operator_verified": True,
        "freshness_verified": True,
        "combined_odds": hit.get("combined_odds"),
        "odds_timestamp": hit.get("odds_timestamp"),
        "source": hit.get("source"),
        "source_event_id": event_id,
        "operator_combination_selection_id": hit.get("operator_selection_id"),
        "component_selection_ids": list(component_ids),
        "source_quote_kind": hit.get("quote_kind"),
    }


def resolve_dynamic_combined_quote(composition: dict, direct: dict, payload: dict, *, observed_at: str | None, source_url: str | None) -> dict | None:
    if not all(isinstance(x, dict) for x in (composition, direct, payload)) or not observed_at:
        return None
    match_id = _text(composition.get("match_id"))
    if not match_id or not _text(direct.get("generated_at")):
        return None
    matches = []
    for row in direct.get("matches") or []:
        if not isinstance(row, dict):
            continue
        row_id = row.get("match_id") if row.get("match_id") is not None else row.get("id")
        if _text(row_id) == match_id and row.get("direct_match_verified") is True:
            matches.append(row)
    if len(matches) != 1:
        return None
    event_id = _text(matches[0].get("event_id"))
    if not event_id:
        return None
    component_ids = []
    for leg in composition.get("legs") or []:
        resolved = direct_quote(direct, match_id, leg)
        sid = _text((resolved or {}).get("operator_selection_id"))
        if not sid:
            return None
        component_ids.append(sid)
    if len(component_ids) < 2 or len(set(component_ids)) != len(component_ids):
        return None
    hit = parse_dynamic_sga_quote(payload, event_id=event_id, component_selection_ids=component_ids, observed_at=observed_at, source_url=source_url)
    if not hit:
        return None
    return {
        "composition_id": composition.get("composition_id"), "operator": OPERATOR,
        "quote_kind": QUOTE_KIND, "operator_verified": True, "freshness_verified": True,
        "combined_odds": hit.get("combined_odds"), "odds_timestamp": hit.get("odds_timestamp"),
        "source": hit.get("source"), "source_event_id": event_id,
        "operator_combination_selection_id": hit.get("operator_combination_selection_id"),
        "component_selection_ids": component_ids, "source_quote_kind": hit.get("quote_kind"),
        "source_url": hit.get("source_url"),
    }


def attach_verified_combined_quote(composition: dict, quote: dict | None) -> dict:
    out = deepcopy(composition or {})
    out["combined_odds"] = None
    out["combined_price_status"] = "NOT_AVAILABLE"
    out["combined_price_reason"] = "NO_EXACT_OPERATOR_BUILDER_QUOTE"
    out["combined_price_provenance"] = None
    out["economic_ready"] = False

    if not isinstance(quote, dict):
        return out
    if quote.get("operator") != OPERATOR or quote.get("quote_kind") != QUOTE_KIND:
        return out
    if quote.get("operator_verified") is not True or quote.get("freshness_verified") is not True:
        return out
    if _text(quote.get("composition_id")) != _text(out.get("composition_id")):
        return out
    try:
        odds = float(quote.get("combined_odds"))
    except (TypeError, ValueError):
        return out
    if odds <= 1.0 or not _text(quote.get("odds_timestamp")) or not _text(quote.get("source")):
        return out

    out["combined_odds"] = odds
    out["combined_price_status"] = "VERIFIED"
    out["combined_price_reason"] = None
    out["combined_price_provenance"] = {
        "source": quote.get("source"),
        "odds_timestamp": quote.get("odds_timestamp"),
        "operator_verified": True,
        "freshness_verified": True,
        "quote_kind": QUOTE_KIND,
        "source_quote_kind": quote.get("source_quote_kind"),
        "source_event_id": quote.get("source_event_id"),
        "operator_combination_selection_id": quote.get("operator_combination_selection_id"),
        "component_selection_ids": deepcopy(quote.get("component_selection_ids")),
        "source_url": quote.get("source_url"),
    }
    out["economic_ready"] = True
    return out


def _num(value, default=None):
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _iso(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _builder_kelly(p: float, effective_odds: float) -> float:
    b = effective_odds - 1.0
    if b <= 0:
        return 0.0
    return max(0.0, (b * p - (1.0 - p)) / b)


def _builder_round_down(value: float, step: float) -> float:
    if step <= 0:
        return value
    return math.floor((value + 1e-12) / step) * step


def _builder_reject(base: dict, reason: str, status: str = "SHADOW_REJECTED") -> dict:
    return {
        **base,
        "status": status,
        "reason_code": reason,
        "reservation_proposal": None,
        "runtime_publishable": False,
        "automatic_real_betting": False,
    }


def _verified_builder_economic_input(row: dict) -> bool:
    provenance = row.get("combined_price_provenance")
    component_ids = (provenance or {}).get("component_selection_ids")
    legs = [x for x in (row.get("legs") or []) if isinstance(x, dict)]
    return bool(
        row.get("mode") == "SHADOW"
        and row.get("operator") == OPERATOR
        and row.get("combined_price_status") == "VERIFIED"
        and row.get("economic_ready") is True
        and isinstance(provenance, dict)
        and provenance.get("operator_verified") is True
        and provenance.get("freshness_verified") is True
        and provenance.get("quote_kind") == QUOTE_KIND
        and _text(provenance.get("source"))
        and _text(provenance.get("odds_timestamp"))
        and len(legs) >= 2
        and row.get("leg_count") == len(legs)
        and isinstance(component_ids, list)
        and len(component_ids) == len(legs)
        and len(set(map(str, component_ids))) == len(component_ids)
    )


def evaluate_builder_economics_shadow(
    compositions: list[dict], cfg: dict, state: dict, now: datetime | None = None
) -> list[dict]:
    """Evaluate whole-builder economics without publishing or reserving bankroll."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    risk = risk_exposure_state(state)
    available = risk["available_capital"]
    allocated = list(risk["risk_exposures"])
    existing_composition_ids = {
        _text(x.get("composition_id")) for x in allocated if _text(x.get("composition_id"))
    }
    equity = risk["bankroll_equity"]
    experiment = state.get("experiment") or {}
    peak = float(
        state.get("peak_bankroll")
        or max(float(experiment.get("starting_bankroll") or equity), equity)
    )
    rstate, drawdown = risk_state(equity, peak, cfg)
    profile = (cfg.get("risk_profiles") or {}).get(rstate) or {}
    min_ev = float(profile.get("minimum_net_ev", cfg.get("minimum_net_ev", 0.05)))
    min_edge = float(profile.get("minimum_edge_pp", cfg.get("minimum_edge_pp", 4.0)))
    stake_mult = float(profile.get("stake_multiplier", 1.0))
    exp_mult = float(profile.get("exposure_multiplier", 1.0))
    minimum_stake = float(cfg.get("minimum_stake", 2.0))
    results: list[dict | None] = [None] * len(compositions)
    candidates = []
    seen: set[str] = set()

    for idx, row in enumerate(compositions or []):
        if not isinstance(row, dict):
            results[idx] = _builder_reject({}, "INVALID_COMPOSITION")
            continue
        cid = _text(row.get("composition_id"))
        base = {
            "composition_id": cid or None,
            "match_id": _text(row.get("match_id")) or None,
            "p1": row.get("p1"), "p2": row.get("p2"),
            "leg_count": row.get("leg_count"),
            "joint_probability": row.get("joint_probability"),
            "odds": row.get("combined_odds"),
            "combined_price_provenance": deepcopy(row.get("combined_price_provenance")),
            "runtime_publishable": False,
            "automatic_real_betting": False,
            "reservation_proposal": None,
        }
        if not cid:
            results[idx] = _builder_reject(base, "INVALID_COMPOSITION")
            continue
        if not _text(row.get("p1")) or not _text(row.get("p2")):
            results[idx] = _builder_reject(base, "INVALID_COMPOSITION")
            continue
        if cid in existing_composition_ids:
            results[idx] = _builder_reject(base, "DUPLICATE_COMPOSITION")
            continue
        if not _verified_builder_economic_input(row):
            results[idx] = _builder_reject(base, "NO_EXACT_OPERATOR_BUILDER_QUOTE")
            continue
        joint = _num(row.get("joint_probability"))
        odds = _num(row.get("combined_odds"))
        if joint is None or not (0.0 <= joint <= 100.0) or odds is None or odds <= 1.0:
            results[idx] = _builder_reject(base, "INVALID_ECONOMIC_INPUT")
            continue
        ts = _iso((row.get("combined_price_provenance") or {}).get("odds_timestamp"))
        if ts is None:
            results[idx] = _builder_reject(base, "INVALID_ODDS_TIMESTAMP")
            continue
        age_seconds = (now - ts).total_seconds()
        if age_seconds > float(cfg.get("odds_max_age_minutes", 108)) * 60:
            results[idx] = _builder_reject(
                {**base, "odds_timestamp": ts.isoformat()}, "STALE_ODDS", "SHADOW_EXPIRED"
            )
            continue
        if odds < float(cfg.get("minimum_odds", 1.01)):
            results[idx] = _builder_reject(base, "ODDS_OUT_OF_RANGE")
            continue
        maximum_odds = cfg.get("maximum_odds")
        if maximum_odds is not None and odds > float(maximum_odds):
            results[idx] = _builder_reject(base, "ODDS_OUT_OF_RANGE")
            continue

        econ = economics(joint, odds, cfg, siblings=None, stake=1.0)
        enriched = {**base, **econ, "odds": odds, "odds_timestamp": ts.isoformat()}
        if rstate == "HALTED":
            results[idx] = _builder_reject(enriched, "RISK_ENGINE_HALTED")
            continue
        if econ["expected_value_net"] < min_ev:
            results[idx] = _builder_reject(enriched, "LOW_EV")
            continue
        if econ["edge_probability_points"] < min_edge:
            results[idx] = _builder_reject(enriched, "LOW_EDGE")
            continue
        legs = [x for x in (row.get("legs") or []) if isinstance(x, dict)]
        reliabilities = [_num(x.get("learning_reliability")) for x in legs]
        confidence = min(reliabilities) if reliabilities and all(x is not None for x in reliabilities) else None
        minimum_conf = cfg.get("minimum_confidence")
        if minimum_conf is not None and (confidence is None or confidence < float(minimum_conf)):
            results[idx] = _builder_reject({**enriched, "confidence": confidence}, "LOW_CONFIDENCE")
            continue
        markets = sorted({_text(x.get("market")) for x in legs if _text(x.get("market"))})
        if not markets:
            results[idx] = _builder_reject(enriched, "INVALID_COMPOSITION")
            continue
        if cid in seen:
            results[idx] = _builder_reject(enriched, "DUPLICATE_COMPOSITION")
            continue
        seen.add(cid)
        candidates.append({
            "idx": idx, "row": row, "base": enriched, "econ": econ,
            "confidence": confidence, "markets": markets,
            "p1": _text(row.get("p1")), "p2": _text(row.get("p2")),
        })

    candidates.sort(key=lambda item: item["econ"]["expected_value_net"], reverse=True)

    for item in candidates:
        idx = item["idx"]
        row = item["row"]
        base = item["base"]
        markets = item["markets"]
        p1, p2 = item["p1"], item["p2"]
        active = list(allocated)
        current_total = sum(float(x.get("stake") or 0.0) for x in active)
        same_match = sum(
            float(x.get("stake") or 0.0) for x in active
            if _text(x.get("match_id")) == _text(row.get("match_id"))
        )
        same_player = sum(
            float(x.get("stake") or 0.0) for x in active
            if risk_exposure_overlaps_player(x, p1, p2)
        )
        market_exposure = {
            market: sum(
                float(x.get("stake") or 0.0) for x in active
                if market in (x.get("markets") or [])
            )
            for market in markets
        }
        p = float(item["econ"]["model_probability"])
        kelly = _builder_kelly(p, float(item["econ"]["effective_odds_after_tax"]))
        stake = equity * kelly * float(cfg.get("fractional_kelly", 0.25)) * stake_mult
        single_cap = equity * float(cfg.get("max_single_bet_pct", 0.03)) * stake_mult
        match_cap = equity * float(cfg.get("max_match_exposure_pct", 0.03)) * exp_mult
        player_cap = equity * float(cfg.get("max_player_exposure_pct", 0.03)) * exp_mult
        market_cap = equity * float(cfg.get("max_market_exposure_pct", 0.15)) * exp_mult
        total_cap = equity * float(cfg.get("max_total_exposure_pct", 0.15)) * exp_mult
        match_headroom = max(0.0, match_cap - same_match)
        player_headroom = max(0.0, player_cap - same_player)
        market_headroom = min(max(0.0, market_cap - market_exposure[m]) for m in markets)
        total_headroom = max(0.0, total_cap - current_total)
        stake = min(
            stake, single_cap, match_headroom, player_headroom,
            market_headroom, total_headroom, available,
        )
        stake = _builder_round_down(stake, float(cfg.get("stake_rounding", 0.01)))
        if stake < minimum_stake:
            if match_headroom < minimum_stake:
                reason = "MATCH_EXPOSURE_LIMIT"
            elif player_headroom < minimum_stake:
                reason = "CORRELATION_LIMIT"
            elif market_headroom < minimum_stake:
                reason = "MARKET_EXPOSURE_LIMIT"
            elif total_headroom < minimum_stake:
                reason = "TOTAL_EXPOSURE_LIMIT"
            elif available < minimum_stake:
                reason = "BANKROLL_TOO_LOW"
            else:
                reason = "STAKE_BELOW_MINIMUM"
            results[idx] = _builder_reject({**base, "kelly_full": kelly}, reason)
            continue

        final_econ = economics(
            float(row["joint_probability"]), float(row["combined_odds"]), cfg,
            siblings=None, stake=stake,
        )
        reservation = {
            "status": "SHADOW_PROPOSED",
            "unit": "BET_BUILDER_COMPOSITION",
            "reservation_key": f"builder:{row['composition_id']}",
            "composition_id": row["composition_id"],
            "amount": stake,
            "currency": cfg.get("currency", "PLN"),
            "runtime_publishable": False,
        }
        snapshot = {
            "timestamp": now.isoformat(),
            "operator": OPERATOR,
            "mode": "SHADOW",
            "economic_unit": "BET_BUILDER_COMPOSITION",
            "composition_id": row["composition_id"],
            "match_id": row.get("match_id"),
            "p1": row.get("p1"), "p2": row.get("p2"),
            "builder_markets": markets,
            "joint_probability": row.get("joint_probability"),
            "combined_odds": row.get("combined_odds"),
            "combined_price_provenance": deepcopy(row.get("combined_price_provenance")),
            "risk_state": rstate, "drawdown": drawdown,
            "kelly_full": kelly, "fractional_kelly": cfg.get("fractional_kelly"),
            "final_stake": stake, "automatic_real_betting": False,
        }
        results[idx] = {
            **base,
            **final_econ,
            "status": "SHADOW_QUALIFIED",
            "reason_code": None,
            "confidence": item["confidence"],
            "risk_state": rstate,
            "drawdown": drawdown,
            "kelly_full": kelly,
            "proposed_stake": stake,
            "final_stake": stake,
            "reservation_proposal": reservation,
            "snapshot": snapshot,
            "runtime_publishable": False,
            "automatic_real_betting": False,
        }
        allocated.append({
            "economic_unit": RISK_UNIT_BUILDER, "status": "PENDING", "stake": stake,
            "match_id": _text(row.get("match_id")),
            "players": [x for x in (_text(row.get("p1")), _text(row.get("p2"))) if x],
            "markets": list(markets), "source_id": f"builder:{row['composition_id']}",
            "composition_id": row.get("composition_id"),
        })
        available -= stake

    return [row for row in results if row is not None]
