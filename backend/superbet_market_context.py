from __future__ import annotations

"""Canonical production entrypoint for Superbet market-context mapping.

Production callers execute this stable module name. The current legacy implementation
is kept behind an explicit compatibility boundary while its internals are collapsed.
Future production fixes belong here; do not create another version-suffixed module.
"""

try:
    from . import superbet_market_context_v924 as _impl
except ImportError:  # direct script execution compatibility
    import superbet_market_context_v924 as _impl  # type: ignore

CANONICAL_ENTRYPOINT = True
LEGACY_IMPLEMENTATION = "superbet_market_context_v924"

VERSION = _impl.VERSION
STRICT_FIXTURE_LINE_VERSION = _impl.STRICT_FIXTURE_LINE_VERSION
NEW_LINE_MARKETS = _impl.NEW_LINE_MARKETS
NEW_HANDICAP_MARKETS = _impl.NEW_HANDICAP_MARKETS
NEW_MARKETS = _impl.NEW_MARKETS

canonical_market = _impl.canonical_market
selection_pick = _impl.selection_pick
mapped_sanitize = _impl.mapped_sanitize
prepare = _impl.prepare
finalize = _impl.finalize
main = _impl.main

__all__ = [
    "VERSION",
    "STRICT_FIXTURE_LINE_VERSION",
    "NEW_LINE_MARKETS",
    "NEW_HANDICAP_MARKETS",
    "NEW_MARKETS",
    "canonical_market",
    "selection_pick",
    "mapped_sanitize",
    "prepare",
    "finalize",
    "main",
]


if __name__ == "__main__":
    main()
