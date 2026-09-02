from __future__ import annotations

"""Temporary compatibility shim for canonical Superbet market context.

Production imports :mod:`superbet_market_context`. This module contains no
business logic; it only exposes canonical symbols while legacy imports are
being removed.
"""

try:
    from . import superbet_market_context as _impl
except ImportError:
    import superbet_market_context as _impl

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

__all__ = [name for name in dir(_impl) if not name.startswith("_")]

if __name__ == "__main__":
    _impl.main()
