from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
WORKFLOW = ROOT / ".github" / "workflows" / "symphony2-check.yml"


def test_pbp_evidence_has_one_canonical_module_path():
    assert (BACKEND / "pbp_market_evidence.py").is_file()
    assert not (BACKEND / "pbp_market_evidence_v940.py").exists()
    test = (ROOT / "tests" / "test_pbp_market_evidence_v940.py").read_text(encoding="utf-8")
    assert "from backend.pbp_market_evidence import" in test
    assert "pbp_market_evidence_v940" not in test


def test_pbp_cache_recovery_has_one_canonical_module_path():
    assert (BACKEND / "pbp_cache_recovery.py").is_file()
    assert not (BACKEND / "pbp_cache_recovery_v941.py").exists()
    test = (ROOT / "tests" / "test_pbp_profile_supply_v941.py").read_text(encoding="utf-8")
    assert "from backend import pbp_cache_recovery as recovery" in test
    assert "pbp_cache_recovery_v941" not in test


def test_symphony_workflow_uses_canonical_state_and_pbp_paths():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "backend/symphony2_state_core.py" in text
    assert "backend/symphony2_state_core_v945.py" not in text
    assert "backend/pbp_market_evidence.py" in text
    assert "backend/pbp_market_evidence_v940.py" not in text
