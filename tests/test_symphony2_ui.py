from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "symphony2.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "symphony2.css").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
APP_META = (ROOT / "frontend" / "app-meta.js").read_text(encoding="utf-8")
PLAYABLE_UI = (ROOT / "frontend" / "playable-ui-coherence-v917.js").read_text(encoding="utf-8")


def test_single_symphony2_frontend_is_loaded():
    assert "symphony2.js?v=210" in INDEX
    assert "symphony2.css?v=210" in INDEX
    for legacy in (
        "symphony-v90.js", "symphony-v90.css", "symphony-stats-v90d.js",
        "symphony-stats-v90d.css", "symphony-surface-v90.js",
        "symphony-playable-detail-guard-v915.js",
    ):
        assert legacy not in INDEX


def test_stats_ui_reads_only_symphony2_stats():
    assert "./data/symphony2_stats.json" in JS
    assert "#pc77" in JS
    assert "symphony2-performance" in JS
    assert "Wyniki starej Symfonii i starego generatora nie są importowane" in JS
    assert "symphony_stats_v90d.json" not in JS
    assert "symphony_model_stats_v93.json" not in JS


def test_symphony_hub_explains_exact_superbet_probability_contract():
    assert "dokładną aktualną ofertę Superbet" in JS
    assert "operator_model_probability" in JS
    assert "joint_probability" in JS
    assert "learning_support_rows" in JS
    assert "#symphony2-hub" in JS
    assert "Ułóż Symfonię 2.0" in JS


def test_symphony2_owns_the_retired_scenario_nav_slot():
    assert "data-p751-nav=\"symphony2\"" in JS
    assert "data-p751-nav=\"scenarios\"" in JS  # migration lookup only
    assert "nav.dataset.p751Nav='symphony2'" in JS
    assert "nav.innerHTML='<span>🎼</span><b>Symfonia 2.0</b>'" in JS
    assert "TENIS_AI_SCENARIOS" not in JS
    assert "scenario-v82a-panel" not in JS


def test_match_view_replaces_legacy_symphony_surfaces_with_symphony2():
    assert "symphony2-match-detail" in JS
    assert "cleanupLegacySymphony" in JS
    assert "data-symphony-match-mini" in JS
    assert "SYMFONIA 2.0 · PLAYABLE" in JS
    assert "RAW nie jest źródłem linii PLAYABLE" in JS
    assert ".s2-match-detail" in CSS


def test_match_view_compacts_full_superbet_offer_without_changing_data():
    assert "compactSuperbet" in JS
    assert "SUPERBET · REALNA OFERTA" in JS
    assert "Dokładne rynki i linie Superbet" in JS
    assert "Pokaż pełną ofertę" in JS
    assert "data-s2-offer-extra" in CSS


def test_no_runtime_reads_legacy_compact_card_feed():
    assert "symphony_match_cards_v90.json" not in JS
    assert "symphony_match_cards_v90.json" not in PLAYABLE_UI
    assert "patchSymphonyMinis" not in PLAYABLE_UI
    assert "reloadCompact" not in PLAYABLE_UI


def test_metadata_boots_symphony_live_ui_without_generator_bootstrap():
    assert "symphony2-live-ui-v201.js?v=201" in APP_META
    assert "generator-quality-v888.js" not in APP_META
    assert "scenario-studio-v82a.js" not in APP_META
