from __future__ import annotations

"""Canonical Superbet -> model-family registry for the future NEURO shadow layer.

Audit/metadata only. This module is intentionally not imported by production
PLAYABLE, Symphony2, model training, settlement or frontend runtime code.
"""

VERSION = "neuro-market-registry-v9.3.4"

# coverage_status is deliberately descriptive rather than promotional.
# NEURO eligibility does not mean a market may influence production; it only
# means a future shadow model may collect/evaluate predictions for that family.
MARKET_REGISTRY = {
    "match_winner": {"family": "RESULT", "sources": ["base", "catboost", "tabpfn", "adaptive", "surface_elo"], "coverage_status": "EXISTING_SUPPORTED", "neuro_eligible": True},
    "set1_winner": {"family": "RESULT", "sources": ["player_model", "state_distribution"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP", "neuro_eligible": True},
    "set2_winner": {"family": "RESULT", "sources": ["player_model", "state_distribution"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP", "neuro_eligible": True},
    "set3_winner": {"family": "RESULT", "sources": ["player_model", "state_distribution"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP", "neuro_eligible": True},
    "exact_match_score": {"family": "EXACT_SCORE", "sources": ["state_distribution", "symphony2"], "coverage_status": "EXISTING_SUPPORTED", "neuro_eligible": True},
    "set1_exact_score": {"family": "EXACT_SCORE", "sources": ["state_distribution", "symphony2"], "coverage_status": "EXISTING_SUPPORTED", "neuro_eligible": True},
    "set2_exact_score": {"family": "EXACT_SCORE", "sources": ["state_distribution"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP", "neuro_eligible": True},
    "match_total": {"family": "TOTALS", "sources": ["base", "catboost", "tabpfn", "adaptive", "state_distribution"], "coverage_status": "EXISTING_SUPPORTED", "neuro_eligible": True},
    "set1_total": {"family": "TOTALS", "sources": ["joint_builder", "state_distribution", "symphony2"], "coverage_status": "EXISTING_SUPPORTED", "neuro_eligible": True},
    "set2_total": {"family": "TOTALS", "sources": ["state_distribution"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP_SETTLEMENT_GAP", "neuro_eligible": True},
    "set3_total": {"family": "TOTALS", "sources": ["state_distribution"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP", "neuro_eligible": True},
    "total_sets": {"family": "TOTALS", "sources": ["state_distribution", "symphony2"], "coverage_status": "EXISTING_SUPPORTED", "neuro_eligible": True},
    "game_state": {"family": "GAME_STATE_EARLY", "sources": ["early_hold", "pbp", "state_distribution"], "coverage_status": "PBP_GAP", "neuro_eligible": True, "pbp_required": True},
    "set2_game_state": {"family": "GAME_STATE_EARLY", "sources": ["pbp", "state_distribution"], "coverage_status": "PBP_GAP", "neuro_eligible": True, "pbp_required": True},
    "set1_tiebreak": {"family": "GAME_STATE_EARLY", "sources": ["early_hold", "pbp", "state_distribution"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP", "neuro_eligible": True},
    "match_game_handicap": {"family": "HANDICAP", "sources": ["match_distribution", "base", "adaptive"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP_SETTLEMENT_GAP", "neuro_eligible": True},
    "set1_game_handicap": {"family": "HANDICAP", "sources": ["set1_distribution", "joint_builder"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP_SETTLEMENT_GAP", "neuro_eligible": True},
    "set2_game_handicap": {"family": "HANDICAP", "sources": ["set2_distribution"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP_SETTLEMENT_GAP", "neuro_eligible": True},
    "set_handicap": {"family": "HANDICAP", "sources": ["sets_distribution"], "coverage_status": "SETTLEMENT_GAP", "neuro_eligible": False},
    "player_total_games": {"family": "PLAYER_TOTAL", "sources": ["player_model", "player_intelligence", "match_distribution"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP_SETTLEMENT_GAP", "neuro_eligible": True},
    "match_total_aces": {"family": "SERVE", "sources": ["serve_props", "player_intelligence"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP", "neuro_eligible": True},
    "most_aces": {"family": "SERVE", "sources": ["serve_props", "player_intelligence"], "coverage_status": "EXISTING_MODEL_MAPPING_GAP", "neuro_eligible": True},
    "any_set_to_nil": {"family": "SET_OUTCOME", "sources": ["sets_distribution", "candidate_shadow_v925"], "coverage_status": "EXISTING_SHADOW_EVIDENCE", "neuro_eligible": True},
    "exact_sets": {"family": "SET_OUTCOME", "sources": ["sets_distribution", "candidate_shadow_v925"], "coverage_status": "EXISTING_SHADOW_EVIDENCE", "neuro_eligible": True},
    "p1_exactly_1_set": {"family": "SET_OUTCOME", "sources": ["player_model", "sets_distribution", "candidate_shadow_v925"], "coverage_status": "EXISTING_SHADOW_EVIDENCE", "neuro_eligible": True},
    "p1_exactly_2_sets": {"family": "SET_OUTCOME", "sources": ["player_model", "sets_distribution", "candidate_shadow_v925"], "coverage_status": "EXISTING_SHADOW_EVIDENCE", "neuro_eligible": True},
    "p2_exactly_1_set": {"family": "SET_OUTCOME", "sources": ["player_model", "sets_distribution", "candidate_shadow_v925"], "coverage_status": "EXISTING_SHADOW_EVIDENCE", "neuro_eligible": True},
    "p2_exactly_2_sets": {"family": "SET_OUTCOME", "sources": ["player_model", "sets_distribution", "candidate_shadow_v925"], "coverage_status": "EXISTING_SHADOW_EVIDENCE", "neuro_eligible": True},
    "p1_wins_a_set": {"family": "SET_OUTCOME", "sources": ["player_model", "sets_distribution", "candidate_shadow_v925"], "coverage_status": "EXISTING_SHADOW_EVIDENCE", "neuro_eligible": True},
    "p2_wins_a_set": {"family": "SET_OUTCOME", "sources": ["player_model", "sets_distribution", "candidate_shadow_v925"], "coverage_status": "EXISTING_SHADOW_EVIDENCE", "neuro_eligible": True},
    "match_games_parity": {"family": "PARITY", "sources": ["candidate_shadow_v925"], "coverage_status": "TRUE_NEURO_CANDIDATE_WEAK_BASE", "neuro_eligible": False},
    "set1_games_parity": {"family": "PARITY", "sources": ["candidate_shadow_v925"], "coverage_status": "TRUE_NEURO_CANDIDATE_WEAK_BASE", "neuro_eligible": False},
    "set2_games_parity": {"family": "PARITY", "sources": ["candidate_shadow_v925"], "coverage_status": "TRUE_NEURO_CANDIDATE_WEAK_BASE", "neuro_eligible": False},
}


def market_meta(canonical_market: str) -> dict:
    """Return a copy so callers cannot mutate the registry in place."""
    return dict(MARKET_REGISTRY.get(str(canonical_market or ""), {
        "family": "UNASSIGNED",
        "sources": [],
        "coverage_status": "UNASSIGNED",
        "neuro_eligible": False,
    }))


def validate_registry(markets) -> dict:
    requested = {str(m) for m in markets if str(m)}
    missing = sorted(requested - set(MARKET_REGISTRY))
    return {
        "version": VERSION,
        "requested": len(requested),
        "classified": len(requested) - len(missing),
        "missing": missing,
        "complete": not missing,
    }
