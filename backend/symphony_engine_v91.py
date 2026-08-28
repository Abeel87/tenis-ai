from __future__ import annotations

"""Tenis AI v9.1 — market-aware Tennis Symphony runner."""

import json

try:
    from . import symphony_engine_v90c as base
    from .symphony_operator_guard_v91 import VERSION as OPERATOR_VERSION, apply_superbet_market_guard
except ImportError:
    import symphony_engine_v90c as base
    from symphony_operator_guard_v91 import VERSION as OPERATOR_VERSION, apply_superbet_market_guard

VERSION = "v9.1"
BASE_VERSION = base.VERSION
_BASE_AUGMENT = base.augment_match_c4


def _guarded_augment(match: dict):
    augmented, evidence = _BASE_AUGMENT(match)
    return apply_superbet_market_guard(augmented, evidence, match)


def build_report(legs: int = 4) -> dict:
    previous = base.augment_match_c4
    base.augment_match_c4 = _guarded_augment
    try:
        report = base.build_report(legs=legs)
    finally:
        base.augment_match_c4 = previous
    report = dict(report)
    report["version"] = VERSION
    report["base_symphony_version"] = BASE_VERSION
    report["operator_market_context_version"] = OPERATOR_VERSION
    contract = dict(report.get("contract") or {})
    contract.update({
        "real_superbet_availability_gates_ready_to_bet_pool": True,
        "bookmaker_prices_used": False,
        "bookmaker_lines_are_context_not_training_targets": True,
        "core_prod_adaptive_shadow_scores_unchanged": True,
        "unavailable_markets_remain_analysis_only": True,
    })
    report["contract"] = contract
    return report


def run(legs: int = 4) -> dict:
    report = build_report(legs=legs)
    base.core._write(base.core.REPORT, report)
    source_rows = base.core._read(base.core.RESULTS, [])
    active = sum(
        1 for row in (source_rows if isinstance(source_rows, list) else [])
        if isinstance(row, dict)
        and (row.get("superbet_market_v91") or {}).get("operator_verified") is True
    )
    return {
        "status": "OK",
        "version": VERSION,
        "base_version": BASE_VERSION,
        "operator_market_context_version": OPERATOR_VERSION,
        "matches": report.get("matches_count", 0),
        "operator_context_matches": active,
        "production_influence": False,
        "prices_used": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
