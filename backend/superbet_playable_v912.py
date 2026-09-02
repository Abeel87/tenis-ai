from __future__ import annotations

"""Temporary compatibility shim for the canonical PLAYABLE runtime.

Production imports :mod:`superbet_playable`. This module contains no business
logic; it only exposes the canonical module's symbols while legacy imports are
being removed.
"""

try:
    from . import superbet_playable as _impl
except ImportError:
    import superbet_playable as _impl

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

__all__ = [name for name in dir(_impl) if not name.startswith("_")]

if __name__ == "__main__":
    _impl.main()
