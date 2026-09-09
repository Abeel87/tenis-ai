from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_legacy_cleanup_bridge_is_deleted_and_project_ui_has_no_polish_loop():
    assert not (ROOT/"frontend/ui-cleanup.js").exists()
    js = read("frontend/project-ui.js")
    assert "setInterval(" not in js
    assert "new MutationObserver(" not in js
    for retired in ("wrapScenarioOpen","decorateGeneratorCards","clarifyScenarioScores","TENIS_AI_SCENARIOS","scenario-v82a-panel"):
        assert retired not in js

def test_v88_compat_bridge_keeps_adaptive_logic_without_scenario_runtime_or_polling():
    js = read("frontend/adaptive-prod-bridge.js")
    assert "RUNTIME_FIX='v8.8.21'" in js
    assert "adaptive_prod_score:final" in js
    assert "v88AdaptiveProd=true" in js
    assert "[250,800,1600]" not in js
    assert "setTimeout(" not in js
    assert "tenis-ai:stats-dashboard-ready" in js
    for retired in ("wrapScenarioOpen","decorateGenerator","TENIS_AI_SCENARIOS","#scenario-v82a-panel",'data-p751-nav="scenarios"'):
        assert retired not in js

def test_active_compat_layers_do_not_poll():
    for path in ("frontend/adaptive-prod-bridge.js","frontend/project-ui.js"):
        js=read(path)
        assert "new MutationObserver(" not in js
        assert "setInterval(" not in js
