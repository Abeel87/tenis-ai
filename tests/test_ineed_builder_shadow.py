import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import ineed_builder_shadow as b


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
