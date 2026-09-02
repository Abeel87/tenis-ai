from __future__ import annotations

"""Temporary compatibility shim for the canonical Superbet line coverage module."""

try:
    from .superbet_line_coverage import enrich_match, enrich_results, main
except ImportError:
    from superbet_line_coverage import enrich_match, enrich_results, main

__all__ = ["enrich_match", "enrich_results", "main"]

if __name__ == "__main__":
    main()
