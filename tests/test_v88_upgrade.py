from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_match_winner_uses_same_final_ranking_as_other_markets():
    js=text("frontend/model-guide.js")
    assert "Missing base probabilities must not be fabricated" in js
    assert "const winner=sorted.find" not in js
    assert "Kto wygra mecz" in js
    assert "adaptive_learning_v79?.signals" in js

def test_v88_generator_uses_adaptive_prod_wrapper():
    js=text("frontend/v88-upgrade.js")
    assert "adaptive_prod_score:final" in js
    assert "ensemble:rawEnsemble" in js
    assert "final_score:final" in js
    assert "v88AdaptiveProd=true" in js
    assert "wrapAutoLearn" in js

def test_v88_performance_intelligence_exists():
    js=text("frontend/v88-upgrade.js")
    css=text("frontend/v88-upgrade.css")

    for token in [
        "confidenceRows",
        "renderMarkets",
        "segmentRows",
        "modelRows",
        "repeated_errors",
        "data/adaptive_learning_v79.json",
        "data/model_telemetry_v84c.json",
    ]:
        assert token in js

    assert ".pc88-dashboard" in css
    assert ".sc88-generator-head" in css

def test_v88_preserves_protected_runtime_contract():
    html=text("frontend/index.html")
    meta=text("frontend/app-meta.js")
    upgrade=text("frontend/v88-upgrade.js")

    assert "scenario-studio-v82a.js?v=82a6" in html
    assert "scenario-studio-v82a.css?v=82a51" in html
    assert "model-guide.js?v=87dc1" in html

    assert "v88-upgrade.css?v=88" in html
    assert "v88-upgrade.js?v=88" in html

    # Runtime compatibility remains fixed; visible version has a single owner.
    assert "appVersion: 'v8.0.1'" in meta
    assert "displayVersion: 'v8.8.4'" in meta

    # Compatibility bridge delegates visible branding to central metadata.
    assert "function applyV88Brand()" in upgrade
    assert "window.TENIS_AI_APPLY_META?.()" in upgrade
