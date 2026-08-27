from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_v883_final_cleanup_has_no_delayed_global_polish_loop():
    js = read("frontend/v883-final.js")
    assert "RUNTIME_FIX='v8.8.20'" in js
    assert "tenis-ai:stats-ready" in js
    assert "tenis-ai:stats-dashboard-ready" in js
    assert "wrapScenarioOpen" in js
    assert "[120,350,800,1500,2600]" not in js
    assert "setTimeout(polish" not in js
    assert "document.addEventListener('click',()=>" not in js
    assert "requestAnimationFrame" in js


def test_v88_compat_bridge_keeps_adaptive_logic_without_polling():
    js = read("frontend/v88-upgrade.js")
    assert "RUNTIME_FIX='v8.8.21'" in js
    assert "adaptive_prod_score:final" in js
    assert "v88AdaptiveProd=true" in js
    assert "wrapScenarioOpen" in js
    assert "[250,800,1600]" not in js
    assert "setTimeout(" not in js
    assert "#scenario-v82a-panel" in js
    assert "tenis-ai:stats-dashboard-ready" in js


def test_v88_layers_do_not_use_mutation_or_interval_polling():
    for path in ["frontend/v88-upgrade.js", "frontend/v883-final.js"]:
        js = read(path)
        assert "new MutationObserver(" not in js
        assert "setInterval(" not in js
