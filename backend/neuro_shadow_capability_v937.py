from __future__ import annotations

"""Current capability truth for the isolated NEURO SHADOW state.

The v9.3.4 audit/capability map is intentionally historical: it describes what
was available before the SHADOW state expansion. This module describes what
the current isolated SHADOW state can actually capture, without implying any
production readiness.
"""

from backend.neuro_shadow_state_v935 import CANDIDATE_CAPTURE_READY_MARKETS

VERSION = "neuro-shadow-capability-v9.3.8"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

READY = "SHADOW_READY"
UNSUPPORTED = "SHADOW_UNSUPPORTED"


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

    return {
        "market": market,
        "status": READY,
        "scope": "ALL_SUPPORTED_MATCH_FORMATS",
        "reason": None,
        "production_influence": False,
        "playable_influence": False,
    }


def ready_markets(*, best_of: int | None = None) -> frozenset[str]:
    return frozenset(
        market
        for market in CANDIDATE_CAPTURE_READY_MARKETS
        if shadow_capability(market, best_of=best_of)["status"] == READY
    )
