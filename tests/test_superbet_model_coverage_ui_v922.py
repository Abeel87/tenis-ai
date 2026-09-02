from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = (ROOT / "frontend" / "superbet-model-coverage.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-list-visibility.js").read_text(encoding="utf-8")


def test_coverage_bridge_loads_after_playable_without_legacy_raw_panel():
    assert "function loadSuperbetModelCoverageV922()" in LOADER
    assert "superbet-model-coverage.js?v=933&contract=operator-model-coverage" in LOADER
    assert "script.addEventListener('load',loadSuperbetModelCoverageV922,{once:true})" in LOADER
    assert "script.addEventListener('load',loadMarketSegregationV93G,{once:true})" in LOADER
    assert "raw-playable-separation-v921" not in LOADER


def test_real_superbet_rows_show_model_probability_or_explicit_uncovered_state():
    assert "MODEL ${approximate?'~':''}${fmt(signal.score)}" in ADDON
    assert "MODEL: niepokryty" in ADDON
    assert "Superbet ✓" in ADDON
    assert "push_probability" in ADDON
    assert "canonical_selections" in ADDON
    assert "model_signals" in ADDON
    assert "coverage_shadow_signals" in ADDON
    assert "SHADOW · " in ADDON
    assert "SUPERBET — pełna aktualna oferta" in ADDON


def test_ui_bridge_never_mutates_model_raw_ownership_fields():
    forbidden = [
        ".p751-top-pick",
        ".p751-strength",
        ".rp921-raw-card",
        "[data-rp921-match]",
        "setBars(",
        "model_weight",
        "threshold=",
        "supabase",
    ]
    lowered = ADDON.lower()
    for token in forbidden:
        assert token.lower() not in lowered
    assert "data-superbet-model-coverage-v922" in ADDON
    assert "MODEL/RAW pozostaje osobną warstwą" in ADDON


def test_addon_is_display_only_and_does_not_fetch_or_train():
    lowered = ADDON.lower()
    for token in ("fetch(", "xmlhttprequest", "fit(", "train(", "websocket"):
        assert token not in lowered
    assert "TENIS_AI_SUPERBET_MODEL_COVERAGE_V922" in ADDON
    assert "coverageKey" in ADDON
