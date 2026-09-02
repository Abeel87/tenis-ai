from __future__ import annotations

"""Compatibility alias for :mod:`superbet_market_core`.

All production core logic lives under the stable non-versioned module.  The
legacy module name resolves to the same module object so old tests/callers that
monkeypatch configuration (for example ``REFRESH_HOURS``) still affect the
canonical implementation instead of a copied namespace.
"""

import sys

try:
    from . import superbet_market_core as _impl
except ImportError:
    import superbet_market_core as _impl

if __name__ == "__main__":
    _impl.main()
else:
    sys.modules[__name__] = _impl
