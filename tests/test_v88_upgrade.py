from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_v88_match_winner_is_restored_and_pinned():
    js=text("frontend/model-guide.js")
    assert "v8.8 MATCH WINNER FALLBACK" in js
    assert "const winner=sorted.find" in js
    assert "Kto wygra mecz" in js
    assert "adaptive_learning_v79?.signals" in js

def test_v88_generator_uses_adaptive_prod_wrapper():
    js=text("frontend/v88-upgrade.js")
    assert "adaptive_prod_score:final" in js
    assert "ensemble:final" in js
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

    # Chroniony kontrakt runtime pozostaje v8.7.
    assert "displayVersion: 'v8.7'" in meta

    # Widoczna wersja funkcjonalna jest nakładana przez v8.8.
    assert "function applyV88Brand()" in upgrade
    assert "Tenis AI · v8.8" in upgrade
