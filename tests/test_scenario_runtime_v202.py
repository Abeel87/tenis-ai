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


def test_symphony_live_ui_boots_new_scenario_runtime_without_intercepting_it():
    js = (ROOT / "frontend" / "symphony2-live-ui-v201.js").read_text(encoding="utf-8")
    assert "scenario-runtime-v202.js?v=203" in js
    assert "data-sc-generate" not in js
    assert "TENIS_AI_GENERATOR_QUALITY_V888" not in js
    assert "MutationObserver" not in js
    assert "stopImmediatePropagation" not in js
