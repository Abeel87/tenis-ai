from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scenario_runtime_has_bounded_quality_wait_and_direct_nav():
    js = (ROOT / "frontend" / "scenario-runtime-v202.js").read_text(encoding="utf-8")
    assert "VERSION='v2.0.4'" in js
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


def test_scenario_runtime_recovers_missing_broken_or_hidden_studio_api():
    js = (ROOT / "frontend" / "scenario-runtime-v202.js").read_text(encoding="utf-8")
    assert "scenario-studio-v82a.js?v=82a6&recovery=204" in js
    assert "loadStudioFresh" in js
    assert "scenario-studio-recovery-v204" in js
    assert "ts=${Date.now()}" in js
    assert "removeBrokenShell" in js
    assert "resetStudioRuntime" in js
    assert "panelVisible" in js
    assert "getComputedStyle(panel).display!=='none'" in js
    assert "#scenario-v82a-panel" in js
    assert "#scenario-v82a-dock" in js
    assert "delete window.TENIS_AI_SCENARIOS" in js
    assert "if(tryOpen(api,tab))return true" in js


def test_runtime_replaces_legacy_bottom_nav_handler_instead_of_silent_noop():
    js = (ROOT / "frontend" / "scenario-runtime-v202.js").read_text(encoding="utf-8")
    assert "NAV_SELECTOR='#p751-bottom-nav [data-p751-nav=\"scenarios\"]'" in js
    assert "nav.onclick=directNavClick" in js
    assert "nav.dataset.scenarioDirectNav='204'" in js
    assert "bindDirectNav" in js
    assert "scheduleDirectNavBind" in js
    assert "openScenarios('home')" in js


def test_corrupted_legacy_open_draft_is_removed_without_touching_saved_history():
    js = (ROOT / "frontend" / "scenario-runtime-v202.js").read_text(encoding="utf-8")
    assert "DRAFT_KEY='tenis-ai-v82a-scenario-draft'" in js
    assert "MAX_DRAFT_ITEMS=32" in js
    assert "sanitizeLegacyDraft" in js
    assert "localStorage.removeItem(DRAFT_KEY)" in js
    assert "tenis-ai-v82a-scenarios-local" not in js


def test_scenario_runtime_is_loaded_directly_after_studio_not_by_symphony():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    sym = (ROOT / "frontend" / "symphony2-live-ui-v201.js").read_text(encoding="utf-8")
    studio = 'scenario-studio-v82a.js?v=82a6&hf=84a1&amp;audit=884'
    runtime = 'scenario-runtime-v202.js?v=205'
    assert studio in index
    assert runtime in index
    assert 'scenario-runtime-v202.js?v=203' not in index
    assert index.index(studio) < index.index(runtime) < index.index('symphony2.js?v=200')
    assert "scenario-runtime-v202.js" not in sym
    assert "data-sc-generate" not in sym
    assert "TENIS_AI_GENERATOR_QUALITY_V888" not in sym
    assert "MutationObserver" not in sym
    assert "stopImmediatePropagation" not in sym
