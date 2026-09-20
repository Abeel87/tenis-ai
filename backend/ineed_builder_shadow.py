from __future__ import annotations

"""Pure SHADOW contract for final same-match Bet Builder compositions.

This module is intentionally not wired into the production iNeed$ runner.
It consumes the already-published final Symphony composition and may attach
only an exact verified operator-provided combined quote. It does not compute
probability, EV, Kelly, stake, settlement, or real-money actions.
"""

from copy import deepcopy
import hashlib
import json

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
    }
    out["economic_ready"] = True
    return out
