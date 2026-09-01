from backend.neuro_market_audit_v934 import build_audit


def test_audit_separates_mapping_evidence_pbp_and_true_neuro_gaps_exclusively():
    symphony = {
        "current_offer": {
            "probability_diagnostics": {
                "per_market": {
                    "match_winner": {"offered_selections": 2, "scored_selections": 2, "unscored_zero_support": 0, "support_rows": 158},
                    "player_total_games": {"offered_selections": 4, "scored_selections": 0, "unscored_zero_support": 4, "support_rows": 0},
                    "game_state": {"offered_selections": 6, "scored_selections": 0, "unscored_zero_support": 6, "support_rows": 0},
                    "match_games_parity": {"offered_selections": 2, "scored_selections": 0, "unscored_zero_support": 2, "support_rows": 0},
                    "any_set_to_nil": {"offered_selections": 2, "scored_selections": 0, "unscored_zero_support": 2, "support_rows": 0},
                }
            }
        }
    }
    candidate = {
        "by_market": {
            "any_set_to_nil": {
                "captured": 46,
                "settled": 46,
                "accuracy": 87.0,
                "brier": 0.1207,
                "review_ready": True,
                "promotion_status": "REVIEW_READY",
            }
        }
    }

    audit = build_audit(symphony, candidate)
    summary = audit["summary"]
    assert summary["exact_operator_selections"] == 16
    assert summary["scored"] == 2
    assert summary["unscored"] == 14
    assert summary["exclusive_unscored_by_gap_class"] == {
        "PBP_GAP": 6,
        "SETTLEMENT_GAP": 4,
        "SHADOW_EVIDENCE": 2,
        "SUPPORTED": 0,
        "TRUE_NEURO_CANDIDATE": 2,
    }
    assert sum(summary["exclusive_unscored_by_gap_class"].values()) == summary["unscored"]

    by_market = {row["canonical_market"]: row for row in audit["markets"]}
    assert by_market["any_set_to_nil"]["candidate_review_ready"] is True
    assert by_market["any_set_to_nil"]["candidate_accuracy"] == 87.0
    assert by_market["any_set_to_nil"]["primary_gap_class"] == "SHADOW_EVIDENCE"
    assert by_market["game_state"]["primary_gap_class"] == "PBP_GAP"
    assert by_market["game_state"]["pbp_required"] is True
    assert by_market["player_total_games"]["primary_gap_class"] == "SETTLEMENT_GAP"
    assert by_market["match_games_parity"]["primary_gap_class"] == "TRUE_NEURO_CANDIDATE"

    queue = audit["priority_queue"]
    assert queue[0]["canonical_market"] == "any_set_to_nil"
    assert all(row["unscored"] > 0 for row in queue)
    assert all(queue[i]["priority_score"] >= queue[i + 1]["priority_score"] for i in range(len(queue) - 1))


def test_audit_is_explicitly_read_only_and_non_prod():
    audit = build_audit({"current_offer": {"probability_diagnostics": {"per_market": {}}}}, {"by_market": {}})
    assert audit["contract"] == {
        "read_only": True,
        "production_influence": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
    }