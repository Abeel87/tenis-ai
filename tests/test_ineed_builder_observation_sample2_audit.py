from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "audits" / "logic12_builder_observation_sample_15059413_20260922T074441Z.json"
AUDIT = ROOT / "TENIS_AI_LOGIC12_BUILDER_OBSERVATION_SAMPLE2_AUDIT.md"


def load_sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_observation_is_exact_bounded_and_not_settlement():
    data = load_sample()
    row = data["sample"]
    assert data["source_main_sha"] == "e679eb59cee33049dba78be208ba390764e4a1f6"
    assert data["external_requests"] == 2
    assert data["candidate_count"] == 3
    assert row["event_id"] == "15059413"
    assert row["operator_selection_id"] == "006b60ca-3498-50c4-97f8-5f1a1f327749"
    assert row["event_identity_verified"] is True
    assert row["event_offer_state_status"] == {"1": "stop", "2": "active"}
    assert row["evidence_status"] == "NO_EXACT_RESULT_EVIDENCE"


def test_quote_disappearance_does_not_create_result_or_payout():
    data = load_sample()
    row = data["sample"]
    delta = data["observed_delta"]
    assert row["exact_combination_offer_present"] is False
    assert row["exact_combination_result_hits"] == []
    assert row["raw_match_results"] is None
    assert row["odds_results_count"] is None
    assert row["settlement_result"] is None
    assert row["payout"] is None
    assert row["result_inferred"] is False
    assert delta["exact_combination_offer_disappeared"] is True
    assert delta["settlement_evidence_gained"] is False


def test_third_frozen_event_remained_outside_probe_window():
    data = load_sample()
    other = {row["event_id"]: row["evidence_status"] for row in data["other_candidates"]}
    assert other["15059409"] == "EVENT_FINISHED_NO_EXACT_RESULT_EVIDENCE"
    assert other["15063427"] == "NOT_PROBE_WINDOW"


def test_sample_and_audit_keep_hard_safety_boundary():
    data = load_sample()
    text = AUDIT.read_text(encoding="utf-8")
    assert data["settlement_enabled"] is False
    assert data["result_inference_allowed"] is False
    assert data["automatic_real_betting"] is False
    assert data["conclusion"] == "BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE"
    assert "quote disappearance" in text
    assert "not settlement evidence" in text
    assert "Do not enable `builder_reservation`" in text
