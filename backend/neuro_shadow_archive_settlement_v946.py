from __future__ import annotations

"""Bridge settled main history into isolated NEURO SHADOW settlement.

NEURO capture happens against the current operator/results feed. Finished fixtures
can disappear from that feed before a later NEURO run sees a terminal status.
The canonical app history already stores conservative, verified final evidence.
This module reuses only that frozen evidence and never changes production,
PLAYABLE or Symphony output.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from backend.neuro_shadow_history_v935 import (
    DEFAULT_HISTORY_PATH as DEFAULT_NEURO_HISTORY_PATH,
    DEFAULT_STATS_PATH,
    settle_history,
)

VERSION = "neuro-shadow-archive-settlement-v9.4.6"
MODE = "SHADOW"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP_HISTORY_PATH = ROOT / "frontend" / "data" / "history.json"


def _read_rows(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def verified_finals(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only terminal final evidence already accepted by main history.

    No result is reconstructed from prediction data. A row must carry an explicit
    result object produced by the main history settlement path.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        result = entry.get("result")
        if not isinstance(result, dict):
            continue
        status = str(result.get("status") or "").lower()
        if status not in {"completed", "retired", "void"}:
            continue
        match_id = entry.get("match_id")
        if match_id is None:
            continue
        key = str(match_id)
        if key in seen:
            continue
        seen.add(key)
        final = dict(result)
        final["match_id"] = match_id
        final["id"] = match_id
        final["p1"] = entry.get("p1")
        final["p2"] = entry.get("p2")
        out.append(final)
    return out


def settle_from_archive(
    app_history_path: Path = DEFAULT_APP_HISTORY_PATH,
    *,
    neuro_history_path: Path = DEFAULT_NEURO_HISTORY_PATH,
    stats_path: Path = DEFAULT_STATS_PATH,
) -> dict[str, Any]:
    finals = verified_finals(_read_rows(app_history_path))
    result = settle_history(finals, history_path=neuro_history_path, stats_path=stats_path)
    return {
        "version": VERSION,
        "mode": MODE,
        "verified_finals": len(finals),
        "settlement": result,
        "production_influence": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Settle NEURO SHADOW from verified app history")
    parser.add_argument("--app-history", type=Path, default=DEFAULT_APP_HISTORY_PATH)
    parser.add_argument("--neuro-history", type=Path, default=DEFAULT_NEURO_HISTORY_PATH)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS_PATH)
    args = parser.parse_args()
    payload = settle_from_archive(
        args.app_history,
        neuro_history_path=args.neuro_history,
        stats_path=args.stats,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
