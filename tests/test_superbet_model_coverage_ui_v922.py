from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = (ROOT / "frontend" / "superbet-model-coverage-v922.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-list-visibility-v916.js").read_text(encoding="utf-8")


def test_coverage_bridge_loads_only_after_raw_superbet_panel_exists():
    assert "function loadSuperbetModelCoverageV922()" in LOADER
    assert "superbet-model-coverage-v922.js?v=922&contract=operator-model-coverage" in LOADER
    assert "script.addEventListener('load',loadSuperbetModelCoverageV922,{once:true})" in LOADER
    assert "if(window.TENIS_AI_RAW_PLAYABLE_V921){loadSuperbetModelCoverageV922();return}" in LOADER


def test_real_superbet_rows_show_model_probability_or_explicit_uncovered_state():
    assert "MODEL ${approximate?'~':''}${fmt(signal.score)}" in ADDON
    assert "MODEL: niepokryty" in ADDON
    assert "Superbet ✓" in ADDON
    assert "push_probability" in ADDON
    assert "canonical_selections" in ADDON
    assert "model_signals" in ADDON


def test_ui_bridge_never_mutates_model_raw_ownership_fields():
    forbidden = [
        ".p751-top-pick",
        ".p751-strength",
        ".rp921-raw-card",
        "setBars(",
        "model_weight",
        "threshold=",
        "settlement",
        "supabase",
    ]
    lowered = ADDON.lower()
    for token in forbidden:
        assert token.lower() not in lowered
    assert "[data-rp921-match]" in ADDON
    assert "SUPERBET" in ADDON


def test_addon_is_display_only_and_does_not_fetch_or_train():
    lowered = ADDON.lower()
    for token in ("fetch(", "xmlhttprequest", "fit(", "train(", "websocket"):
        assert token not in lowered
    assert "TENIS_AI_SUPERBET_MODEL_COVERAGE_V922" in ADDON
