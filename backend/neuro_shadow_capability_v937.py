from __future__ import annotations

"""Current capability truth for the isolated NEURO SHADOW state.

The v9.3.4 audit/capability map is intentionally historical: it describes what
was available before the SHADOW state expansion.  This module describes what
v9.3.6+ can actually capture now, without implying any production readiness.
"""

from backend.neuro_shadow_state_v935 import CANDIDATE_CAPTURE_READY_MARKETS

VERSION = "neuro-shadow-capability-v9.3.7"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

READY = "SHADOW_READY"
UNSUPPORTED = "SHADOW_UNSUPPORTED"

# Markets whose current SHADOW implementation has a narrower semantic scope.
MARKET_SCOPES = {
    "any_set_to_nil": "BO3_ONLY",
}


def shadow_capability(canonical_market: str, *, best_of: int | None = None) -> dict:
    market = str(canonical_market or "")
    if market not in CANDIDATE_CAPTURE_READY_MARKETS:
        return {
            "market": market,
            "status": UNSUPPORTED,
            "scope": None,
            "production_influence": False,
            "playable_influence": False,
        }

    scope = MARKET_SCOPES.get(market, "ALL_SUPPORTED_MATCH_FORMATS")
    status = READY
    reason = None
    if market == "any_set_to_nil" and best_of is not None and int(best_of) != 3:
        status = UNSUPPORTED
        reason = "current SHADOW state retains only the set scores needed for BO3 any-set-to-nil"

    return {
        "market": market,
        "status": status,
        "scope": scope,
        "reason": reason,
        "production_influence": False,
        "playable_influence": False,
    }


def ready_markets(*, best_of: int | None = None) -> frozenset[str]:
    return frozenset(
        market
        for market in CANDIDATE_CAPTURE_READY_MARKETS
        if shadow_capability(market, best_of=best_of)["status"] == READY
    )
