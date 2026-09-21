from copy import deepcopy

import pytest

from backend.ineed_builder_ticket_shadow import build_builder_ticket_shadow


def composition():
    provenance = {
        "source": "superbet_dynamic_betbuilder_getSgaOddPrice_v2",
        "odds_timestamp": "2026-09-21T05:30:00+00:00",
        "operator_verified": True,
        "freshness_verified": True,
        "quote_kind": "BET_BUILDER_COMBINED",
        "source_quote_kind": "BET_BUILDER_DYNAMIC_SGA",
        "source_event_id": "15000001",
        "operator_combination_selection_id": "sga-1",
        "component_selection_ids": ["leg-a", "leg-b"],
        "source_url": "https://production-superbet-bmb.freetls.fastly.net/betbuilder/v2/getSgaOddPrice?proof=1",
    }
    return {
        "mode": "SHADOW",
        "operator": "superbet.pl",
        "match_id": "192095",
        "p1": "Eva Lys",
        "p2": "Gabriela Elena Ruse",
        "composition_id": "bb-0123456789abcdef01234567",
        "leg_count": 2,
        "legs": [
            {
                "market": "set1_total", "pick": "over", "line": 8.5,
                "operator_market_id": "10", "operator_outcome_id": "11",
                "fixture_line_verified": True,
            },
            {
                "market": "match_winner", "pick": "Eva Lys", "line": None,
                "operator_market_id": "20", "operator_outcome_id": "21",
                "fixture_line_verified": True,
            },
        ],
        "joint_probability": 90.0,
        "combined_odds": 1.70,
        "combined_price_status": "VERIFIED",
        "combined_price_provenance": provenance,
        "economic_ready": True,
        "automatic_real_betting": False,
    }


def evaluation():
    c = composition()
    reservation = {
        "status": "SHADOW_PROPOSED",
        "unit": "BET_BUILDER_COMPOSITION",
        "reservation_key": f"builder:{c['composition_id']}",
        "composition_id": c["composition_id"],
        "amount": 6.0,
        "currency": "PLN",
        "runtime_publishable": False,
    }
    return {
        "composition_id": c["composition_id"],
        "match_id": c["match_id"],
        "p1": c["p1"],
        "p2": c["p2"],
        "leg_count": c["leg_count"],
        "joint_probability": c["joint_probability"],
        "odds": c["combined_odds"],
        "combined_price_provenance": deepcopy(c["combined_price_provenance"]),
        "model_probability": 0.90,
        "raw_implied_probability": 1 / 1.70,
        "no_vig_probability": None,
        "break_even_probability": 0.6684491979,
        "fair_odds": 1.1111111111,
        "edge_probability_points": 31.1764705882,
        "expected_value_net": 0.3464,
        "effective_odds_after_tax": 1.496,
        "confidence": 0.8,
        "risk_state": "NORMAL",
        "drawdown": 0.0,
        "kelly_full": 0.6983870968,
        "proposed_stake": 6.0,
        "final_stake": 6.0,
        "potential_payout": 8.976,
        "status": "SHADOW_QUALIFIED",
        "reason_code": None,
        "reservation_proposal": reservation,
        "snapshot": {
            "timestamp": "2026-09-21T05:31:00+00:00",
            "operator": "superbet.pl",
            "mode": "SHADOW",
            "economic_unit": "BET_BUILDER_COMPOSITION",
            "composition_id": c["composition_id"],
            "match_id": c["match_id"],
            "p1": c["p1"], "p2": c["p2"],
            "builder_markets": ["match_winner", "set1_total"],
            "joint_probability": c["joint_probability"],
            "combined_odds": c["combined_odds"],
            "combined_price_provenance": deepcopy(c["combined_price_provenance"]),
            "risk_state": "NORMAL", "drawdown": 0.0,
            "kelly_full": 0.6983870968, "fractional_kelly": 0.25,
            "final_stake": 6.0, "automatic_real_betting": False,
        },
        "runtime_publishable": False,
        "automatic_real_betting": False,
    }


def test_builds_one_nonruntime_ticket_from_exact_phase4_contract():
    c, e = composition(), evaluation()
    ticket = build_builder_ticket_shadow(c, e)
    assert ticket is not None
    assert ticket["schema_version"] == "logic12-builder-ticket-shadow-v1"
    assert ticket["status"] == "SHADOW_TICKET_PROPOSED"
    assert ticket["ticket_key"] == f"builder-ticket:{c['composition_id']}"
    assert ticket["economic_unit"] == "BET_BUILDER_COMPOSITION"
    assert ticket["composition_id"] == c["composition_id"]
    assert ticket["legs"] == c["legs"]
    assert ticket["component_selection_ids"] == ["leg-a", "leg-b"]
    assert ticket["operator_combination_selection_id"] == "sga-1"
    assert ticket["source_event_id"] == "15000001"
    assert ticket["joint_probability"] == 90.0
    assert ticket["combined_odds"] == 1.70
    assert ticket["reservation_proposal"] == e["reservation_proposal"]
    assert ticket["economics"]["final_stake"] == 6.0
    assert ticket["runtime_publishable"] is False
    assert ticket["persistence_ready"] is False
    assert ticket["settlement_ready"] is False
    assert ticket["automatic_real_betting"] is False


@pytest.mark.parametrize("status", ["QUALIFIED", "SHADOW_REJECTED", "SHADOW_EXPIRED", "PENDING"])
def test_rejects_any_status_other_than_phase4_shadow_qualified(status):
    e = evaluation()
    e["status"] = status
    assert build_builder_ticket_shadow(composition(), e) is None


def test_rejects_identity_or_economic_mismatch_between_sources():
    mutations = [
        ("composition_id", "bb-other"),
        ("match_id", "other-match"),
        ("p1", "Other Player"),
        ("p2", "Other Player"),
        ("leg_count", 3),
        ("joint_probability", 89.0),
        ("odds", 1.69),
    ]
    for key, value in mutations:
        e = evaluation()
        e[key] = value
        assert build_builder_ticket_shadow(composition(), e) is None, key


def test_requires_exact_single_whole_builder_reservation():
    for key, value in [
        ("status", "PENDING"),
        ("unit", "SIGNAL"),
        ("reservation_key", "builder:wrong"),
        ("composition_id", "bb-wrong"),
        ("amount", 5.99),
        ("runtime_publishable", True),
    ]:
        e = evaluation()
        e["reservation_proposal"][key] = value
        assert build_builder_ticket_shadow(composition(), e) is None, key


def test_requires_exact_operator_quote_provenance_and_component_identity():
    cases = [
        ("operator_verified", False),
        ("freshness_verified", False),
        ("quote_kind", "SINGLE"),
        ("source_event_id", None),
        ("operator_combination_selection_id", None),
        ("source_url", None),
    ]
    for key, value in cases:
        e = evaluation()
        e["combined_price_provenance"][key] = value
        assert build_builder_ticket_shadow(composition(), e) is None, key
    e = evaluation()
    e["combined_price_provenance"]["component_selection_ids"] = ["leg-a", "leg-a"]
    assert build_builder_ticket_shadow(composition(), e) is None
    e = evaluation()
    e["combined_price_provenance"]["source_event_id"] = "different"
    e["snapshot"]["combined_price_provenance"] = deepcopy(e["combined_price_provenance"])
    assert build_builder_ticket_shadow(composition(), e) is None


def test_requires_verified_complete_leg_contract():
    variants = []
    c = composition(); c["leg_count"] = 3; variants.append(c)
    c = composition(); c["legs"][0]["fixture_line_verified"] = False; variants.append(c)
    c = composition(); c["legs"][0]["operator_market_id"] = None; variants.append(c)
    c = composition(); c["legs"][0]["operator_outcome_id"] = None; variants.append(c)
    for c in variants:
        assert build_builder_ticket_shadow(c, evaluation()) is None


def test_ticket_cannot_look_like_v1_signal_or_claim_settlement():
    ticket = build_builder_ticket_shadow(composition(), evaluation())
    assert ticket is not None
    for forbidden in ("signal_id", "fingerprint", "market", "selection", "outcome", "payout"):
        assert forbidden not in ticket
    assert ticket["persistence_ready"] is False
    assert ticket["settlement_ready"] is False
    assert ticket["settlement_contract_status"] == "NOT_IMPLEMENTED"


def test_ticket_is_deterministic_and_deep_copies_evidence():
    c, e = composition(), evaluation()
    first = build_builder_ticket_shadow(c, e)
    second = build_builder_ticket_shadow(deepcopy(c), deepcopy(e))
    assert first == second
    c["legs"][0]["pick"] = "mutated"
    e["combined_price_provenance"]["source_event_id"] = "mutated"
    e["reservation_proposal"]["amount"] = 99.0
    assert first["legs"][0]["pick"] == "over"
    assert first["source_event_id"] == "15000001"
    assert first["reservation_proposal"]["amount"] == 6.0
