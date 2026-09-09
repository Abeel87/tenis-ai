from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_project_ui_quality_bridge_is_retired_and_canonical_quality_loads_first():
    html = read("frontend/index.html")
    assert "project-ui-quality.js" not in html
    assert not (ROOT/"frontend/project-ui-quality.js").exists()
    assert "market-quality.js" in html
    assert html.index("market-quality.js") < html.index("project-ui.js")

def test_project_ui_recommendations_use_final_signals_directly():
    js = read("frontend/project-ui.js")
    assert "if(api?.signals)" in js
    assert "api.signals(m,40)" in js
    assert "modelAllSignals(m)" in js
    assert "Najlepszy typ" in js
    assert "match-tile-score" in js

def test_quality_semantics_remain_owned_by_market_quality():
    quality = read("frontend/market-quality.js")
    for token in (
        "finalSelectedSignals(match,limit=3)",
        "window.bestSignalsData=(match,limit=3)=>finalSelectedSignals",
        "FINAL Adaptive PROD · Quality Lock",
        "Manual i Model Test/SHADOW zachowują pełne rynki",
    ):
        assert token in quality

def test_project_ui_has_no_legacy_quality_patch_polling():
    js = read("frontend/project-ui.js")
    assert "project-ui-quality" not in js
    assert "setInterval(" not in js
    assert "new MutationObserver(" not in js

def test_project_ui_keeps_lab_and_market_diagnostics_without_dom_patch_bridge():
    js = read("frontend/project-ui.js")
    assert 'data-sp-market="p772-' in js
    assert "function serve(m)" in js
    assert "m.serve_props_v72" in js
    assert "m.exact_match_score" in js
    assert "matchGamesLines" in js
