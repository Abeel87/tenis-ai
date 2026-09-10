from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RETIRED_FILES = (
    "backend/scenario_settlement_v83c.py",
    "frontend/generator-quality-v888.js",
    "frontend/scenario-dynamic-v84d3.css",
    "frontend/scenario-dynamic-v84d3.js",
    "frontend/scenario-runtime-v202.js",
    "frontend/scenario-settlement-v83c.js",
    "frontend/scenario-studio-v82a.css",
    "frontend/scenario-studio-v82a.js",
    "frontend/data/scenario_results_v83c.json",
    "scripts/verify_v83d.py",
    "scripts/verify_v84d3.py",
)


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_old_scenario_generator_files_are_removed():
    for path in RETIRED_FILES:
        assert not (ROOT / path).exists(), path


def test_no_active_frontend_javascript_references_retired_scenario_runtime():
    for path in (ROOT / "frontend").glob("*.js"):
        source = path.read_text(encoding="utf-8")
        assert "TENIS_AI_SCENARIOS" not in source, path
        assert 'data-p751-nav="scenarios"' not in source, path


def test_data_workflow_no_longer_builds_or_guards_old_scenarios():
    workflow = text(".github/workflows/update-and-pages.yml")
    assert "Build Scenario Settlement feed" not in workflow
    assert "Scenario Dynamic Audit Guard" not in workflow
    assert "Integration Guard v8.3D" not in workflow
    assert "scenario_settlement_v83c.py" not in workflow
    assert "verify_v84d3.py" not in workflow
    assert "verify_v83d.py" not in workflow
    assert "Symphony 2.0 operator-first build + clean settlement" in workflow


