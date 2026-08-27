from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_project_ui_quality_bridge_is_loaded_last():
    html = read("frontend/index.html")
    assert "project-ui-quality-v8815.js?v=8815" in html
    assert html.index("checkpoint-quality-v887.js?v=887") < html.index("project-ui-quality-v8815.js?v=8815")


def test_project_ui_recommendations_use_final_signals():
    js = read("frontend/project-ui-quality-v8815.js")
    assert "VERSION='v8.8.15'" in js
    assert "model.signals(match" in js
    assert "model.allSignals" not in js
    for token in [
        "patchTopStrip",
        "patchMatchCards",
        "patchSignalPage",
        "patchVerdict",
        "FINAL Quality",
        "zielonych CORE",
    ]:
        assert token in js


def test_project_ui_keeps_diagnostics_but_removes_core_emphasis_when_blocked():
    js = read("frontend/project-ui-quality-v8815.js")
    assert "patchDiagnosticCoreRows" in js
    assert "LAB / NIE CORE" in js
    assert "DIAGNOSTYKA / NIE CORE" in js
    assert "checkpointEligible" in js
    assert "resultApi?.eligible" in js
    assert "querySelectorAll('.hot').forEach(x=>x.classList.remove('hot'))" in js


def test_project_ui_bridge_has_no_polling_or_mutation_observer():
    js = read("frontend/project-ui-quality-v8815.js")
    assert "new MutationObserver(" not in js
    assert "setInterval(" not in js
    assert "requestAnimationFrame(patchAll)" in js


def test_project_ui_suppresses_only_automatic_startup_rerenders():
    js = read("frontend/project-ui-quality-v8815.js")
    assert "RUNTIME_FIX='v8.8.17'" in js
    assert "STARTUP_SUPPRESS_MS=1250" in js
    assert "startupRenderShouldBeSuppressed" in js
    assert "userRenderPermit" in js
    assert "isUserRenderControl" in js
    assert "if(userRenderPermit>0)return false" in js
    assert "if(startupRenderShouldBeSuppressed())" in js
