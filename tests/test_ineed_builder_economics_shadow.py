import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import ineed_builder_shadow as b

NOW = datetime(2026, 9, 20, 22, 1, tzinfo=timezone.utc)


def cfg():
    return {
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
        "risk_profiles": {
            "NORMAL": {"stake_multiplier": 1.0, "exposure_multiplier": 1.0, "minimum_net_ev": 0.05, "minimum_edge_pp": 4.0},
            "CAUTION": {"stake_multiplier": 0.67, "exposure_multiplier": 0.67, "minimum_net_ev": 0.07, "minimum_edge_pp": 5.0},
            "DEFENSIVE": {"stake_multiplier": 0.33, "exposure_multiplier": 0.33, "minimum_net_ev": 0.10, "minimum_edge_pp": 6.0},
            "HALTED": {"stake_multiplier": 0.0, "exposure_multiplier": 0.0, "minimum_net_ev": 1.0, "minimum_edge_pp": 100.0},
        },
    }


def state(*, available=200.0, equity=200.0, peak=200.0, open_bets=None, risk_exposures=None):
    out = {
        "available_capital": available,
        "bankroll_equity": equity,
        "peak_bankroll": peak,
        "open_bets": list(open_bets or []),
        "experiment": {"starting_bankroll": 200.0},
    }
    if risk_exposures is not None:
        out["risk_exposures"] = list(risk_exposures)
    return out


def quoted_builder(*, match_id="m-1", p1="A", p2="B", joint=90.0, odds=1.5, ts="2026-09-20T21:31:00+00:00"):
    match = {
        "match_id": match_id, "p1": p1, "p2": p2,
        "symphony2_playable": {
            "playable": True, "final_playable_authority": True,
            "authority": "SYMPHONY2_FINAL_PLAYABLE", "operator": "superbet.pl",
            "recommended_leg_count": 2, "joint_probability": joint, "joint_status": "EXACT_STATE",
            "signals": [
                {"market": "set1_total", "pick": "over", "line": 8.5,
                 "operator_market_id": "10", "operator_outcome_id": "11", "fixture_line_verified": True,
                 "learning_reliability": 0.9},
                {"market": "match_winner", "pick": p1, "line": None,
                 "operator_market_id": "20", "operator_outcome_id": "21", "fixture_line_verified": True,
                 "learning_reliability": 0.8},
            ],
        },
    }
    row = b.build_shadow_composition(match)
    quote = {
        "composition_id": row["composition_id"], "operator": "superbet.pl",
        "quote_kind": "BET_BUILDER_COMBINED", "operator_verified": True,
        "freshness_verified": True, "combined_odds": odds, "odds_timestamp": ts,
        "source": "superbet_dynamic_betbuilder_getSgaOddPrice_v2",
        "source_quote_kind": "BET_BUILDER_DYNAMIC_SGA", "source_event_id": "15000001",
        "operator_combination_selection_id": "sga-1",
        "component_selection_ids": ["leg-a", "leg-b"],
        "source_url": "https://production-superbet-bmb.freetls.fastly.net/betbuilder/v2/getSgaOddPrice?proof=1",
    }
    return b.attach_verified_combined_quote(row, quote)


def test_builder_economics_uses_joint_probability_and_exact_price_once():
    out = b.evaluate_builder_economics_shadow([quoted_builder()], cfg(), state(), now=NOW)
    assert len(out) == 1
    row = out[0]
    assert row["status"] == "SHADOW_QUALIFIED"
    assert row["runtime_publishable"] is False
    assert row["automatic_real_betting"] is False
    assert row["joint_probability"] == 90.0
    assert row["model_probability"] == pytest.approx(0.9)
    assert row["odds"] == 1.5
    assert row["raw_implied_probability"] == pytest.approx(2 / 3)
    assert row["no_vig_probability"] is None
    assert row["expected_value_net"] == pytest.approx(0.188)
    assert row["final_stake"] == pytest.approx(6.0)
    assert row["potential_payout"] == pytest.approx(7.92)
    reservation = row["reservation_proposal"]
    assert reservation["status"] == "SHADOW_PROPOSED"
    assert reservation["amount"] == pytest.approx(6.0)
    assert reservation["reservation_key"] == f"builder:{row['composition_id']}"


def test_leg_odds_cannot_change_builder_economics():
    baseline = quoted_builder()
    altered = quoted_builder()
    altered["legs"][0]["odds"] = 99.0
    altered["legs"][1]["odds"] = 0.01
    a = b.evaluate_builder_economics_shadow([baseline], cfg(), state(), now=NOW)[0]
    c = b.evaluate_builder_economics_shadow([altered], cfg(), state(), now=NOW)[0]
    assert a["expected_value_net"] == c["expected_value_net"]
    assert a["final_stake"] == c["final_stake"]


def test_missing_or_stale_builder_quote_fails_closed():
    missing = quoted_builder()
    missing["combined_odds"] = None
    missing["combined_price_status"] = "NOT_AVAILABLE"
    missing["economic_ready"] = False
    stale = quoted_builder(ts="2026-09-20T18:00:00+00:00")
    rows = b.evaluate_builder_economics_shadow([missing, stale], cfg(), state(), now=NOW)
    assert rows[0]["status"] == "SHADOW_REJECTED"
    assert rows[0]["reason_code"] == "NO_EXACT_OPERATOR_BUILDER_QUOTE"
    assert rows[1]["status"] == "SHADOW_EXPIRED"
    assert rows[1]["reason_code"] == "STALE_ODDS"
    assert all(row.get("reservation_proposal") is None for row in rows)


def test_halted_risk_has_no_builder_reservation():
    row = b.evaluate_builder_economics_shadow(
        [quoted_builder()], cfg(), state(available=120.0, equity=120.0, peak=200.0), now=NOW
    )[0]
    assert row["status"] == "SHADOW_REJECTED"
    assert row["reason_code"] == "RISK_ENGINE_HALTED"
    assert row["reservation_proposal"] is None


def test_existing_same_match_exposure_blocks_double_reservation():
    open_bet = {
        "status": "PENDING", "stake": 5.0, "match_id": "m-1", "market": "other",
        "placement_snapshot": {"p1": "A", "p2": "B"},
    }
    row = b.evaluate_builder_economics_shadow(
        [quoted_builder()], cfg(), state(available=195.0, equity=200.0, open_bets=[open_bet]), now=NOW
    )[0]
    assert row["status"] == "SHADOW_REJECTED"
    assert row["reason_code"] == "MATCH_EXPOSURE_LIMIT"
    assert row["reservation_proposal"] is None


def test_constituent_market_exposure_blocks_builder_once():
    c = cfg()
    c["max_single_bet_pct"] = 1.0
    c["max_match_exposure_pct"] = 1.0
    c["max_player_exposure_pct"] = 1.0
    c["max_total_exposure_pct"] = 1.0
    open_bet = {
        "status": "PENDING", "stake": 29.0, "match_id": "other-match", "market": "set1_total",
        "placement_snapshot": {"p1": "X", "p2": "Y"},
    }
    row = b.evaluate_builder_economics_shadow(
        [quoted_builder()], c, state(available=171.0, equity=200.0, open_bets=[open_bet]), now=NOW
    )[0]
    assert row["status"] == "SHADOW_REJECTED"
    assert row["reason_code"] == "MARKET_EXPOSURE_LIMIT"
    assert row["reservation_proposal"] is None


def test_duplicate_composition_gets_only_one_reservation_proposal():
    first = quoted_builder()
    second = quoted_builder()
    rows = b.evaluate_builder_economics_shadow([first, second], cfg(), state(), now=NOW)
    assert len(rows) == 2
    proposals = [row for row in rows if row.get("reservation_proposal")]
    assert len(proposals) == 1
    rejected = [row for row in rows if row.get("reason_code") == "DUPLICATE_COMPOSITION"]
    assert len(rejected) == 1
    assert rejected[0]["status"] == "SHADOW_REJECTED"


def test_low_ev_builder_is_rejected_without_reservation():
    row = b.evaluate_builder_economics_shadow(
        [quoted_builder(joint=70.0, odds=1.5)], cfg(), state(), now=NOW
    )[0]
    assert row["status"] == "SHADOW_REJECTED"
    assert row["reason_code"] == "LOW_EV"
    assert row["expected_value_net"] == pytest.approx(-0.076)
    assert row["reservation_proposal"] is None


def test_builder_output_never_uses_live_v1_qualified_status():
    rows = b.evaluate_builder_economics_shadow([quoted_builder()], cfg(), state(), now=NOW)
    assert all(row["status"] != "QUALIFIED" for row in rows)
    assert all(row["runtime_publishable"] is False for row in rows)


def test_missing_player_identity_fails_closed_before_risk_allocation():
    row = quoted_builder()
    row["p1"] = None
    out = b.evaluate_builder_economics_shadow([row], cfg(), state(), now=NOW)[0]
    assert out["status"] == "SHADOW_REJECTED"
    assert out["reason_code"] == "INVALID_COMPOSITION"
    assert out["reservation_proposal"] is None


def test_component_identity_count_must_match_builder_leg_count():
    row = quoted_builder()
    row["combined_price_provenance"]["component_selection_ids"] = ["leg-a", "leg-b", "leg-c"]
    out = b.evaluate_builder_economics_shadow([row], cfg(), state(), now=NOW)[0]
    assert out["status"] == "SHADOW_REJECTED"
    assert out["reason_code"] == "NO_EXACT_OPERATOR_BUILDER_QUOTE"
    assert out["reservation_proposal"] is None


def test_existing_shared_risk_same_composition_is_idempotently_rejected():
    row = quoted_builder()
    existing = {
        "economic_unit": "BET_BUILDER_COMPOSITION", "status": "SHADOW_RESERVED", "stake": 2.0,
        "match_id": "other-match", "players": ["X", "Y"], "markets": ["other"],
        "composition_id": row["composition_id"],
        "source_id": f"builder-ticket:{row['composition_id']}",
    }
    c = cfg()
    c["max_single_bet_pct"] = 1.0
    c["max_match_exposure_pct"] = 1.0
    c["max_player_exposure_pct"] = 1.0
    c["max_market_exposure_pct"] = 1.0
    c["max_total_exposure_pct"] = 1.0
    out = b.evaluate_builder_economics_shadow(
        [row], c, state(available=198.0, equity=200.0, risk_exposures=[existing]), now=NOW
    )[0]
    assert out["status"] == "SHADOW_REJECTED"
    assert out["reason_code"] == "DUPLICATE_COMPOSITION"
    assert out["reservation_proposal"] is None
