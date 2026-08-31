from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scenario_runtime_has_bounded_quality_wait_and_direct_nav():
    js = (ROOT / "frontend" / "scenario-runtime-v202.js").read_text(encoding="utf-8")
    assert "READY_TIMEOUT_MS=1200" in js
    assert "Promise.race" in js
    assert "TENIS_AI_GENERATOR_QUALITY_V888" in js
    assert "checkGroup" in js
    assert "TENIS_AI_SCENARIOS" in js
    assert "data-p751-nav=\"scenarios\"" in js
    assert "setInterval" not in js


def test_symphony_live_ui_no_longer_intercepts_scenarios_or_observes_whole_dom():
    js = (ROOT / "frontend" / "symphony2-live-ui-v201.js").read_text(encoding="utf-8")
    assert "scenario-runtime-v202.js?v=202" in js
    assert "data-sc-generate" not in js
    assert "TENIS_AI_GENERATOR_QUALITY_V888" not in js
    assert "MutationObserver" not in js
    assert "stopImmediatePropagation" not in js
