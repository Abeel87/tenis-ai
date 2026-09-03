from __future__ import annotations

"""Compact current-match feed for the isolated NEURO SHADOW UI.

The feed is derived only from already captured immutable NEURO SHADOW rows and
an optional gated neural training artifact. It never changes PLAYABLE or
Symphony and never invents a neural probability while a market is collecting.
"""

import json
from pathlib import Path
from typing import Any

from backend.neuro_shadow_history import DEFAULT_HISTORY_PATH, load_history
from backend.neuro_shadow_neural import VERSION as NEURAL_VERSION, predict
from backend.neuro_shadow_training import DEFAULT_TRAINING_PATH

VERSION = "neuro-shadow-current-v9.3.8"
MODE = "SHADOW"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_PATH = ROOT / "frontend" / "data" / "results.json"
DEFAULT_CURRENT_PATH = ROOT / "frontend" / "data" / "neuro_shadow_current_v936.json"


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _match_id(row: dict[str, Any]) -> str:
    value = row.get("match_id") if row.get("match_id") is not None else row.get("id")
    return "" if value is None else str(value)


def build_current_feed(
    results: list[dict[str, Any]],
    history: list[dict[str, Any]],
    training: dict[str, Any],
) -> dict[str, Any]:
    current_matches = {
        _match_id(match): match
        for match in results or []
        if isinstance(match, dict) and _match_id(match)
    }
    training = training if isinstance(training, dict) else {}
    artifact_neural_version = str(training.get("neural_version") or "")
    training_compatible = artifact_neural_version == NEURAL_VERSION
    market_reports = training.get("markets") if training_compatible else {}
    market_reports = market_reports if isinstance(market_reports, dict) else {}

    grouped: dict[str, dict[str, Any]] = {}
    for row in history or []:
        if not isinstance(row, dict) or row.get("mode") != MODE or row.get("operator_playable") is not False:
            continue
        mid = _match_id(row)
        match = current_matches.get(mid)
        if not match:
            continue
        market = str(row.get("market") or "")
        state_probability = row.get("probability")
        report = market_reports.get(market) if market else None
        neural_probability = predict(report, row.get("feature_snapshot") or {}) if isinstance(report, dict) else None
        if not training_compatible and artifact_neural_version:
            neural_status = "STALE_MODEL_ARTIFACT"
        else:
            neural_status = report.get("status") if isinstance(report, dict) else "COLLECTING_DATA"
            if neural_probability is None and neural_status == "SHADOW_MODEL_READY":
                neural_status = "FEATURES_UNAVAILABLE"

        item = {
            "prediction_key": row.get("prediction_key"),
            "market": market,
            "pick": row.get("pick"),
            "line": row.get("line"),
            "player": row.get("player"),
            "state_probability": state_probability,
            "neural_probability": neural_probability,
            "neural_status": neural_status or "COLLECTING_DATA",
            "source_model": row.get("source_model"),
            "operator": row.get("operator") or "Superbet",
            "operator_playable": False,
            "mode": MODE,
            "production_influence": False,
            "playable_influence": False,
        }
        bucket = grouped.setdefault(mid, {
            "match_id": mid,
            "p1": match.get("p1") or row.get("p1"),
            "p2": match.get("p2") or row.get("p2"),
            "scheduled_time": match.get("scheduled_time") or row.get("scheduled_time"),
            "surface": match.get("surface") or row.get("surface"),
            "tour": match.get("tour") or row.get("tour"),
            "rows": [],
        })
        bucket["rows"].append(item)

    matches = sorted(grouped.values(), key=lambda m: str(m.get("scheduled_time") or ""))
    for match in matches:
        match["rows"].sort(key=lambda r: (str(r.get("market") or ""), str(r.get("pick") or ""), str(r.get("line") or "")))

    neural_rows = sum(
        1 for match in matches for row in match["rows"] if row.get("neural_probability") is not None
    )
    total_rows = sum(len(match["rows"]) for match in matches)
    return {
        "version": VERSION,
        "neural_version": NEURAL_VERSION,
        "training_artifact_neural_version": artifact_neural_version or None,
        "training_artifact_compatible": training_compatible,
        "mode": MODE,
        "status": "SHADOW_ACTIVE" if total_rows else "NO_CURRENT_ROWS",
        "matches_count": len(matches),
        "rows_count": total_rows,
        "neural_rows_count": neural_rows,
        "state_only_rows_count": total_rows - neural_rows,
        "ready_markets": list(training.get("ready_markets") or []) if training_compatible else [],
        "production_influence": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
        "operator_playable": False,
        "matches": matches,
    }


def refresh_current_feed(
    results_path: Path = DEFAULT_RESULTS_PATH,
    history_path: Path = DEFAULT_HISTORY_PATH,
    training_path: Path = DEFAULT_TRAINING_PATH,
    current_path: Path = DEFAULT_CURRENT_PATH,
) -> dict[str, Any]:
    results = _read_json(results_path, [])
    history = load_history(history_path)
    training = _read_json(training_path, {})
    report = build_current_feed(
        [row for row in results if isinstance(row, dict)] if isinstance(results, list) else [],
        history,
        training if isinstance(training, dict) else {},
    )
    _write_json_atomic(current_path, report)
    return report
