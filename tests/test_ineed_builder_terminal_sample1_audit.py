from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "audits" / "logic12_builder_terminal_sample_15059409.json"
AUDIT = ROOT / "TENIS_AI_LOGIC12_BUILDER_TERMINAL_SAMPLE1_AUDIT.md"


def load_sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_sample_is_exact_bounded_and_fail_closed():
    data = load_sample()
    row = data["sample"]
    assert data["source_main_sha"] == "726d92002e00da9393d76cd173f246b9c0f7b0ce"
    assert data["external_requests"] == 1
    assert data["candidate_count"] == 3
    assert row["event_id"] == "15059409"
    assert row["operator_selection_id"] == "0155873a-f67d-5288-a8a7-14e6b0f0e652"
    assert row["event_identity_verified"] is True
    assert row["evidence_status"] == "EVENT_FINISHED_NO_EXACT_RESULT_EVIDENCE"
    assert set(row["event_offer_state_status"].values()) == {"finished"}


def test_sample_has_no_synthetic_settlement_or_payout():
    data = load_sample()
    row = data["sample"]
    assert row["exact_combination_offer_present"] is False
    assert row["exact_combination_result_hits"] == []
    assert row["odds_results_count"] is None
    assert row["raw_match_results"] is None
    assert row["settlement_result"] is None
    assert row["payout"] is None
    assert row["result_inferred"] is False
    assert data["settlement_enabled"] is False
    assert data["result_inference_allowed"] is False
    assert data["automatic_real_betting"] is False
    assert data["conclusion"] == "BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE"


def test_future_windows_were_not_requested_in_sample1():
    data = load_sample()
    other = {row["event_id"]: row["evidence_status"] for row in data["other_candidates"]}
    assert other == {
        "15059413": "NOT_PROBE_WINDOW",
        "15063427": "NOT_PROBE_WINDOW",
    }


def test_audit_keeps_operator_evidence_blocker_and_hard_bans():
    text = AUDIT.read_text(encoding="utf-8")
    assert "BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE" in text
    assert "EVENT_FINISHED_NO_EXACT_RESULT_EVIDENCE" in text
    assert "settlement_result" in text
    assert "payout" in text
    assert "result_inferred=false" in text
    assert "automatic_real_betting=false" in text
    assert "do not infer a result from legs" in text
