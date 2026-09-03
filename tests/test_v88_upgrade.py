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
    js=text("frontend/adaptive-prod-bridge.js")
    assert "adaptive_prod_score:final" in js
    assert "ensemble:rawEnsemble" in js
    assert "final_score:final" in js
    assert "v88AdaptiveProd=true" in js
    assert "wrapAutoLearn" in js


def test_v88_performance_intelligence_compatibility_symbols_exist():
    js=text("frontend/adaptive-prod-bridge.js")
    css=text("frontend/adaptive-prod-bridge.css")
    for token in ["confidenceRows","renderMarkets","segmentRows","modelRows","repeated_errors","data/adaptive_learning_v79.json","data/model_telemetry_v84c.json"]:
        assert token in js
    assert ".pc88-dashboard" in css
    assert ".sc88-generator-head" in css


def test_v88_preserves_protected_runtime_contract():
    html=text("frontend/index.html")
    meta=text("frontend/app-meta.js")
    upgrade=text("frontend/adaptive-prod-bridge.js")
    assert 'src="symphony2.js"' in html
    assert 'href="symphony2.css"' in html
    assert "scenario-studio-v82a.js" not in html
    assert "scenario-studio-v82a.css" not in html
    assert "model-guide.js?v=87dc1" in html
    assert "adaptive-prod-bridge.css" in html
    assert "adaptive-prod-bridge.js" in html
    assert "v88-upgrade.js" not in html
    assert "v88-upgrade.css" not in html
    assert "appVersion: 'v8.0.1'" in meta
    assert "displayVersion:'v8.8.7'" in meta
    assert "currentUiArchitecture:'v8.8.7-checkpoint-quality-lock'" in meta
    assert "symphonyVersion:'canonical'" in meta
    assert "generatorPolicyVersion" not in meta
    assert "function applyV88Brand()" in upgrade
    assert "window.TENIS_AI_APPLY_META?.()" in upgrade
