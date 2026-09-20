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

try:
    from .ineed_money import direct_quote
    from .superbet_direct import exact_combination_quote, parse_dynamic_sga_quote
except ImportError:
    from ineed_money import direct_quote
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
