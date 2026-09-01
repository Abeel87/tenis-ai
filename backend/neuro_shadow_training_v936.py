from __future__ import annotations

"""Persistent training/status artifact for the isolated NEURO SHADOW meta-model.

Reads only dedicated NEURO SHADOW history. It never writes PLAYABLE/Symphony
artifacts and never promotes a neural model automatically. Markets stay in
COLLECTING_DATA until the strict trainer gates are satisfied.
"""

import json
from pathlib import Path
from typing import Any

from backend.neuro_shadow_history_v935 import DEFAULT_HISTORY_PATH, load_history
from backend.neuro_shadow_neural_v936 import train_market

VERSION = "neuro-shadow-training-v9.3.6"
MODE = "SHADOW"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False
AUTO_PROMOTION = False

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAINING_PATH = ROOT / "frontend" / "data" / "neuro_shadow_neural_v936.json"


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def build_training_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    markets = sorted({
        str(row.get("market") or "")
        for row in rows or []
        if isinstance(row, dict) and str(row.get("market") or "")
    })
    reports = {market: train_market(rows, market) for market in markets}
    ready = sum(1 for report in reports.values() if report.get("status") == "SHADOW_MODEL_READY")
    collecting = len(reports) - ready
    return {
        "version": VERSION,
        "mode": MODE,
        "status": "SHADOW_READY" if ready else "COLLECTING_DATA",
        "history_rows": len(rows or []),
        "markets_seen": len(markets),
        "markets_ready": ready,
        "markets_collecting": collecting,
        "markets": reports,
        "auto_promotion": False,
        "production_influence": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
    }


def refresh_training_artifact(
    history_path: Path = DEFAULT_HISTORY_PATH,
    training_path: Path = DEFAULT_TRAINING_PATH,
) -> dict[str, Any]:
    report = build_training_report(load_history(history_path))
    _write_json_atomic(training_path, report)
    return report
