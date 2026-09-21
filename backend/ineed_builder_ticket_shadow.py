from __future__ import annotations

"""Pure non-runtime SHADOW contract for one final Bet Builder ticket.

This module does not persist, reserve bankroll, settle, publish to runtime, or
execute a bet.  It only freezes already-verified Phase-4 builder economics and
its exact upstream composition into one deterministic ticket-shaped envelope.
"""

from copy import deepcopy
import math

OPERATOR = "superbet.pl"
MODE = "SHADOW"
ECONOMIC_UNIT = "BET_BUILDER_COMPOSITION"
QUOTE_KIND = "BET_BUILDER_COMBINED"
SCHEMA_VERSION = "logic12-builder-ticket-shadow-v1"
TICKET_STATUS = "SHADOW_TICKET_PROPOSED"


def _text(value) -> str:
    return str(value or "").strip()


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _same_number(left, right) -> bool:
    a, b = _number(left), _number(right)
    return a is not None and b is not None and abs(a - b) <= 1e-12


def _valid_legs(composition: dict) -> list[dict] | None:
    legs = composition.get("legs")
    if not isinstance(legs, list) or len(legs) < 2:
        return None
    if composition.get("leg_count") != len(legs):
        return None
    for leg in legs:
        if not isinstance(leg, dict):
            return None
        if leg.get("fixture_line_verified") is not True:
            return None
        if not _text(leg.get("operator_market_id")) or not _text(leg.get("operator_outcome_id")):
            return None
        if not _text(leg.get("market")):
            return None
    return legs


def _valid_provenance(provenance: object, leg_count: int) -> dict | None:
    if not isinstance(provenance, dict):
        return None
    if provenance.get("operator_verified") is not True or provenance.get("freshness_verified") is not True:
        return None
    if provenance.get("quote_kind") != QUOTE_KIND:
        return None
    required = (
        "source",
        "odds_timestamp",
        "source_event_id",
        "operator_combination_selection_id",
        "source_url",
    )
    if any(not _text(provenance.get(key)) for key in required):
        return None
    component_ids = provenance.get("component_selection_ids")
    if not isinstance(component_ids, list) or len(component_ids) != leg_count:
        return None
    normalized = [_text(value) for value in component_ids]
    if any(not value for value in normalized) or len(set(normalized)) != len(normalized):
        return None
    return provenance


def _matching_identity(composition: dict, evaluation: dict) -> bool:
    for key in ("composition_id", "match_id", "p1", "p2"):
        if not _text(composition.get(key)) or _text(composition.get(key)) != _text(evaluation.get(key)):
            return False
    if composition.get("leg_count") != evaluation.get("leg_count"):
        return False
    if not _same_number(composition.get("joint_probability"), evaluation.get("joint_probability")):
        return False
    if not _same_number(composition.get("combined_odds"), evaluation.get("odds")):
        return False
    return True


def _valid_phase4_snapshot(composition: dict, evaluation: dict, provenance: dict, final_stake: float) -> dict | None:
    snapshot = evaluation.get("snapshot")
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("operator") != OPERATOR or snapshot.get("mode") != MODE:
        return None
    if snapshot.get("economic_unit") != ECONOMIC_UNIT:
        return None
    if snapshot.get("automatic_real_betting") is not False:
        return None
    for key in ("composition_id", "match_id", "p1", "p2"):
        if _text(snapshot.get(key)) != _text(composition.get(key)):
            return None
    if not _same_number(snapshot.get("joint_probability"), composition.get("joint_probability")):
        return None
    if not _same_number(snapshot.get("combined_odds"), composition.get("combined_odds")):
        return None
    if not _same_number(snapshot.get("final_stake"), final_stake):
        return None
    if snapshot.get("combined_price_provenance") != provenance:
        return None
    return snapshot


def _valid_reservation(composition_id: str, evaluation: dict) -> dict | None:
    reservation = evaluation.get("reservation_proposal")
    if not isinstance(reservation, dict):
        return None
    if reservation.get("status") != "SHADOW_PROPOSED" or reservation.get("unit") != ECONOMIC_UNIT:
        return None
    if _text(reservation.get("reservation_key")) != f"builder:{composition_id}":
        return None
    if _text(reservation.get("composition_id")) != composition_id:
        return None
    if reservation.get("runtime_publishable") is not False or not _text(reservation.get("currency")):
        return None
    amount = _number(reservation.get("amount"))
    final_stake = _number(evaluation.get("final_stake"))
    proposed_stake = _number(evaluation.get("proposed_stake"))
    if amount is None or amount <= 0 or final_stake is None or proposed_stake is None:
        return None
    if not _same_number(amount, final_stake) or not _same_number(proposed_stake, final_stake):
        return None
    return reservation


def build_builder_ticket_shadow(composition: dict, evaluation: dict) -> dict | None:
    """Freeze one exact Phase-4 qualified builder into a non-runtime ticket envelope."""
    if not isinstance(composition, dict) or not isinstance(evaluation, dict):
        return None
    if composition.get("operator") != OPERATOR or composition.get("mode") != MODE:
        return None
    if composition.get("automatic_real_betting") is not False:
        return None
    if composition.get("combined_price_status") != "VERIFIED" or composition.get("economic_ready") is not True:
        return None
    if evaluation.get("status") != "SHADOW_QUALIFIED" or evaluation.get("reason_code") is not None:
        return None
    if evaluation.get("runtime_publishable") is not False or evaluation.get("automatic_real_betting") is not False:
        return None
    if not _matching_identity(composition, evaluation):
        return None

    legs = _valid_legs(composition)
    if legs is None:
        return None
    provenance = _valid_provenance(composition.get("combined_price_provenance"), len(legs))
    if provenance is None:
        return None
    if evaluation.get("combined_price_provenance") != provenance:
        return None

    joint_probability = _number(composition.get("joint_probability"))
    combined_odds = _number(composition.get("combined_odds"))
    if joint_probability is None or not (0.0 <= joint_probability <= 100.0):
        return None
    if combined_odds is None or combined_odds <= 1.0:
        return None

    composition_id = _text(composition.get("composition_id"))
    reservation = _valid_reservation(composition_id, evaluation)
    if reservation is None:
        return None
    final_stake = _number(evaluation.get("final_stake"))
    assert final_stake is not None
    snapshot = _valid_phase4_snapshot(composition, evaluation, provenance, final_stake)
    if snapshot is None:
        return None

    economics_keys = (
        "model_probability",
        "raw_implied_probability",
        "no_vig_probability",
        "break_even_probability",
        "fair_odds",
        "edge_probability_points",
        "expected_value_net",
        "effective_odds_after_tax",
        "confidence",
        "risk_state",
        "drawdown",
        "kelly_full",
        "proposed_stake",
        "final_stake",
        "potential_payout",
    )
    economics = {key: deepcopy(evaluation.get(key)) for key in economics_keys}

    return {
        "schema_version": SCHEMA_VERSION,
        "status": TICKET_STATUS,
        "ticket_key": f"builder-ticket:{composition_id}",
        "economic_unit": ECONOMIC_UNIT,
        "mode": MODE,
        "operator": OPERATOR,
        "composition_id": composition_id,
        "match_id": _text(composition.get("match_id")),
        "p1": composition.get("p1"),
        "p2": composition.get("p2"),
        "leg_count": len(legs),
        "legs": deepcopy(legs),
        "joint_probability": joint_probability,
        "combined_odds": combined_odds,
        "odds_timestamp": provenance.get("odds_timestamp"),
        "source": provenance.get("source"),
        "source_event_id": provenance.get("source_event_id"),
        "operator_combination_selection_id": provenance.get("operator_combination_selection_id"),
        "component_selection_ids": deepcopy(provenance.get("component_selection_ids")),
        "source_url": provenance.get("source_url"),
        "combined_price_provenance": deepcopy(provenance),
        "economics": economics,
        "reservation_proposal": deepcopy(reservation),
        "phase4_snapshot": deepcopy(snapshot),
        "runtime_publishable": False,
        "persistence_ready": False,
        "settlement_ready": False,
        "settlement_contract_status": "NOT_IMPLEMENTED",
        "automatic_real_betting": False,
    }
