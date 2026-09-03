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


def test_index_loads_only_symphony2_composer_assets():
    index = text("frontend/index.html")
    assert 'href="symphony2.css"' in index
    assert 'src="symphony2.js"' in index
    for retired in (
        "scenario-studio-v82a",
        "scenario-runtime-v202",
        "scenario-dynamic-v84d3",
        "scenario-settlement-v83c",
        "generator-quality-v888",
    ):
        assert retired not in index


def test_project_ui_owns_symphony2_slot_without_legacy_scenario_bridge():
    ui = text("frontend/project-ui.js")
    assert 'data-p751-nav="symphony2"' in ui
    assert "<span>🎼</span><b>Symfonia 2.0</b>" in ui
    assert "TENIS_AI_SYMPHONY2" in ui
    assert "TENIS_AI_SCENARIOS" not in ui
    assert 'data-p751-nav="scenarios"' not in ui
    assert "route='scenarios'" not in ui


def test_no_active_frontend_javascript_references_retired_scenario_runtime():
    for path in (ROOT / "frontend").glob("*.js"):
        source = path.read_text(encoding="utf-8")
        assert "TENIS_AI_SCENARIOS" not in source, path
        assert 'data-p751-nav="scenarios"' not in source, path


def test_symphony2_has_own_fullscreen_hub_and_nav_ownership():
    js = text("frontend/symphony2.js")
    css = text("frontend/symphony2.css")
    assert "#symphony2-hub" in js
    assert "data-p751-nav=\"symphony2\"" in js
    assert 'data-p751-nav="scenarios"' not in js
    assert "<span>🎼</span><b>Symfonia 2.0</b>" in js
    assert "TENIS_AI_SYMPHONY2" in js
    assert "TENIS_AI_SCENARIOS" not in js
    assert "scenario-v82a-panel" not in js
    assert ".s2-hub" in css
    assert ".s2-hub[hidden]" in css


def test_data_workflow_no_longer_builds_or_guards_old_scenarios():
    workflow = text(".github/workflows/update-and-pages.yml")
    assert "Build Scenario Settlement feed" not in workflow
    assert "Scenario Dynamic Audit Guard" not in workflow
    assert "Integration Guard v8.3D" not in workflow
    assert "scenario_settlement_v83c.py" not in workflow
    assert "verify_v84d3.py" not in workflow
    assert "verify_v83d.py" not in workflow
    assert "Symphony 2.0 operator-first build + clean settlement" in workflow


def test_service_worker_forgets_scenario_cache_and_pins_symphony2():
    sw = text("frontend/sw.js")
    assert "scenario-runtime" not in sw
    assert "scenario-studio" not in sw
    assert "symphony2-v210" not in sw
    assert "symphony2-v220" not in sw
    assert "symphony2.js" in sw
    assert "symphony2.css" in sw
