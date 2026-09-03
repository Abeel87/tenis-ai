from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_project_ui_quality_bridge_is_loaded_last():
    html = read("frontend/index.html")
    assert "project-ui-quality.js" in html
    assert html.index("market-quality.js") < html.index("project-ui-quality.js")
    assert "project-ui-quality-v8815.js" not in html
    assert "checkpoint-quality-v887.js" not in html


def test_project_ui_recommendations_use_final_signals():
    js = read("frontend/project-ui-quality.js")
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
    js = read("frontend/project-ui-quality.js")
    assert "patchDiagnosticCoreRows" in js
    assert "LAB / NIE CORE" in js
    assert "DIAGNOSTYKA / NIE CORE" in js
    assert "checkpointEligible" in js
    assert "resultApi?.eligible" in js
    assert "querySelectorAll('.hot').forEach(x=>x.classList.remove('hot'))" in js


def test_project_ui_bridge_has_no_polling_or_mutation_observer():
    js = read("frontend/project-ui-quality.js")
    assert "new MutationObserver(" not in js
    assert "setInterval(" not in js
    assert "requestAnimationFrame(patchAll)" in js


def test_project_ui_suppresses_only_automatic_startup_rerenders():
    js = read("frontend/project-ui-quality.js")
    assert "RUNTIME_FIX='v8.8.19'" in js
    assert "STARTUP_SUPPRESS_MS=1250" in js
    assert "startupRenderShouldBeSuppressed" in js
    assert "userRenderPermit" in js
    assert "isUserRenderControl" in js
    assert "if(userRenderPermit>0)return false" in js
    assert "if(startupRenderShouldBeSuppressed())" in js


def test_project_ui_serve_props_is_explicitly_uncalibrated_lab():
    js = read("frontend/project-ui-quality.js")
    assert "patchServePropsHonesty" in js
    assert "LAB · N/D" in js
    assert "model count · niekalibrowany" in js
    assert "kurs modelowy nie jest potwierdzonym fair oddsem" in js
    assert "nie wchodzi do CORE" in js


def test_project_ui_exact_score_is_lab_without_final_telemetry():
    js = read("frontend/project-ui-quality.js")
    assert "patchExactScoreHonesty" in js
    assert "Dokładny wynik · MODEL LAB · N/D" in js
    assert "Brak osobnej telemetrii FINAL — diagnostyka, nie CORE." in js


def test_project_ui_incomplete_ou_pairs_are_shown_as_nd():
    js = read("frontend/project-ui-quality.js")
    assert "patchIncompleteMarketLines" in js
    assert "hasCompleteOuPair" in js
    assert "num(row.over)!=null&&num(row.under)!=null" in js
    assert "value.textContent='N/D'" in js
    assert "patchProjectDetail" in js
