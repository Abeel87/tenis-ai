from __future__ import annotations

"""Temporary compatibility shim for canonical Superbet market context."""

try:
    from .superbet_market_context import finalize, main, prepare
except ImportError:
    from superbet_market_context import finalize, main, prepare

__all__ = ["prepare", "finalize", "main"]

if __name__ == "__main__":
    main()
