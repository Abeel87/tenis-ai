import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import ineed_builder_shadow as b
import superbet_direct as d


def playable_match():
    return {
        "match_id": "m-1", "p1": "A", "p2": "B",
        "symphony2_playable": {
            "playable": True, "final_playable_authority": True,
            "authority": "SYMPHONY2_FINAL_PLAYABLE", "operator": "superbet.pl",
            "recommended_leg_count": 2, "joint_probability": 50.075,
            "joint_status": "EXACT_STATE",
            "signals": [
                {"market": "set1_total", "pick": "over", "line": 8.5,
                 "operator_market_id": "10", "operator_outcome_id": "11", "fixture_line_verified": True},
                {"market": "match_winner", "pick": "A", "line": None,
                 "operator_market_id": "20", "operator_outcome_id": "21", "fixture_line_verified": True},
            ],
        },
    }

def test_extracts_final_symphony_composition_without_economics():
    row = b.build_shadow_composition(playable_match())
    assert row["match_id"] == "m-1"
    assert row["operator"] == "superbet.pl"
    assert row["leg_count"] == 2
    assert row["joint_probability"] == 50.075
    assert row["joint_status"] == "EXACT_STATE"
    assert row["combined_odds"] is None
    assert row["combined_price_status"] == "NOT_AVAILABLE"
    assert row["economic_ready"] is False
    assert "expected_value_net" not in row
    assert "final_stake" not in row


def test_composition_id_is_stable_for_same_leg_set():
    a = b.build_shadow_composition(playable_match())
    m = playable_match()
    m["symphony2_playable"]["signals"].reverse()
    c = b.build_shadow_composition(m)
    assert a["composition_id"] == c["composition_id"]


def test_fails_closed_without_two_verified_legs():
    m = playable_match()
    m["symphony2_playable"]["signals"] = m["symphony2_playable"]["signals"][:1]
    assert b.build_shadow_composition(m) is None

def test_fails_closed_without_joint_probability():
    m = playable_match()
    m["symphony2_playable"]["joint_probability"] = None
    assert b.build_shadow_composition(m) is None


def test_leg_odds_are_never_multiplied_into_builder_price():
    m = playable_match()
    m["symphony2_playable"]["signals"][0]["odds"] = 1.5
    m["symphony2_playable"]["signals"][1]["odds"] = 2.0
    row = b.build_shadow_composition(m)
    assert row["combined_odds"] is None
    assert row["combined_price_status"] == "NOT_AVAILABLE"


def test_only_exact_verified_operator_builder_quote_can_attach_price():
    row = b.build_shadow_composition(playable_match())
    quoted = b.attach_verified_combined_quote(row, {
        "composition_id": row["composition_id"], "operator": "superbet.pl",
        "quote_kind": "BET_BUILDER_COMBINED", "operator_verified": True,
        "freshness_verified": True, "combined_odds": 2.85, "odds_timestamp": "2026-09-20T20:00:00+00:00",
        "source": "superbet_exact_builder_quote",
    })
    assert quoted["combined_odds"] == 2.85
    assert quoted["combined_price_status"] == "VERIFIED"
    assert quoted["economic_ready"] is True


def test_wrong_or_unverified_quote_fails_closed():
    row = b.build_shadow_composition(playable_match())
    q = {"composition_id": row["composition_id"], "operator": "superbet.pl",
         "quote_kind": "BET_BUILDER_COMBINED", "operator_verified": False,
         "combined_odds": 9.99}
    assert b.attach_verified_combined_quote(row, q)["combined_odds"] is None


def test_single_leg_direct_offer_object_is_not_a_builder_quote():
    row = b.build_shadow_composition(playable_match())
    direct_match = {
        "match_id": "m-1", "direct_match_verified": True,
        "canonical_selections": [
            {"market": "set1_total", "pick": "over", "line": 8.5,
             "operator_price": 1.50, "operator_price_verified": True},
            {"market": "match_winner", "pick": "A",
             "operator_price": 2.00, "operator_price_verified": True},
        ],
    }
    out = b.attach_verified_combined_quote(row, direct_match)
    assert out["combined_odds"] is None
    assert out["combined_price_status"] == "NOT_AVAILABLE"
    assert out["economic_ready"] is False


def test_conflicting_canonical_match_identity_fails_closed():
    m = playable_match()
    m["id"] = "different-id"
    assert b.build_shadow_composition(m) is None


def test_missing_operator_leg_identity_fails_closed():
    m = playable_match()
    m["symphony2_playable"]["signals"][0]["operator_outcome_id"] = None
    assert b.build_shadow_composition(m) is None


def test_stale_or_unverified_freshness_quote_fails_closed():
    row = b.build_shadow_composition(playable_match())
    q = {
        "composition_id": row["composition_id"], "operator": "superbet.pl",
        "quote_kind": "BET_BUILDER_COMBINED", "operator_verified": True,
        "freshness_verified": False, "combined_odds": 2.85,
        "odds_timestamp": "2026-09-20T20:00:00+00:00",
        "source": "superbet_exact_builder_quote",
    }
    out = b.attach_verified_combined_quote(row, q)
    assert out["combined_odds"] is None
    assert out["economic_ready"] is False


def _phase2_direct_feed():
    return {
        "generated_at": "2026-09-20T21:30:00+00:00",
        "matches": [{
            "match_id": "m-1", "event_id": "15000001", "direct_match_verified": True,
            "canonical_selections": [
                {"market": "set1_total", "pick": "over", "line": 8.5,
                 "operator_available": True, "operator_price_verified": True,
                 "operator_price": 1.5, "operator_selection_status": "active",
                 "operator_selection_id": "leg-a"},
                {"market": "match_winner", "pick": "A", "line": None,
                 "operator_available": True, "operator_price_verified": True,
                 "operator_price": 2.0, "operator_selection_status": "active",
                 "operator_selection_id": "leg-b"},
            ],
        }],
    }


def _phase2_catalog():
    return {"source_event_id": "15000001", "observed_at": "2026-09-20T21:30:00+00:00",
            "quotes": [{"operator": "superbet.pl", "quote_kind": "SUPERBETS_PREPRICED_COMBINATION",
                        "component_selection_ids": ["leg-b", "leg-a"], "combined_odds": 2.75,
                        "operator_verified": True, "freshness_verified": True,
                        "source_event_id": "15000001", "odds_timestamp": "2026-09-20T21:30:00+00:00",
                        "source": "superbet_direct_public_event_json"}]}


def test_phase2_resolves_only_exact_prepriced_operator_combination():
    composition = b.build_shadow_composition(playable_match())
    quote = b.resolve_prepriced_combined_quote(composition, _phase2_direct_feed(), _phase2_catalog())
    assert quote is not None
    assert quote["composition_id"] == composition["composition_id"]
    assert quote["quote_kind"] == "BET_BUILDER_COMBINED"
    assert quote["combined_odds"] == 2.75
    attached = b.attach_verified_combined_quote(composition, quote)
    assert attached["combined_price_status"] == "VERIFIED"
    assert attached["combined_odds"] == 2.75


def test_phase2_fails_closed_on_snapshot_misalignment_or_missing_exact_row():
    composition = b.build_shadow_composition(playable_match())
    stale = _phase2_catalog()
    stale["observed_at"] = "2026-09-20T21:31:00+00:00"
    assert b.resolve_prepriced_combined_quote(composition, _phase2_direct_feed(), stale) is None
    missing = _phase2_catalog()
    missing["quotes"][0]["component_selection_ids"] = ["leg-a", "leg-c"]
    assert b.resolve_prepriced_combined_quote(composition, _phase2_direct_feed(), missing) is None


def test_phase3_dynamic_sga_quote_resolves_exact_composition():
    composition = b.build_shadow_composition(playable_match())
    payload = {"price": 1.5, "sgaUuid": "sga-1", "status": "ACTIVE",
               "combinationBettingStatus": "ACTIVE", "marketId": "238733", "outcomeId": "16603",
               "legs": [{"oddUuid":"leg-a","status":"ACTIVE"},{"oddUuid":"leg-b","status":"ACTIVE"}]}
    quote = b.resolve_dynamic_combined_quote(composition, _phase2_direct_feed(), payload,
                                             observed_at="2026-09-20T21:31:00+00:00", source_url=d.build_dynamic_sga_quote_url("15000001", ["leg-a", "leg-b"]))
    assert quote is not None
    assert quote["combined_odds"] == 1.5
    assert quote["source_quote_kind"] == "BET_BUILDER_DYNAMIC_SGA"
    attached = b.attach_verified_combined_quote(composition, quote)
    assert attached["combined_price_status"] == "VERIFIED"
    assert attached["combined_odds"] == 1.5
    prov = attached["combined_price_provenance"]
    assert prov["source_quote_kind"] == "BET_BUILDER_DYNAMIC_SGA"
    assert prov["source_event_id"] == "15000001"
    assert prov["operator_combination_selection_id"] == "sga-1"
    assert set(prov["component_selection_ids"]) == {"leg-a", "leg-b"}
    assert prov["source_url"] == d.build_dynamic_sga_quote_url("15000001", ["leg-a", "leg-b"])


def test_phase3_dynamic_sga_quote_fails_closed_on_missing_or_foreign_leg():
    composition = b.build_shadow_composition(playable_match())
    base = {"price": 1.5, "sgaUuid": "sga-1", "status": "ACTIVE",
            "combinationBettingStatus": "ACTIVE", "marketId": "238733", "outcomeId": "16603"}
    missing = dict(base, legs=[{"oddUuid":"leg-a","status":"ACTIVE"}])
    assert b.resolve_dynamic_combined_quote(composition, _phase2_direct_feed(), missing,
                                            observed_at="2026-09-20T21:31:00+00:00", source_url=d.build_dynamic_sga_quote_url("15000001", ["leg-a", "leg-b"])) is None
    foreign = dict(base, legs=[{"oddUuid":"leg-a","status":"ACTIVE"},{"oddUuid":"leg-c","status":"ACTIVE"}])
    assert b.resolve_dynamic_combined_quote(composition, _phase2_direct_feed(), foreign,
                                            observed_at="2026-09-20T21:31:00+00:00", source_url=d.build_dynamic_sga_quote_url("15000001", ["leg-a", "leg-b"])) is None


def _phase6_match(leg_count=4):
    m = playable_match()
    extra = [
        {"market": "set2_total", "pick": "over", "line": 8.5,
         "operator_market_id": "30", "operator_outcome_id": "31", "fixture_line_verified": True},
        {"market": "player_aces", "pick": "A over", "line": 2.5,
         "operator_market_id": "40", "operator_outcome_id": "41", "fixture_line_verified": True},
        {"market": "match_total", "pick": "over", "line": 20.5,
         "operator_market_id": "50", "operator_outcome_id": "51", "fixture_line_verified": True},
        {"market": "total_sets", "pick": "over", "line": 2.5,
         "operator_market_id": "60", "operator_outcome_id": "61", "fixture_line_verified": True},
        {"market": "set3_total", "pick": "over", "line": 8.5,
         "operator_market_id": "70", "operator_outcome_id": "71", "fixture_line_verified": True},
    ]
    m["symphony2_playable"]["signals"].extend(extra[:max(0, leg_count - 2)])
    m["symphony2_playable"]["recommended_leg_count"] = len(m["symphony2_playable"]["signals"])
    return m


def _phase6_direct_feed(leg_count=4):
    m = _phase6_match(leg_count)
    rows = []
    for index, leg in enumerate(m["symphony2_playable"]["signals"]):
        rows.append({
            "market": leg["market"], "pick": leg["pick"], "line": leg.get("line"),
            "operator_available": True, "operator_price_verified": True,
            "operator_price": 1.5 + index / 10, "operator_selection_status": "active",
            "operator_selection_id": f"leg-{chr(ord('a') + index)}",
        })
    return {
        "generated_at": "2026-09-22T09:00:00+00:00",
        "matches": [{
            "match_id": "m-1", "event_id": "15000001", "direct_match_verified": True,
            "canonical_selections": rows,
        }],
    }


def test_phase6a_single_void_plan_is_bounded_and_deterministic():
    composition = b.build_shadow_composition(_phase6_match(4))
    plan = b.build_single_void_reprice_plan(composition, _phase6_direct_feed(4))
    assert plan["scenario_count"] == 4
    assert len(plan["scenarios"]) == 4
    assert plan["single_void_only"] is True
    assert plan["multi_void_supported"] is False
    assert plan["settlement_enabled"] is False
    assert plan["payout_computed"] is False
    assert all(x["remaining_leg_count"] == 3 for x in plan["scenarios"])
    assert all(x["quote_required"] is True for x in plan["scenarios"])
    assert len({x["scenario_id"] for x in plan["scenarios"]}) == 4
    again = b.build_single_void_reprice_plan(composition, _phase6_direct_feed(4))
    assert [x["scenario_id"] for x in plan["scenarios"]] == [x["scenario_id"] for x in again["scenarios"]]


def test_phase6a_two_leg_single_void_is_explicit_nd_not_synthetic_price():
    composition = b.build_shadow_composition(playable_match())
    plan = b.build_single_void_reprice_plan(composition, _phase2_direct_feed())
    assert plan["scenario_count"] == 2
    assert all(x["remaining_leg_count"] == 1 for x in plan["scenarios"])
    assert all(x["quote_required"] is False for x in plan["scenarios"])
    assert all(x["evidence_status"] == "N/D_SINGLE_LEG_REMAINDER" for x in plan["scenarios"])
    assert all(x["combined_odds"] is None for x in plan["scenarios"])


def test_phase6a_rejects_more_than_six_legs():
    composition = b.build_shadow_composition(_phase6_match(7))
    assert composition["leg_count"] == 7
    assert b.build_single_void_reprice_plan(composition, _phase6_direct_feed(7)) is None


def test_phase6a_resolves_exact_operator_reprice_without_settlement():
    composition = b.build_shadow_composition(_phase6_match(4))
    direct = _phase6_direct_feed(4)
    plan = b.build_single_void_reprice_plan(composition, direct)
    target = plan["scenarios"][0]
    remaining = target["remaining_component_selection_ids"]
    payload = {
        "price": 2.35, "sgaUuid": "reprice-1", "status": "ACTIVE",
        "combinationBettingStatus": "ACTIVE", "marketId": "238733", "outcomeId": "16603",
        "legs": [{"oddUuid": sid, "status": "ACTIVE"} for sid in remaining],
    }
    observations = {
        target["scenario_id"]: {
            "payload": payload,
            "observed_at": "2026-09-22T09:01:00+00:00",
            "source_url": d.build_dynamic_sga_quote_url("15000001", remaining),
        }
    }
    evidence = b.resolve_single_void_reprice_evidence(composition, direct, observations)
    resolved = evidence["scenarios"][0]
    assert resolved["evidence_status"] == "EXACT_OPERATOR_REPRICE"
    assert resolved["combined_odds"] == 2.35
    assert resolved["quote_provenance"]["operator_combination_selection_id"] == "reprice-1"
    assert evidence["settlement_enabled"] is False
    assert evidence["settlement_ready"] is False
    assert evidence["payout_computed"] is False
    assert evidence["result_inferred"] is False


def test_phase6a_missing_or_foreign_reprice_stays_nd():
    composition = b.build_shadow_composition(_phase6_match(4))
    direct = _phase6_direct_feed(4)
    plan = b.build_single_void_reprice_plan(composition, direct)
    target = plan["scenarios"][1]
    observations = {
        target["scenario_id"]: {
            "payload": {
                "price": 9.99, "sgaUuid": "foreign", "status": "ACTIVE",
                "combinationBettingStatus": "ACTIVE", "marketId": "238733", "outcomeId": "16603",
                "legs": [{"oddUuid": "foreign-leg", "status": "ACTIVE"}],
            },
            "observed_at": "2026-09-22T09:01:00+00:00",
            "source_url": "https://example.invalid/not-authority",
        }
    }
    evidence = b.resolve_single_void_reprice_evidence(composition, direct, observations)
    assert evidence["scenarios"][1]["evidence_status"] == "N/D_EXACT_OPERATOR_REPRICE_UNAVAILABLE"
    assert evidence["scenarios"][1]["combined_odds"] is None
    assert all(row["combined_odds"] is None for i, row in enumerate(evidence["scenarios"]) if i != 1)
