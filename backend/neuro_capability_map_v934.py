from __future__ import annotations

"""Read-only capability map for recovering Superbet coverage before NEURO.

This module answers a narrower question than the market registry: can an uncovered
canonical market be derived from model/state information that already exists today,
or does it require a real state/model/settlement extension first?

It is audit metadata only and is not imported by PLAYABLE, Symphony2 runtime,
training, weights, settlement or frontend code.
"""

VERSION = "neuro-capability-map-v9.3.4"

DIRECT_STATE_NOW = "DIRECT_STATE_NOW"
STATE_EXTENSION_REQUIRED = "STATE_EXTENSION_REQUIRED"
MODEL_ADAPTER_REQUIRED = "MODEL_ADAPTER_REQUIRED"
PBP_REQUIRED = "PBP_REQUIRED"
SETTLEMENT_FIRST = "SETTLEMENT_FIRST"
WEAK_BASE_NEURO_LATER = "WEAK_BASE_NEURO_LATER"

# `state_fields` names fields already emitted by symphony2_state.build_outcomes.
# A DIRECT_STATE_NOW classification means the probability is derivable from the
# present shared state without inventing a new model. It still requires SHADOW
# validation before any production use.
CAPABILITY_MAP = {
    "match_winner": {"capability": DIRECT_STATE_NOW, "state_fields": ["winner"], "owner": "RESULT"},
    "set1_winner": {"capability": DIRECT_STATE_NOW, "state_fields": ["set1_winner"], "owner": "RESULT"},
    # Later-set winner targets are consumed while constructing the shared state,
    # but build_outcomes does not currently retain set2/set3 terminal scores or
    # winner fields in each emitted outcome. They therefore need a real state
    # extension before an exact Superbet marginal can be exposed.
    "set2_winner": {"capability": STATE_EXTENSION_REQUIRED, "required_fields": ["set2", "set2_winner"], "owner": "RESULT", "settlement_required": True},
    "set3_winner": {"capability": STATE_EXTENSION_REQUIRED, "required_fields": ["set3", "set3_winner"], "owner": "RESULT", "settlement_required": True},
    "exact_match_score": {"capability": DIRECT_STATE_NOW, "state_fields": ["sets"], "owner": "EXACT_SCORE"},
    "set1_exact_score": {"capability": DIRECT_STATE_NOW, "state_fields": ["set1"], "owner": "EXACT_SCORE"},
    "match_total": {"capability": DIRECT_STATE_NOW, "state_fields": ["total_games"], "owner": "TOTALS"},
    "set1_total": {"capability": DIRECT_STATE_NOW, "state_fields": ["set1"], "owner": "TOTALS"},
    "total_sets": {"capability": DIRECT_STATE_NOW, "state_fields": ["set_count"], "owner": "TOTALS"},
    "game_state": {"capability": DIRECT_STATE_NOW, "state_fields": ["cp2", "cp4", "cp6"], "owner": "GAME_STATE_EARLY", "quality_dependency": "service_model/PBP"},
    "set1_tiebreak": {"capability": DIRECT_STATE_NOW, "state_fields": ["set1_tiebreak"], "owner": "GAME_STATE_EARLY"},

    # Current shared outcomes contain per-player match sets and total match games,
    # but do not retain per-player game totals over every later set. Match game
    # handicap therefore needs state to retain p1_games/p2_games, not a guessed
    # conversion from match winner probability.
    "match_game_handicap": {"capability": STATE_EXTENSION_REQUIRED, "required_fields": ["p1_total_games", "p2_total_games"], "owner": "HANDICAP", "settlement_required": True},
    "player_total_games": {"capability": STATE_EXTENSION_REQUIRED, "required_fields": ["p1_total_games", "p2_total_games"], "owner": "PLAYER_TOTAL", "settlement_required": True},

    # symphony2_state computes later-set terminal distributions internally, but
    # build_outcomes currently does not freeze set2/set3 score fields into each
    # outcome. These markets are natural state extensions, not new neural targets.
    "set2_exact_score": {"capability": STATE_EXTENSION_REQUIRED, "required_fields": ["set2"], "owner": "EXACT_SCORE", "settlement_required": True},
    "set2_total": {"capability": STATE_EXTENSION_REQUIRED, "required_fields": ["set2"], "owner": "TOTALS", "settlement_required": True},
    "set3_total": {"capability": STATE_EXTENSION_REQUIRED, "required_fields": ["set3"], "owner": "TOTALS", "settlement_required": True},
    "set2_game_handicap": {"capability": STATE_EXTENSION_REQUIRED, "required_fields": ["set2"], "owner": "HANDICAP", "settlement_required": True},
    "set1_game_handicap": {"capability": DIRECT_STATE_NOW, "state_fields": ["set1"], "owner": "HANDICAP", "settlement_required": True},
    "set_handicap": {"capability": DIRECT_STATE_NOW, "state_fields": ["sets"], "owner": "HANDICAP", "settlement_required": True, "blocked_by": "current settlement quality/unverifiable rows"},
    "exact_sets": {"capability": DIRECT_STATE_NOW, "state_fields": ["set_count"], "owner": "SET_OUTCOME", "settlement_required": True},
    "any_set_to_nil": {"capability": STATE_EXTENSION_REQUIRED, "required_fields": ["all_set_scores"], "owner": "SET_OUTCOME", "settlement_required": True},
    "p1_exactly_1_set": {"capability": DIRECT_STATE_NOW, "state_fields": ["sets"], "owner": "SET_OUTCOME", "settlement_required": True},
    "p1_exactly_2_sets": {"capability": DIRECT_STATE_NOW, "state_fields": ["sets"], "owner": "SET_OUTCOME", "settlement_required": True},
    "p2_exactly_1_set": {"capability": DIRECT_STATE_NOW, "state_fields": ["sets"], "owner": "SET_OUTCOME", "settlement_required": True},
    "p2_exactly_2_sets": {"capability": DIRECT_STATE_NOW, "state_fields": ["sets"], "owner": "SET_OUTCOME", "settlement_required": True},
    "p1_wins_a_set": {"capability": DIRECT_STATE_NOW, "state_fields": ["sets"], "owner": "SET_OUTCOME", "settlement_required": True},
    "p2_wins_a_set": {"capability": DIRECT_STATE_NOW, "state_fields": ["sets"], "owner": "SET_OUTCOME", "settlement_required": True},

    # Serve props already own player ace distributions. Exact Superbet market-line
    # adapters + settlement are needed; NEURO should consume these as inputs later.
    "match_total_aces": {"capability": MODEL_ADAPTER_REQUIRED, "model_sources": ["serve_props", "player_intelligence"], "owner": "SERVE", "settlement_required": True},
    "most_aces": {"capability": MODEL_ADAPTER_REQUIRED, "model_sources": ["serve_props", "player_intelligence"], "owner": "SERVE", "settlement_required": True},

    "set2_game_state": {"capability": PBP_REQUIRED, "owner": "GAME_STATE_EARLY", "required_fields": ["set2 checkpoints"]},

    # Parity has no strong causal/model owner in the current stack. Keep it out of
    # production and consider a later neural specialist only after enough labels.
    "match_games_parity": {"capability": WEAK_BASE_NEURO_LATER, "owner": "PARITY"},
    "set1_games_parity": {"capability": WEAK_BASE_NEURO_LATER, "owner": "PARITY"},
    "set2_games_parity": {"capability": WEAK_BASE_NEURO_LATER, "owner": "PARITY"},
}


def capability(canonical_market: str) -> dict:
    return dict(CAPABILITY_MAP.get(str(canonical_market or ""), {
        "capability": "UNASSIGNED",
        "owner": "UNASSIGNED",
    }))


def recovery_priority(canonical_market: str) -> int:
    """Lower is earlier: harvest existing state/model capability before NEURO."""
    kind = capability(canonical_market).get("capability")
    return {
        DIRECT_STATE_NOW: 1,
        MODEL_ADAPTER_REQUIRED: 2,
        STATE_EXTENSION_REQUIRED: 3,
        SETTLEMENT_FIRST: 4,
        PBP_REQUIRED: 5,
        WEAK_BASE_NEURO_LATER: 6,
        "UNASSIGNED": 9,
    }.get(kind, 9)
