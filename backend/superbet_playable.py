from __future__ import annotations

"""Canonical production entrypoint for the Superbet PLAYABLE projection.

The PLAYABLE layer remains downstream of MODEL/RAW and operator availability. Keep
this stable module name for production. Do not add a new version-suffixed PLAYABLE
module for routine fixes.
"""

try:
    from .superbet_playable_v912 import *  # noqa: F401,F403
    from .superbet_playable_v912 import main
except ImportError:  # direct script execution compatibility
    from superbet_playable_v912 import *  # type: ignore # noqa: F401,F403
    from superbet_playable_v912 import main  # type: ignore

CANONICAL_ENTRYPOINT = True
LEGACY_IMPLEMENTATION = "superbet_playable_v912"


if __name__ == "__main__":
    main()
