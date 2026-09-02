from __future__ import annotations

"""Canonical production entrypoint for Superbet line coverage.

Keep the external data contract stable while the old version-suffixed implementation
is retired behind one explicit boundary. Future fixes belong here, not in a new
``*_vXXX.py`` module.
"""

try:
    from . import superbet_line_coverage_v924 as _impl
except ImportError:  # direct script execution compatibility
    import superbet_line_coverage_v924 as _impl  # type: ignore

CANONICAL_ENTRYPOINT = True
LEGACY_IMPLEMENTATION = "superbet_line_coverage_v924"

VERSION = _impl.VERSION
RESULTS = _impl.RESULTS
META = _impl.META
DISPLAY_DERIVED_MARKETS = _impl.DISPLAY_DERIVED_MARKETS

enrich_match = _impl.enrich_match
enrich_results = _impl.enrich_results
main = _impl.main

__all__ = [
    "VERSION",
    "RESULTS",
    "META",
    "DISPLAY_DERIVED_MARKETS",
    "enrich_match",
    "enrich_results",
    "main",
]


if __name__ == "__main__":
    main()
