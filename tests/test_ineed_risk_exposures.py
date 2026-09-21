from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import ineed_builder_shadow as builder
import ineed_money as money

NOW = datetime(2026, 9, 21, 7, 30, tzinfo=timezone.utc)

CFG = {
    "currency": "PLN", "minimum_stake": 2.0, "stake_rounding": 0.01,
    "stake_tax_rate": 0.12, "high_win_tax_rate": 0.10,
    "high_win_tax_threshold_pln": 2280.0, "high_win_tax_trigger": "above",
    "fractional_kelly": 0.25, "max_single_bet_pct": 0.03,
    "max_match_exposure_pct": 0.03, "max_player_exposure_pct": 0.03,
    "max_market_exposure_pct": 0.15, "max_total_exposure_pct": 0.15,
    "minimum_net_ev": 0.05, "minimum_edge_pp": 4.0,
    "minimum_confidence": None, "minimum_odds": 1.01,
    "maximum_odds": None, "odds_max_age_minutes": 108,
    "drawdown": {"caution": 0.10, "defensive": 0.20, "halted": 0.30},
}
CFG["risk_profiles"] = {
    "NORMAL": {"stake_multiplier": 1.0, "exposure_multiplier": 1.0, "minimum_net_ev": 0.05, "minimum_edge_pp": 4.0},
    "CAUTION": {"stake_multiplier": 0.67, "exposure_multiplier": 0.67, "minimum_net_ev": 0.07, "minimum_edge_pp": 5.0},
    "DEFENSIVE": {"stake_multiplier": 0.33, "exposure_multiplier": 0.33, "minimum_net_ev": 0.10, "minimum_edge_pp": 6.0},
    "HALTED": {"stake_multiplier": 0.0, "exposure_multiplier": 0.0, "minimum_net_ev": 1.0, "minimum_edge_pp": 100.0},
}
CFG["version"] = "risk-exposure-test"


def playable_result(probability=70.0):
    return [{
        "match_id": "m-1", "p1": "A", "p2": "B",
        "symphony2_playable": {
            "playable": True, "final_playable_authority": True,
            "authority": money.FINAL_AUTHORITY, "operator": money.OPERATOR,
            "signals": [{
                "market": "match_winner", "pick": "A",
                "operator_model_probability": probability,
                "learning_reliability": 0.9,
            }],
        },
    }]


def direct_quote(odds=2.0):
    return {"operator": money.OPERATOR, "status": "OK", "generated_at": "2026-09-21T07:20:00+00:00", "matches": [{
        "match_id": "m-1", "p1": "A", "p2": "B", "direct_match_verified": True,
        "canonical_selections": [
            {"market": "match_winner", "pick": "A", "operator_available": True,
             "operator_price_verified": True, "operator_price": odds, "operator_selection_status": "active"},
            {"market": "match_winner", "pick": "B", "operator_available": True,
             "operator_price_verified": True, "operator_price": 2.0, "operator_selection_status": "active"},
        ],
    }]}


def legacy_state(open_bets=None, *, equity=200.0, peak=200.0):
    open_bets = list(open_bets or [])
    reserved = sum(float(row.get("stake") or 0.0) for row in open_bets if row.get("status") in money.OPEN)
    return {
        "experiment": {"starting_bankroll": 200.0},
        "available_capital": equity - reserved,
        "bankroll_equity": equity,
        "peak_bankroll": peak,
        "open_bets": open_bets,
    }


def v1_bet(*, stake=5.0, match_id="other", market="set1_total", p1="X", p2="Y", status="PENDING"):
    return {
        "id": "bet-1", "status": status, "stake": stake,
        "match_id": match_id, "market": market,
        "placement_snapshot": {"p1": p1, "p2": p2},
    }

def test_legacy_open_bets_normalize_to_v1_risk_exposures_only():
    state = legacy_state([
        v1_bet(stake=5.0, match_id="m-1", market="match_winner", p1="A", p2="B"),
        v1_bet(stake=7.0, status="WIN"),
    ])
    rows = money.normalize_risk_exposures(state)
    assert rows == [{
        "economic_unit": money.RISK_UNIT_V1,
        "status": "PENDING", "stake": 5.0, "match_id": "m-1",
        "players": ["A", "B"], "markets": ["match_winner"],
        "source_id": "bet-1", "composition_id": None,
    }]


def test_explicit_risk_exposures_reconstruct_shared_equity_once():
    state = {
        "available_capital": 188.0,
        "risk_exposures": [
            {"economic_unit": money.RISK_UNIT_V1, "status": "PENDING", "stake": 5.0,
             "match_id": "m-v1", "players": ["A", "B"], "markets": ["match_winner"]},
            {"economic_unit": money.RISK_UNIT_BUILDER, "status": "PENDING", "stake": 7.0,
             "match_id": "m-bb", "players": ["C", "D"],
             "markets": ["set1_total", "match_winner"], "composition_id": "bb-1"},
        ],
    }
    risk = money.risk_exposure_state(state)
    assert risk["active_exposure"] == 12.0
    assert risk["bankroll_equity"] == 200.0

def test_v1_legacy_state_equals_explicit_risk_read_model_exactly():
    legacy = legacy_state([
        v1_bet(stake=5.0, match_id="other", market="set1_total", p1="A", p2="C"),
        {**v1_bet(stake=3.0, match_id="m-1", market="set1_winner", p1="X", p2="Y"), "id": "bet-2"},
    ], equity=200.0, peak=200.0)
    explicit = deepcopy(legacy)
    explicit["risk_exposures"] = money.normalize_risk_exposures(legacy)
    assert money.evaluate(playable_result(), direct_quote(), CFG, legacy, now=NOW) == money.evaluate(
        playable_result(), direct_quote(), CFG, explicit, now=NOW
    )


def test_explicit_builder_exposure_limits_v1_without_entering_open_bets():
    state = {
        "experiment": {"starting_bankroll": 200.0},
        "available_capital": 194.0,
        "peak_bankroll": 200.0,
        "open_bets": [],
        "risk_exposures": [{
            "economic_unit": money.RISK_UNIT_BUILDER, "status": "PENDING", "stake": 6.0,
            "match_id": "m-1", "players": ["A", "B"],
            "markets": ["set1_total", "match_winner"], "composition_id": "bb-existing",
            "source_id": "builder-ticket:bb-existing",
        }],
    }
    row = money.evaluate(playable_result(), direct_quote(), CFG, state, now=NOW)[0]
    assert row["reason_code"] in {"MATCH_EXPOSURE_LIMIT", "CORRELATION_LIMIT", "STAKE_BELOW_MINIMUM"}
    assert state["open_bets"] == []

def quoted_builder():
    match = {
        "match_id": "m-1", "p1": "A", "p2": "B",
        "symphony2_playable": {
            "playable": True, "final_playable_authority": True,
            "authority": "SYMPHONY2_FINAL_PLAYABLE", "operator": "superbet.pl",
            "recommended_leg_count": 2, "joint_probability": 90.0, "joint_status": "EXACT_STATE",
            "signals": [
                {"market": "set1_total", "pick": "over", "line": 8.5,
                 "operator_market_id": "10", "operator_outcome_id": "11", "fixture_line_verified": True, "learning_reliability": 0.9},
                {"market": "match_winner", "pick": "A", "line": None,
                 "operator_market_id": "20", "operator_outcome_id": "21", "fixture_line_verified": True, "learning_reliability": 0.8},
            ],
        },
    }
    row = builder.build_shadow_composition(match)
    return builder.attach_verified_combined_quote(row, {
        "composition_id": row["composition_id"], "operator": "superbet.pl",
        "quote_kind": "BET_BUILDER_COMBINED", "operator_verified": True,
        "freshness_verified": True, "combined_odds": 1.5,
        "odds_timestamp": "2026-09-21T07:20:00+00:00",
        "source": "superbet_dynamic_betbuilder_getSgaOddPrice_v2",
        "source_quote_kind": "BET_BUILDER_DYNAMIC_SGA", "source_event_id": "15000001",
        "operator_combination_selection_id": "sga-1",
        "component_selection_ids": ["leg-a", "leg-b"], "source_url": "https://example.invalid/proof",
    })

def test_builder_legacy_v1_exposure_equals_explicit_risk_read_model():
    open_bet = v1_bet(stake=5.0, match_id="other", market="set1_total", p1="A", p2="C")
    legacy = legacy_state([open_bet], equity=200.0, peak=200.0)
    explicit = deepcopy(legacy)
    explicit["risk_exposures"] = money.normalize_risk_exposures(legacy)
    a = builder.evaluate_builder_economics_shadow([quoted_builder()], CFG, legacy, now=NOW)
    b = builder.evaluate_builder_economics_shadow([quoted_builder()], CFG, explicit, now=NOW)
    assert a == b


def test_existing_builder_composition_is_rejected_from_shared_risk_model():
    row = quoted_builder()
    state = {
        "experiment": {"starting_bankroll": 200.0}, "available_capital": 198.0,
        "peak_bankroll": 200.0, "open_bets": [],
        "risk_exposures": [{
            "economic_unit": money.RISK_UNIT_BUILDER, "status": "PENDING", "stake": 2.0,
            "match_id": "other-match", "players": ["X", "Y"], "markets": ["other"],
            "composition_id": row["composition_id"], "source_id": f"builder-ticket:{row['composition_id']}",
        }],
    }
    out = builder.evaluate_builder_economics_shadow([row], CFG, state, now=NOW)[0]
    assert out["status"] == "SHADOW_REJECTED"
    assert out["reason_code"] == "DUPLICATE_COMPOSITION"
    assert out["reservation_proposal"] is None


@pytest.mark.parametrize("bad", [{}, "bad", 7])
def test_explicit_risk_exposures_fail_closed_on_non_list(bad):
    with pytest.raises(ValueError, match="risk_exposures must be a list"):
        money.normalize_risk_exposures({"risk_exposures": bad})


def test_builder_shaped_legacy_open_bet_fails_closed():
    bad = v1_bet(stake=2.0, match_id="m-1", market="BET_BUILDER", p1="A", p2="B")
    bad["placement_snapshot"]["composition_id"] = "bb-illegal-v1-lane"
    with pytest.raises(ValueError, match="builder exposure must not use V1 open_bets"):
        money.normalize_risk_exposures(legacy_state([bad]))


def test_explicit_v1_exposure_rejects_composition_identity():
    with pytest.raises(ValueError, match="one market and no composition_id"):
        money.normalize_risk_exposures({"risk_exposures": [{
            "economic_unit": money.RISK_UNIT_V1, "status": "PENDING", "stake": 2.0,
            "match_id": "m-1", "players": ["A", "B"], "markets": ["match_winner"],
            "composition_id": "bb-not-v1",
        }]})


def test_explicit_builder_exposure_requires_two_players():
    with pytest.raises(ValueError, match="two players"):
        money.normalize_risk_exposures({"risk_exposures": [{
            "economic_unit": money.RISK_UNIT_BUILDER, "status": "PENDING", "stake": 2.0,
            "match_id": "m-1", "players": ["A"], "markets": ["match_winner"],
            "composition_id": "bb-1",
        }]})


def test_builder_market_concentration_counts_existing_builder_stake_once_per_market():
    c = deepcopy(CFG)
    c["max_single_bet_pct"] = 1.0
    c["max_match_exposure_pct"] = 1.0
    c["max_player_exposure_pct"] = 1.0
    c["max_total_exposure_pct"] = 1.0
    state = {
        "experiment": {"starting_bankroll": 200.0}, "available_capital": 171.0,
        "peak_bankroll": 200.0, "open_bets": [],
        "risk_exposures": [{
            "economic_unit": money.RISK_UNIT_BUILDER, "status": "PENDING", "stake": 29.0,
            "match_id": "other-match", "players": ["X", "Y"],
            "markets": ["set1_total", "other"], "composition_id": "bb-other",
        }],
    }
    out = builder.evaluate_builder_economics_shadow([quoted_builder()], c, state, now=NOW)[0]
    assert out["status"] == "SHADOW_REJECTED"
    assert out["reason_code"] == "MARKET_EXPOSURE_LIMIT"
