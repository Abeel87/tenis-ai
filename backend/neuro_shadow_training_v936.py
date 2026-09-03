from __future__ import annotations

"""Persistent training/status artifact for the isolated NEURO SHADOW meta-model.

Reads only dedicated NEURO SHADOW history. It never writes PLAYABLE/Symphony
artifacts and never promotes a neural model automatically. Markets stay in
COLLECTING_DATA until the strict trainer gates are satisfied.
"""

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from backend.neuro_shadow_history_v935 import DEFAULT_HISTORY_PATH, load_history
from backend.neuro_shadow_neural_v936 import VERSION as NEURAL_VERSION, train_market

VERSION = "neuro-shadow-training-v9.3.11"
MODE = "SHADOW"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False
AUTO_PROMOTION = False
ORIENTATION_POLICY = "SIDE_MARKET_PLAYER_MUST_MATCH_APP_ORDER"
SIDE_MARKETS = {
    "p1_exactly_1_set": "p1",
    "p1_exactly_2_sets": "p1",
    "p1_wins_a_set": "p1",
    "p2_exactly_1_set": "p2",
    "p2_exactly_2_sets": "p2",
    "p2_wins_a_set": "p2",
}

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAINING_PATH = ROOT / "frontend" / "data" / "neuro_shadow_neural_v936.json"


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _name_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return " ".join(sorted(re.sub(r"[^a-z0-9]+", " ", text).split()))


def _orientation_valid(row: dict[str, Any]) -> bool:
    """Fail closed for historical side-sensitive rows captured before fixture orientation.

    Dedicated history remains append-only. This guard only decides whether a row
    is trustworthy enough to train the neural SHADOW model.
    """
    market = str(row.get("market") or "")
    side = SIDE_MARKETS.get(market)
    if side is None:
        return True
    player = _name_key(row.get("player"))
    expected = _name_key(row.get(side))
    return bool(player and expected and player == expected)


def _eligible_training_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows or [] if isinstance(row, dict) and _orientation_valid(row)]


def _group_by_market(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        market = str(row.get("market") or "")
        if market:
            grouped[market].append(row)
    return dict(grouped)


def training_fingerprint(rows: list[dict[str, Any]]) -> str:
    """Hash every trusted settled field that can affect neural training or its split.

    Pending/VOID rows do not trigger an expensive retrain. HIT/MISS evidence,
    immutable features, match grouping identity and chronological split time do.
    Historical side-market rows with inconsistent player orientation are
    quarantined before fingerprinting so they can never preserve a contaminated
    cached model artifact.
    """
    evidence = []
    for row in _eligible_training_rows(rows):
        if row.get("settlement") not in {"hit", "miss"}:
            continue
        evidence.append({
            "prediction_key": row.get("prediction_key"),
            "match_id": row.get("match_id") or row.get("id"),
            "p1": row.get("p1"),
            "p2": row.get("p2"),
            "scheduled_time": row.get("scheduled_time"),
            "created_at": row.get("created_at"),
            "market": row.get("market"),
            "settlement": row.get("settlement"),
            "probability": row.get("probability"),
            "feature_snapshot": row.get("feature_snapshot"),
        })
    evidence.sort(key=lambda row: (
        str(row.get("scheduled_time") or row.get("created_at") or ""),
        str(row.get("match_id") or ""),
        str(row.get("prediction_key") or ""),
        str(row.get("market") or ""),
        str(row.get("settlement") or ""),
    ))
    raw = json.dumps(
        {
            "trainer": VERSION,
            "neural": NEURAL_VERSION,
            "orientation_policy": ORIENTATION_POLICY,
            "evidence": evidence,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_training_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    raw_rows = [row for row in rows or [] if isinstance(row, dict)]
    eligible = _eligible_training_rows(raw_rows)
    quarantined = len(raw_rows) - len(eligible)
    grouped = _group_by_market(eligible)
    reports = {
        market: train_market(grouped[market], market)
        for market in sorted(grouped)
    }
    ready_markets = sorted(
        market for market, report in reports.items()
        if report.get("status") == "SHADOW_MODEL_READY"
    )
    ready = len(ready_markets)
    collecting = len(reports) - ready
    return {
        "version": VERSION,
        "neural_version": NEURAL_VERSION,
        "mode": MODE,
        "status": "SHADOW_READY" if ready else "COLLECTING_DATA",
        "history_rows_total": len(raw_rows),
        "history_rows": len(eligible),
        "orientation_quarantined_rows": quarantined,
        "orientation_policy": ORIENTATION_POLICY,
        "markets_seen": len(reports),
        "markets_ready": ready,
        "ready_markets": ready_markets,
        "markets_collecting": collecting,
        "markets": reports,
        "auto_promotion": False,
        "auto_promote": False,
        "production_influence": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
    }


def refresh_training_artifact(
    history_path: Path = DEFAULT_HISTORY_PATH,
    training_path: Path = DEFAULT_TRAINING_PATH,
) -> dict[str, Any]:
    rows = load_history(history_path)
    fingerprint = training_fingerprint(rows)
    existing = _read_json(training_path)
    if (
        existing.get("training_fingerprint") == fingerprint
        and existing.get("version") == VERSION
        and existing.get("neural_version") == NEURAL_VERSION
        and existing.get("orientation_policy") == ORIENTATION_POLICY
        and isinstance(existing.get("markets"), dict)
    ):
        return {**existing, "training_reused": True}

    report = build_training_report(rows)
    report["training_fingerprint"] = fingerprint
    report["training_reused"] = False
    _write_json_atomic(training_path, report)
    return report
