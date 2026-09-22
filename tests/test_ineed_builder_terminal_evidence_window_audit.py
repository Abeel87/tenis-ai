from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "audits" / "logic12_builder_terminal_evidence_manifest.json"
AUDIT = ROOT / "TENIS_AI_LOGIC12_BUILDER_EVIDENCE_WINDOW_AUDIT.md"

EXPECTED = {
    "15059409": ("2026-09-22T03:00:00Z", "2026-09-26T03:00:00Z", "0155873a-f67d-5288-a8a7-14e6b0f0e652"),
    "15059413": ("2026-09-22T07:00:00Z", "2026-09-26T07:00:00Z", "006b60ca-3498-50c4-97f8-5f1a1f327749"),
    "15063427": ("2026-09-22T12:00:00Z", "2026-09-26T12:00:00Z", "041c4d76-7e31-5acb-a1b3-3a060ae7e4e2"),
}


def test_manifest_keeps_same_three_frozen_identities_with_96h_windows():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["status"] == "FROZEN"
    assert data["observation_window_revision"] == "OFFICIAL_RESULT_PUBLICATION_BUFFER_96H"
    assert data["observation_window_hours"] == 96
    rows = {row["event_id"]: row for row in data["candidates"]}
    assert set(rows) == set(EXPECTED)
    for event_id, (probe_from, probe_until, selection_id) in EXPECTED.items():
        row = rows[event_id]
        assert row["probe_from"] == probe_from
        assert row["probe_until"] == probe_until
        assert row["operator_selection_id"] == selection_id
        start = datetime.fromisoformat(probe_from.replace("Z", "+00:00"))
        end = datetime.fromisoformat(probe_until.replace("Z", "+00:00"))
        assert (end - start).total_seconds() == 96 * 3600


def test_window_extension_changes_no_settlement_or_runtime_authority():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["settlement_enabled"] is False
    assert data["result_inference_allowed"] is False
    assert data["production_influence"] is False
    assert data["playable_influence"] is False
    assert data["symphony_influence"] is False
    assert data["ineed_runtime_influence"] is False
    assert data["automatic_real_betting"] is False
    assert "settlement timing" in data["observation_window_note"]


def test_audit_preserves_operator_evidence_blocker_and_bounded_request_contract():
    text = AUDIT.read_text(encoding="utf-8")
    assert "MAX_CANDIDATES=3" in text
    assert "at most three public event requests" in text
    assert "BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE" in text
    assert "settlement_enabled=false" in text
    assert "result_inference_allowed=false" in text
    assert "automatic_real_betting=false" in text
    assert "must not by itself be converted" in text
