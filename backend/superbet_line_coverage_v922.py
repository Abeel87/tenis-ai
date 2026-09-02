from __future__ import annotations

"""Compatibility alias for the canonical Superbet line coverage runtime.

All production logic now lives in :mod:`superbet_line_coverage`.
"""

try:
    from . import superbet_line_coverage as _impl
except ImportError:
    import superbet_line_coverage as _impl

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

__all__ = [name for name in dir(_impl) if not name.startswith("_")]

if __name__ == "__main__":
    _impl.main()
