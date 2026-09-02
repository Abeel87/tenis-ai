from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
WORKFLOWS = ROOT / ".github" / "workflows"


def test_pbp_evidence_has_one_canonical_module_path():
    assert (BACKEND / "pbp_market_evidence.py").is_file()
    assert not (BACKEND / "pbp_market_evidence_v940.py").exists()
    test = (ROOT / "tests" / "test_pbp_market_evidence_v940.py").read_text(encoding="utf-8")
    assert "from backend.pbp_market_evidence import" in test
    assert "from backend.pbp_market_evidence_v940" not in test


def test_pbp_cache_recovery_has_one_canonical_module_path():
    assert (BACKEND / "pbp_cache_recovery.py").is_file()
    assert not (BACKEND / "pbp_cache_recovery_v941.py").exists()
    test = (ROOT / "tests" / "test_pbp_profile_supply_v941.py").read_text(encoding="utf-8")
    assert "from backend import pbp_cache_recovery as recovery" in test
    assert "from backend import pbp_cache_recovery_v941" not in test


def test_joint_builder_publication_has_one_canonical_wrapper_path():
    assert (BACKEND / "apply_joint_to_results.py").is_file()
    assert not (BACKEND / "apply_joint_to_results_v78b.py").exists()
    wrapper = (BACKEND / "apply_joint_to_results.py").read_text(encoding="utf-8")
    assert "from joint_builder_v78b import add_joint_builder" in wrapper
    assert "from pbp_cache_recovery import recover_rows_from_cache" in wrapper
    assert "from pbp_market_evidence import enrich_market_evidence" in wrapper
    assert "from pbp_cache_recovery_v941 import" not in wrapper
    assert "from pbp_market_evidence_v940 import" not in wrapper
    # Persisted metadata keys keep their historical version identity.
    assert 'meta["pbp_cache_recovery_v941"]' in wrapper
    assert '"market_evidence_v940"' in wrapper


def test_active_workflows_use_canonical_state_pbp_and_publication_paths():
    symphony = (WORKFLOWS / "symphony2-check.yml").read_text(encoding="utf-8")
    update = (WORKFLOWS / "update-and-pages.yml").read_text(encoding="utf-8")

    assert "backend/symphony2_state_core.py" in symphony
    assert "backend/symphony2_state_core_v945.py" not in symphony
    assert "backend/pbp_market_evidence.py" in symphony
    assert "backend/pbp_market_evidence_v940.py" not in symphony
    assert "backend/apply_joint_to_results.py" in symphony
    assert "backend/apply_joint_to_results_v78b.py" not in symphony

    assert "python backend/apply_joint_to_results.py" in update
    assert "backend/apply_joint_to_results_v78b.py" not in update
