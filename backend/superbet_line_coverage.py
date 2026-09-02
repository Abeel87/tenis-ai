from __future__ import annotations

"""Canonical production entrypoint for Superbet line coverage.

Keep the external data contract stable while version-suffixed implementation files are
retired behind this boundary. Future production fixes belong on the canonical path,
not in a new ``*_vXXX.py`` module.
"""

try:
    from .superbet_line_coverage_v924 import *  # noqa: F401,F403
    from .superbet_line_coverage_v924 import main
except ImportError:  # direct script execution compatibility
    from superbet_line_coverage_v924 import *  # type: ignore # noqa: F401,F403
    from superbet_line_coverage_v924 import main  # type: ignore

CANONICAL_ENTRYPOINT = True
LEGACY_IMPLEMENTATION = "superbet_line_coverage_v924"


if __name__ == "__main__":
    main()
