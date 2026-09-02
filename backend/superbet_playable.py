from __future__ import annotations

"""Canonical production entrypoint for the Superbet PLAYABLE projection.

The PLAYABLE layer remains downstream of MODEL/RAW and operator availability. Keep
this stable module name for production; routine fixes belong here instead of a new
version-suffixed PLAYABLE module.
"""

try:
    from . import superbet_playable_v912 as _impl
except ImportError:  # direct script execution compatibility
    import superbet_playable_v912 as _impl  # type: ignore

CANONICAL_ENTRYPOINT = True
LEGACY_IMPLEMENTATION = "superbet_playable_v912"

VERSION = _impl.VERSION
OPERATOR = _impl.OPERATOR
GREEN_THRESHOLD = _impl.GREEN_THRESHOLD
MODEL_SELECT_THRESHOLD = _impl.MODEL_SELECT_THRESHOLD
SHADOW_MIN_THRESHOLD = _impl.SHADOW_MIN_THRESHOLD

inject_results = _impl.inject_results
project_match_for_display = _impl.project_match_for_display
inject = _impl.inject
project = _impl.project
main = _impl.main

__all__ = [
    "VERSION",
    "OPERATOR",
    "GREEN_THRESHOLD",
    "MODEL_SELECT_THRESHOLD",
    "SHADOW_MIN_THRESHOLD",
    "inject_results",
    "project_match_for_display",
    "inject",
    "project",
    "main",
]


if __name__ == "__main__":
    main()
