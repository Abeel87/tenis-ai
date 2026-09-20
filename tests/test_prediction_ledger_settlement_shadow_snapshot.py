from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend import prediction_ledger_settlement_shadow as settlement


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"


def test_real_frozen_repository_snapshot_builds_fail_closed_sidecar():
    ledger_path = DATA / "prediction_ledger_shadow.json"
    history_path = DATA / "history.json"
    selection_path = DATA / "prediction_ledger_selection_shadow.json"

    ledger_bytes_before = ledger_path.read_bytes()
    ledger = json.loads(ledger_bytes_before)
    history = json.loads(history_path.read_text(encoding="utf-8"))
    selection_doc = json.loads(selection_path.read_text(encoding="utf-8"))

    doc = settlement.build_sidecar(
        ledger,
        history,
        selection_doc,
        now=datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc),
    )

    assert ledger_path.read_bytes() == ledger_bytes_before
    assert doc["schema_version"] == settlement.SCHEMA_VERSION
    assert doc["mode"] == "SHADOW_ONLY"
    assert doc["network_fetch_enabled"] is False
    assert doc["source_ledger_mutated"] is False
    assert doc["production_influence"] is False
    assert doc["runtime_gating_enabled"] is False
    assert doc["learning_consumer_enabled"] is False
    assert doc["telemetry_consumer_enabled"] is False
    assert len(doc["rows"]) == len(ledger.get("rows") or [])
    assert doc["summary"]["rows"] == len(doc["rows"])
    assert doc["summary"]["exact_history_match_keys"] > 0
    assert sum(doc["summary"]["settlement_results"].values()) == len(doc["rows"])
    assert set(doc["summary"]["settlement_results"]) == {"hit", "miss", "void", "N/D"}
    assert doc["metric_contract"]["common_intersection_required"] == ["current", "catboost", "tabpfn"]
    assert doc["metric_contract"]["ranking_enabled"] is False
    assert all(
        (row.get("settlement") or {}).get("result") in {None, "hit", "miss", "void"}
        for row in doc["rows"]
    )
