from __future__ import annotations

"""Temporary compatibility shim.

Production uses :mod:`superbet_playable`. This file contains no PLAYABLE logic and
exists only while legacy tests/workflow references are being removed.
"""

try:
    from .superbet_playable import inject, main, project
except ImportError:
    from superbet_playable import inject, main, project

__all__ = ["inject", "project", "main"]

if __name__ == "__main__":
    main()
