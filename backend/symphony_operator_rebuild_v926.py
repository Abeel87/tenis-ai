from __future__ import annotations

"""Tenis AI v9.2.6 — rebuild actionable Symphony from current Superbet lines.

Unlike the old lightweight reprojector, this reruns the operator-aware Symphony
candidate/composition search after every Superbet refresh. MODEL/RAW maths,
training, weights and bookmaker prices remain untouched. The deep MODEL/RAW
lattice is intentionally not started here.
"""

import json
from datetime import datetime, timezone

try:
    from . import symphony_engine_v91 as engine
except ImportError:
    import symphony_engine_v91 as engine

VERSION = "v9.2.6"


def build_current_operator_report(legs: int = 4) -> dict:
    report = engine.build_report(legs=legs)
    report = dict(report)
    report["operator_reprojection_version"] = VERSION
    report["operator_reprojected_at"] = datetime.now(timezone.utc).isoformat()
    report["operator_reprojection"] = {
        "mode": "FULL_CURRENT_OPERATOR_CATALOGUE_REBUILD",
        "full_scenario_search_rerun": True,
        "deep_model_raw_rerun": False,
        "prices_used": False,
        "source": "symphony_engine_v91.build_report",
    }
    return report


def run(legs: int = 4) -> dict:
    report = build_current_operator_report(legs=legs)
    engine.base.core._write(engine.base.core.REPORT, report)
    matches = report.get("matches") or []
    playable = 0
    leg_counts = 0
    for row in matches if isinstance(matches, list) else []:
        if not isinstance(row, dict):
            continue
        comps = row.get("compositions") or {}
        if isinstance(comps, dict) and comps:
            playable += 1
            leg_counts += len(comps)
    return {
        "status": "OK",
        "version": VERSION,
        "matches": len(matches) if isinstance(matches, list) else 0,
        "matches_with_compositions": playable,
        "playable_leg_count_compositions": leg_counts,
        "full_scenario_search_rerun": True,
        "deep_model_raw_rerun": False,
        "prices_used": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
