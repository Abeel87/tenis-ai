from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
WORKFLOWS = ROOT / ".github" / "workflows"


def test_frontend_data_compactor_has_one_canonical_runtime_path():
    assert (SCRIPTS / "compact_frontend_data.py").is_file()
    assert not (SCRIPTS / "compact_frontend_data_v853.py").exists()


def test_results_publication_pruner_has_one_canonical_runtime_path():
    assert (SCRIPTS / "prune_results_payload.py").is_file()
    assert not (SCRIPTS / "prune_results_payload_v854.py").exists()
    compactor = (SCRIPTS / "compact_frontend_data.py").read_text(encoding="utf-8")
    assert "from prune_results_payload import prune_results" in compactor
    assert "prune_results_payload_v854" not in compactor


def test_runtime_health_has_one_canonical_utility_path():
    assert (SCRIPTS / "runtime_health.py").is_file()
    assert not (SCRIPTS / "runtime_health_v84e0.py").exists()
    health_test = (ROOT / "tests" / "test_v84e0_runtime_health.py").read_text(encoding="utf-8")
    assert "from scripts.runtime_health import audit" in health_test
    assert "runtime_health_v84e0" not in health_test


def test_active_workflows_use_canonical_publication_build_utilities():
    update = (WORKFLOWS / "update-and-pages.yml").read_text(encoding="utf-8")
    refresh = (WORKFLOWS / "superbet-market-refresh.yml").read_text(encoding="utf-8")
    symphony = (WORKFLOWS / "symphony2-check.yml").read_text(encoding="utf-8")
    ui = (WORKFLOWS / "ui-smoke.yml").read_text(encoding="utf-8")

    for text in (update, refresh, symphony):
        assert "scripts/compact_frontend_data.py" in text
        assert "scripts/compact_frontend_data_v853.py" not in text

    for text in (update, ui):
        assert "scripts/prune_results_payload.py" in text
        assert "scripts/prune_results_payload_v854.py" not in text
