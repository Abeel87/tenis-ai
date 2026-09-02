from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYABLE = (ROOT / "frontend" / "playable-ui.js").read_text(encoding="utf-8")
COVERAGE = (ROOT / "frontend" / "superbet-model-coverage.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-visibility.js").read_text(encoding="utf-8")
APP_META = (ROOT / "frontend" / "app-meta.js").read_text(encoding="utf-8")
BASE = (ROOT / "frontend" / "project-ui.js").read_text(encoding="utf-8")


def test_playable_never_overwrites_base_model_card_fields():
    assert "card.querySelector('.p751-top-pick')" not in PLAYABLE
    assert "card.querySelector('.p751-strength')" not in PLAYABLE
    assert "setBars(card" not in PLAYABLE
    assert "data-v917-playable-card" in PLAYABLE
    assert "MODEL / RAW bez zmian" in PLAYABLE


def test_playable_match_total_has_its_own_slot():
    assert "card.querySelector('[data-v917-match-total-preview]')" in PLAYABLE
    assert "card.querySelector('.p753-match-total-preview')" not in PLAYABLE
    assert "data-v917-match-total-preview" in PLAYABLE


def test_model_top_strip_is_preserved_beside_superbet_top_strip():
    assert 'document.querySelector(\'#app [data-playable-top-v917="1"]\')' in PLAYABLE
    assert '.p751-top:not([data-playable-top-v917])' in PLAYABLE
    assert "if(rawTop)rawTop.insertAdjacentElement('afterend',fresh)" in PLAYABLE
    assert "const old=document.querySelector('#app .p751-top')" not in PLAYABLE


def test_model_signal_page_is_not_filtered_by_operator_availability():
    assert "posortowane po sile modelu" in BASE
    assert "page.dataset.playableUiV917='raw-preserved'" in PLAYABLE
    assert "if(!signal){button.remove();continue}" not in PLAYABLE
    assert "button.querySelector('strong')" not in PLAYABLE


def test_strong_filter_uses_raw_model_rows_during_base_render():
    assert "TENIS_AI_PLAYABLE_UI_V917?.playableSignals?.(m,1)" in BASE
    assert "playableSignals:modelSignals" in PLAYABLE
    assert "finally{if(strictApi)window.TENIS_AI_PLAYABLE_UI_V917=strictApi}" in PLAYABLE
    assert "function playableSignals(match,limit=100)" in PLAYABLE
    assert ".filter(row=>isPlayable(match,row))" in PLAYABLE


def test_current_operator_chain_has_no_legacy_v921_dependency():
    assert "raw-playable-separation-v921" not in LOADER
    assert "loadRawPlayableV921" not in LOADER
    assert "playable-ui-coherence-v917.js" not in LOADER + APP_META
    assert "load('playable-ui.js','tenis-ai-playable-ui',freshness)" in APP_META
    assert "superbet-model-coverage.js" in LOADER
    assert "market-segregation.js" in LOADER
    assert "match-detail.js" in LOADER
    assert "superbet-model-coverage-v922.js" not in LOADER
    assert "market-segregation-v93g.js" not in LOADER
    assert "match-detail-architecture-v950.js" not in LOADER
    assert "data-superbet-model-coverage-v922" in COVERAGE
    assert "canonical_selections" in COVERAGE


def test_scope_remains_ui_only():
    forbidden = ["supabase", "fit(", "train(", "model_weight", "threshold=", "settlement"]
    lowered = (PLAYABLE + COVERAGE).lower()
    for token in forbidden:
        assert token not in lowered
