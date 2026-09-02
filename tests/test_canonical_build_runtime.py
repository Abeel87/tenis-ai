from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
WORKFLOWS = ROOT / ".github" / "workflows"


def test_frontend_data_compactor_has_one_canonical_runtime_path():
    assert (SCRIPTS / "compact_frontend_data.py").is_file()
    assert not (SCRIPTS / "compact_frontend_data_v853.py").exists()


def test_active_workflows_use_canonical_frontend_data_compactor():
    for name in ("update-and-pages.yml", "superbet-market-refresh.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "scripts/compact_frontend_data.py" in text
        assert "scripts/compact_frontend_data_v853.py" not in text
