from __future__ import annotations

"""Canonical production entrypoint for Superbet market-context mapping.

Production callers must import/execute this stable module instead of version-suffixed
implementations. The current implementation is kept behind this boundary while the
legacy adapter chain is collapsed without changing the published JSON contract.

Do not create a new ``superbet_market_context_vXXX.py`` for future fixes. Update the
canonical implementation/boundary instead.
"""

try:
    from .superbet_market_context_v924 import *  # noqa: F401,F403
    from .superbet_market_context_v924 import main
except ImportError:  # direct script execution compatibility
    from superbet_market_context_v924 import *  # type: ignore # noqa: F401,F403
    from superbet_market_context_v924 import main  # type: ignore

CANONICAL_ENTRYPOINT = True
LEGACY_IMPLEMENTATION = "superbet_market_context_v924"


if __name__ == "__main__":
    main()
