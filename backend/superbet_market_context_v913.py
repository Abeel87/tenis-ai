from __future__ import annotations

"""Compatibility alias for :mod:`superbet_market_mapping`."""

try:
    from . import superbet_market_mapping as _impl
except ImportError:
    import superbet_market_mapping as _impl

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

__all__ = [name for name in dir(_impl) if not name.startswith("_")]

if __name__ == "__main__":
    _impl.main()
