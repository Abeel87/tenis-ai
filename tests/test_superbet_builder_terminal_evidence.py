from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend import superbet_builder_terminal_evidence as evidence

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "audits/logic12_builder_terminal_evidence_manifest.json"
WORKFLOW = ROOT / ".github/workflows/superbet-market-refresh.yml"


def _candidate():
    return {
        "match_id": 192095,
        "event_id": "15059409",
        "scheduled_time": "2026-09-22T03:00:00Z",
        "probe_from": "2026-09-22T03:00:00Z",
        "probe_until": "2026-09-23T03:00:00Z",
        "p1": "Eva Lys",
        "p2": "Gabriela Elena Ruse",
        "operator_selection_id": "0155873a-f67d-5288-a8a7-14e6b0f0e652",
        "component_selection_ids": [
            "aedacd3b-c001-5ef5-ae42-3e53e7aac1a5",
            "9398c9c3-6d51-5339-a5b3-fba8f2611742",
        ],
        "combined_odds": 2.9,
    }


def _manifest(candidate=None):
    return {
        "schema_version": evidence.MANIFEST_SCHEMA,
        "status": "FROZEN",
        "operator": "superbet.pl",
        "market_id": 238733,
        "source_commit_sha": "935a2d1b2119c061fcda2ecdb3333ef395327125",
        "source_blob_sha": "3f7b58212540f7c5a4b28f42457b3c747a9fb6f7",
        "source_generated_at": "2026-09-21T18:56:50.924941+00:00",
        "selection_policy": "LEXICOGRAPHICALLY_SMALLEST_OPERATOR_SELECTION_ID_PER_EVENT",
        "candidates": [candidate or _candidate()],
        "settlement_enabled": False,
        "production_influence": False,
        "ineed_runtime_influence": False,
        "automatic_real_betting": False,
    }


def _payload(*, odds=None, odds_results=None, match_results=None, state=None):
    c = _candidate()
    return {
        "data": [{
            "eventId": c["event_id"],
            "matchName": "Eva Lys\u00b7Gabriela Elena Ruse",
            "utcDate": c["scheduled_time"],
            "offerStateStatus": state if state is not None else {"1": "finished", "2": "finished"},
            "odds": odds if odds is not None else [],
            "oddsResults": odds_results if odds_results is not None else [],
            "matchResults": match_results,
        }]
    }


def test_manifest_is_frozen_from_exact_git_artifact_and_has_three_deterministic_candidates():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    evidence.validate_manifest(data)
    assert data["source_commit_sha"] == "935a2d1b2119c061fcda2ecdb3333ef395327125"
    assert data["source_blob_sha"] == "3f7b58212540f7c5a4b28f42457b3c747a9fb6f7"
    assert data["selection_policy"] == "LEXICOGRAPHICALLY_SMALLEST_OPERATOR_SELECTION_ID_PER_EVENT"
    assert [row["event_id"] for row in data["candidates"]] == ["15059409", "15059413", "15063427"]
    assert len({row["operator_selection_id"] for row in data["candidates"]}) == 3
    assert all(row["probe_from"] == row["scheduled_time"] for row in data["candidates"])
    source = json.loads((ROOT / data["source_path"]).read_text(encoding="utf-8"))
    by_event = {str(m["event_id"]): m for m in source["matches"]}
    for row in data["candidates"]:
        quotes = sorted(by_event[row["event_id"]]["quotes"], key=lambda q: q["operator_selection_id"])
        assert row["operator_selection_id"] == quotes[0]["operator_selection_id"]
        assert row["component_selection_ids"] == quotes[0]["component_selection_ids"]


def test_before_probe_window_performs_zero_external_requests():
    calls = []
    out = evidence.build_evidence(
        _manifest(),
        previous=None,
        fetcher=lambda event_id: calls.append(event_id),
        now=datetime(2026, 9, 22, 2, 0, tzinfo=timezone.utc),
    )
    assert calls == []
    assert out["external_requests"] == 0
    assert out["candidates"][0]["evidence_status"] == "NOT_PROBE_WINDOW"
    assert out["settlement_enabled"] is False
    assert out["result_inferred"] is False


def test_finished_event_without_exact_result_stays_nd_and_never_infers_outcome():
    out = evidence.build_evidence(
        _manifest(),
        previous=None,
        fetcher=lambda event_id: _payload(),
        now=datetime(2026, 9, 22, 5, 0, tzinfo=timezone.utc),
    )
    row = out["candidates"][0]
    assert out["external_requests"] == 1
    assert row["event_identity_verified"] is True
    assert row["event_offer_state_status"] == {"1": "finished", "2": "finished"}
    assert row["exact_combination_result_hits"] == []
    assert row["evidence_status"] == "EVENT_FINISHED_NO_EXACT_RESULT_EVIDENCE"
    assert row["settlement_result"] is None
    assert row["payout"] is None
    assert row["result_inferred"] is False


def test_exact_combination_uuid_hit_is_preserved_raw_but_not_interpreted():
    c = _candidate()
    raw = {"uuid": c["operator_selection_id"], "resultCode": "opaque-operator-value", "nested": {"x": 7}}
    out = evidence.build_evidence(
        _manifest(), previous=None,
        fetcher=lambda event_id: _payload(odds_results=[raw]),
        now=datetime(2026, 9, 22, 5, 0, tzinfo=timezone.utc),
    )
    row = out["candidates"][0]
    assert row["evidence_status"] == "EXACT_OPERATOR_IDENTITY_HIT"
    assert row["exact_combination_result_hits"][0]["object"] == raw
    assert row["settlement_result"] is None
    assert row["payout"] is None
    assert row["result_inferred"] is False


def test_component_only_hits_do_not_become_whole_ticket_result():
    c = _candidate()
    out = evidence.build_evidence(
        _manifest(), previous=None,
        fetcher=lambda event_id: _payload(odds_results=[{"uuid": c["component_selection_ids"][0], "result": "opaque"}]),
        now=datetime(2026, 9, 22, 5, 0, tzinfo=timezone.utc),
    )
    row = out["candidates"][0]
    assert row["exact_combination_result_hits"] == []
    assert row["component_result_hits"][c["component_selection_ids"][0]]
    assert row["evidence_status"] == "EVENT_FINISHED_NO_EXACT_RESULT_EVIDENCE"
    assert row["settlement_result"] is None


def test_identity_mismatch_fails_closed():
    bad = _payload()
    bad["data"][0]["matchName"] = "Wrong One\u00b7Wrong Two"
    out = evidence.build_evidence(
        _manifest(), previous=None, fetcher=lambda event_id: bad,
        now=datetime(2026, 9, 22, 5, 0, tzinfo=timezone.utc),
    )
    row = out["candidates"][0]
    assert row["evidence_status"] == "EVENT_IDENTITY_MISMATCH"
    assert row["event_identity_verified"] is False
    assert row["settlement_result"] is None


def test_source_failure_is_nd_and_never_creates_outcome():
    def fail(_event_id):
        raise RuntimeError("network-down")
    out = evidence.build_evidence(
        _manifest(), previous=None, fetcher=fail,
        now=datetime(2026, 9, 22, 5, 0, tzinfo=timezone.utc),
    )
    row = out["candidates"][0]
    assert row["evidence_status"] == "SOURCE_UNAVAILABLE"
    assert row["source_error"] == "RuntimeError"
    assert row["settlement_result"] is None
    assert row["payout"] is None
    assert row["result_inferred"] is False


def test_exact_identity_hit_is_preserved_without_refetch():
    c = _candidate()
    raw = {"uuid": c["operator_selection_id"], "resultCode": "opaque"}
    first = evidence.build_evidence(
        _manifest(), previous=None,
        fetcher=lambda event_id: _payload(odds_results=[raw]),
        now=datetime(2026, 9, 22, 5, 0, tzinfo=timezone.utc),
    )
    calls = []
    second = evidence.build_evidence(
        _manifest(), previous=first,
        fetcher=lambda event_id: calls.append(event_id),
        now=datetime(2026, 9, 22, 6, 0, tzinfo=timezone.utc),
    )
    assert calls == []
    assert second["external_requests"] == 0
    row = second["candidates"][0]
    assert row["evidence_status"] == "EXACT_OPERATOR_IDENTITY_HIT"
    assert row["preserved_from_previous"] is True
    assert row["exact_combination_result_hits"][0]["object"] == raw
    assert row["settlement_result"] is None


def test_probe_window_is_bounded_and_expired_candidate_does_not_fetch():
    calls = []
    c = _candidate(); c["probe_until"] = "2026-09-22T04:00:00Z"
    out = evidence.build_evidence(
        _manifest(c), previous=None, fetcher=lambda event_id: calls.append(event_id),
        now=datetime(2026, 9, 22, 5, 0, tzinfo=timezone.utc),
    )
    assert calls == []
    assert out["candidates"][0]["evidence_status"] == "PROBE_WINDOW_EXPIRED"


def test_output_validator_forbids_runtime_or_settlement_authority():
    out = evidence.build_evidence(
        _manifest(), previous=None, fetcher=lambda event_id: _payload(),
        now=datetime(2026, 9, 22, 5, 0, tzinfo=timezone.utc),
    )
    evidence.validate_evidence(out)
    out["settlement_enabled"] = True
    with pytest.raises(ValueError):
        evidence.validate_evidence(out)


def test_module_and_workflow_are_read_only_evidence_not_settlement_path():
    module = (ROOT / "backend/superbet_builder_terminal_evidence.py").read_text(encoding="utf-8").lower()
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in (
        "ineed_system_settle_bet", "ineed_system_reserve_builder_ticket",
        "signal_settlement", "symphony2_tracker", "payout_after_taxes",
    ):
        assert forbidden not in module
    assert "from supabase" not in module and "import supabase" not in module
    assert "Refresh read-only Bet Builder terminal evidence" in workflow
    step = workflow.split("Refresh read-only Bet Builder terminal evidence", 1)[1].split("- name:", 1)[0]
    assert "github.event_name != 'pull_request'" in step
    assert "superbet_builder_terminal_evidence.py refresh" in step
    assert "tests/test_superbet_builder_terminal_evidence.py" in workflow
