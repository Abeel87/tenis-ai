from copy import deepcopy
from pathlib import Path

from backend import readiness_engine_shadow as readiness
from backend import snapshot_digest


ROOT = Path(__file__).resolve().parents[1]


def _results():
    return [
        {
            "id": 101,
            "scheduled_time": "2026-09-19T12:00:00Z",
            "p1": "Alpha",
            "p2": "Beta",
            "model_ready": True,
            "early_hold_v7": {"market_evidence_v940": {"mode": "EVIDENCE_ONLY", "ready_markets": []}},
        }
    ]


def _report(results):
    return {
        "status": readiness.STATUS,
        "source_snapshot": {
            "results_snapshot_contract": readiness.SNAPSHOT_CONTRACT,
            "results_snapshot_sha256": readiness.results_snapshot_sha256(results),
            "history_coverage_snapshot_aligned": True,
            "player_state_snapshot_aligned": True,
            "legacy_model_ready_reference_mismatches": 0,
        },
    }


def test_exact_snapshot_is_observability_eligible():
    results = _results()
    verdict = readiness.observability_snapshot_alignment(results, _report(results))
    assert verdict["available"] is True
    assert verdict["reason"] == "EXACT_RESULTS_SNAPSHOT_ALIGNED"


def test_cross_snapshot_readiness_is_rejected_not_relabelled():
    results = _results()
    report = _report(results)
    newer = deepcopy(results)
    newer[0]["model_ready"] = False
    verdict = readiness.observability_snapshot_alignment(newer, report)
    assert verdict["available"] is False
    assert verdict["reason"] == "RESULTS_SNAPSHOT_MISMATCH"
    assert verdict["expected_results_snapshot_sha256"] != verdict["current_results_snapshot_sha256"]


def test_wrong_snapshot_contract_is_rejected():
    results = _results()
    report = _report(results)
    report["source_snapshot"]["results_snapshot_contract"] = "other-contract"
    verdict = readiness.observability_snapshot_alignment(results, report)
    assert verdict == {"available": False, "reason": "READINESS_SNAPSHOT_CONTRACT_MISMATCH"}


def test_missing_digest_is_nd_not_zero_or_ready():
    results = _results()
    report = _report(results)
    report["source_snapshot"].pop("results_snapshot_sha256")
    verdict = readiness.observability_snapshot_alignment(results, report)
    assert verdict == {"available": False, "reason": "READINESS_SNAPSHOT_DIGEST_MISSING"}


def test_failed_source_alignment_is_rejected():
    results = _results()
    report = _report(results)
    report["source_snapshot"]["player_state_snapshot_aligned"] = False
    verdict = readiness.observability_snapshot_alignment(results, report)
    assert verdict == {"available": False, "reason": "READINESS_SOURCE_ALIGNMENT_FAILED"}


def test_player_dna_post_update_host_delivers_exact_snapshot_readiness_sidecar():
    point = (ROOT / ".github/workflows/point-tape-audit.yml").read_text(encoding="utf-8")
    player = (ROOT / ".github/workflows/player-dna-shadow-refresh.yml").read_text(encoding="utf-8")
    update = (ROOT / ".github/workflows/update-and-pages.yml").read_text(encoding="utf-8")
    scope = (ROOT / ".github/scripts/change_scope.py").read_text(encoding="utf-8")
    backend_update = (ROOT / "backend/update.py").read_text(encoding="utf-8")

    assert "python backend/readiness_engine_shadow.py" in point
    assert "frontend/data/readiness_engine_shadow.json" in point
    assert "name: player-dna-point-foundation" in point
    assert "workflow_run:" not in point

    assert 'workflows: ["Update tennis data and deploy Pages"]' in player
    ordered_commands = [
        "python backend/player_dna_profile_readiness.py",
        "python backend/player_dna_service_split_source_readiness.py",
        "python backend/player_dna_pbp_service_split_readiness.py",
        "python backend/player_dna_match_state_readiness.py",
        "python backend/player_dna_shadow_profiles.py",
        "python backend/player_dna_matchup_readiness_audit.py",
        "python backend/player_dna_recent_form_challenger.py",
        "python backend/history_coverage_audit.py",
        "python backend/snapshot_digest.py stamp-report",
        "python backend/readiness_engine_shadow.py",
    ]
    positions = [player.index(command) for command in ordered_commands]
    assert positions == sorted(positions)

    artifact = player.split("- name: Upload Player DNA SHADOW artifacts", 1)[1].split(
        "- name: Publish Player DNA SHADOW reports", 1
    )[0]
    for path in (
        "frontend/data/results.json",
        "frontend/data/history_coverage_audit_v949.json",
        "frontend/data/player_dna_service_split_source_readiness.json",
        "frontend/data/player_dna_pbp_service_split_readiness.json",
        "frontend/data/player_dna_match_state_readiness.json",
        "frontend/data/player_dna_matchup_readiness_audit.json",
        "frontend/data/player_dna_recent_form_challenger.json",
        "frontend/data/player_dna_player_state_shadow.json",
        "frontend/data/readiness_engine_shadow.json",
    ):
        assert path in artifact

    publish = player.split("- name: Publish Player DNA SHADOW reports", 1)[1].split(
        "- name: Dispatch FAST Pages deploy", 1
    )[0]
    assert "frontend/data/readiness_engine_shadow.json" in publish
    assert "frontend/data/history_coverage_audit_v949.json" not in publish
    assert "frontend/data/player_dna_player_state_shadow.json" not in publish

    cleanup = player.split("- name: Clean run-local LOGIC-08 evidence before publish", 1)[1].split(
        "- name: Publish Player DNA SHADOW reports", 1
    )[0]
    assert "git restore -- frontend/data/history_coverage_audit_v949.json" in cleanup
    assert "frontend/data/player_dna_player_state_shadow.json" in cleanup
    assert "frontend/data/readiness_engine_shadow.json" not in cleanup

    assert "readiness_engine_shadow" not in backend_update
    assert "- 'frontend/data/**'" in update
    assert "path.startswith(('backend/', 'data/', 'frontend/data/'))" in scope


def test_snapshot_digest_is_key_order_stable():
    a = _results()
    b = [dict(reversed(list(a[0].items())))]
    assert readiness.results_snapshot_sha256(a) == readiness.results_snapshot_sha256(b)


def test_snapshot_stamp_adds_results_provenance_without_changing_history_owner(tmp_path):
    results = _results()
    report_path = tmp_path / "history.json"
    results_path = tmp_path / "results.json"
    report_path.write_text('{"summary":{"visible_matches":1},"source_snapshot":{"raw_rows":10}}', encoding="utf-8")
    results_path.write_text(__import__("json").dumps(results), encoding="utf-8")

    stamped = snapshot_digest.stamp_report_results_snapshot(report_path, results_path)
    source = stamped["source_snapshot"]
    assert source["raw_rows"] == 10
    assert source["results_snapshot_contract"] == snapshot_digest.SNAPSHOT_CONTRACT
    assert source["results_snapshot_sha256"] == readiness.results_snapshot_sha256(results)


def test_player_dna_refresh_is_existing_post_update_candidate_host():
    player = (ROOT / ".github/workflows/player-dna-shadow-refresh.yml").read_text(encoding="utf-8")
    assert "workflow_run:" in player
    assert 'workflows: ["Update tennis data and deploy Pages"]' in player
    assert "github.event.workflow_run.conclusion == 'success'" in player
    assert "github.event.workflow_run.head_branch == 'main'" in player
    assert "Restore tennis history + PBP cache" in player
    assert "Build strict Player DNA point dataset" in player
    assert "Build leakage-safe Player DNA profiles" in player
    assert "Publish Player DNA SHADOW reports" in player
    assert "git push origin HEAD:main" in player
    assert "gh workflow run deploy-pages-fast.yml --ref main" in player


def test_candidate_readiness_modules_are_zero_network_by_source_contract():
    modules = (
        "backend/history_coverage_audit.py",
        "backend/snapshot_digest.py",
        "backend/player_dna_service_split_source_readiness.py",
        "backend/player_dna_pbp_service_split_readiness.py",
        "backend/player_dna_match_state_readiness.py",
        "backend/player_dna_matchup_readiness_audit.py",
        "backend/player_dna_recent_form_challenger.py",
        "backend/player_dna_player_state_shadow.py",
        "backend/readiness_engine_shadow.py",
        "backend/player_identity.py",
    )
    forbidden = (
        "import requests",
        "from requests",
        "import urllib",
        "from urllib",
        "import httpx",
        "from httpx",
        "import aiohttp",
        "from aiohttp",
        "import selenium",
        "from selenium",
        "LIVE_TENNIS_API_KEY",
        "ODDSPAPI_API_KEY",
    )
    for relative in modules:
        text = (ROOT / relative).read_text(encoding="utf-8")
        hits = [token for token in forbidden if token in text]
        assert not hits, f"{relative} contains network-capable source tokens: {hits}"
