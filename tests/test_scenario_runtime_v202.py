from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scenario_runtime_has_bounded_quality_wait_and_direct_nav():
    js = (ROOT / "frontend" / "scenario-runtime-v202.js").read_text(encoding="utf-8")
    assert "VERSION='v2.0.3'" in js
    assert "READY_TIMEOUT_MS=1200" in js
    assert "API_TIMEOUT_MS=2200" in js
    assert "Promise.race" in js
    assert "TENIS_AI_GENERATOR_QUALITY_V888" in js
    assert "checkGroup" in js
    assert "TENIS_AI_SCENARIOS" in js
    assert "data-p751-nav=\"scenarios\"" in js
    assert "stopImmediatePropagation" in js
    assert "setInterval" not in js
    assert "MutationObserver" not in js


def test_scenario_runtime_recovers_missing_or_broken_studio_api():
    js = (ROOT / "frontend" / "scenario-runtime-v202.js").read_text(encoding="utf-8")
    assert "scenario-studio-v82a.js?v=82a6&recovery=203" in js
    assert "loadStudioFresh" in js
    assert "scenario-studio-recovery-v203" in js
    assert "ts=${Date.now()}" in js
    assert "removeBrokenShell" in js
    assert "#scenario-v82a-panel" in js
    assert "#scenario-v82a-dock" in js
    assert "delete window.TENIS_AI_SCENARIOS" in js
    assert "return !document.querySelector('#scenario-v82a-panel')?.hidden" in js


def test_scenario_runtime_is_loaded_directly_after_studio_not_by_symphony():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    sym = (ROOT / "frontend" / "symphony2-live-ui-v201.js").read_text(encoding="utf-8")
    studio = 'scenario-studio-v82a.js?v=82a6&hf=84a1&amp;audit=884'
    runtime = 'scenario-runtime-v202.js?v=203'
    assert studio in index
    assert runtime in index
    assert index.index(studio) < index.index(runtime) < index.index('symphony2.js?v=200')
    assert "scenario-runtime-v202.js" not in sym
    assert "data-sc-generate" not in sym
    assert "TENIS_AI_GENERATOR_QUALITY_V888" not in sym
    assert "MutationObserver" not in sym
    assert "stopImmediatePropagation" not in sym
