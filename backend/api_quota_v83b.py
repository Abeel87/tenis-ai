"""Compatibility import only.

The active runtime authority is backend/api_quota.py.
Do not add new logic here and do not point workflows or canonical modules at
this versioned path.
"""

try:
    from .api_quota import *  # noqa: F401,F403
    from .api_quota import main
except ImportError:  # direct backend execution compatibility
    from api_quota import *  # type: ignore # noqa: F401,F403
    from api_quota import main  # type: ignore


if __name__ == "__main__":
    main()
