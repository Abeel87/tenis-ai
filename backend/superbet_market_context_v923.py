from __future__ import annotations

"""Compatibility alias for :mod:`superbet_market_audit`."""

import json
import sys

try:
    from . import superbet_market_audit as _impl
except ImportError:
    import superbet_market_audit as _impl

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

__all__ = [name for name in dir(_impl) if not name.startswith("_")]


def main() -> None:
    mode = str(sys.argv[1] if len(sys.argv) > 1 else "prepare").strip().casefold()
    if mode == "prepare":
        result = _impl.prepare()
    elif mode == "finalize":
        result = _impl.finalize()
    else:
        raise SystemExit("usage: superbet_market_context_v923.py [prepare|finalize]")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
