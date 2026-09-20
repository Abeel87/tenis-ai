from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import backend.prediction_ledger_selection_shadow as joins
import backend.prediction_ledger_shadow as ledger


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_frozen_repository_snapshot_builds_exact_shadow_sidecar_without_source_mutation():
    root = Path(__file__).resolve().parents[1]
    data = root / "frontend" / "data"
    ledger_doc = _read(data / "prediction_ledger_shadow.json")
    base_history = _read(data / "history.json")
    symphony_history = _read(data / "symphony2_history.json")

    assert ledger_doc.get("schema_version") == ledger.SCHEMA_VERSION
    assert isinstance(ledger_doc.get("rows"), list) and ledger_doc["rows"]
    before = deepcopy(ledger_doc)

    doc = joins.build_sidecar(
        ledger_doc,
        base_history,
        symphony_history,
        now=datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc),
    )

    assert ledger_doc == before
    assert doc["summary"]["rows"] == len(ledger_doc["rows"])
    assert doc["summary"]["population_counts"]["ALL"] == len(ledger_doc["rows"])
    assert doc["summary"]["population_counts"]["PLAYABLE"] > 0
    assert doc["summary"]["population_counts"]["SYMPHONY_SELECTED"] > 0
    assert doc["summary"]["population_counts"]["INEED_SELECTED"] is None
    assert doc["summary"]["common_current_catboost_tabpfn"] > 0
    assert doc["summary"]["common_with_playable"] > 0
    assert doc["production_influence"] is False
    assert doc["learning_consumer_enabled"] is False
    assert doc["telemetry_consumer_enabled"] is False
    assert doc["ineed_contract"]["network_fetch_enabled"] is False
