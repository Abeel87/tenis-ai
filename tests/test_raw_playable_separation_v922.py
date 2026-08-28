from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYABLE = (ROOT / "frontend" / "playable-ui-coherence-v917.js").read_text(encoding="utf-8")
RAW = (ROOT / "frontend" / "raw-playable-separation-v921.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-list-visibility-v916.js").read_text(encoding="utf-8")
BASE = (ROOT / "frontend" / "ui-v751.js").read_text(encoding="utf-8")


def test_playable_never_overwrites_base_model_card_fields():
    # These selectors are owned by ui-v751 MODEL/RAW and must never be mutation targets
    # for the operator layer again.
    assert "card.querySelector('.p751-top-pick')" not in PLAYABLE
    assert "card.querySelector('.p751-strength')" not in PLAYABLE
    assert "setBars(card" not in PLAYABLE
    assert "data-v917-playable-card" in PLAYABLE
    assert "MODEL / RAW bez zmian" in PLAYABLE


def test_playable_match_total_has_its_own_slot():
    # A missing PLAYABLE total must not remove ui-v751's model match-total preview.
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
    # ui-v751 still calls the historical PLAYABLE bridge in its ⭐80+ filter.
    # v9.2.2 supplies raw model rows only for that synchronous base render and then
    # immediately restores the strict Superbet API used by actionable surfaces.
    assert "TENIS_AI_PLAYABLE_UI_V917?.playableSignals?.(m,1)" in BASE
    assert "playableSignals:modelSignals" in PLAYABLE
    assert "finally{if(strictApi)window.TENIS_AI_PLAYABLE_UI_V917=strictApi}" in PLAYABLE
    assert "function playableSignals(match,limit=100)" in PLAYABLE
    assert ".filter(row=>isPlayable(match,row))" in PLAYABLE


def test_raw_layer_loads_after_strict_playable_gate():
    assert "playable-ui-coherence-v917.js?v=922&contract=raw-playable" in LOADER
    assert "raw-playable-separation-v921.js?v=921&contract=raw-playable" in LOADER
    assert "script.addEventListener('load',loadRawPlayableV921,{once:true})" in LOADER
    assert "🧠 MODEL / RAW · analiza" in RAW
    assert "Niezależne od Superbet" in RAW


def test_scope_remains_ui_only():
    # Regression guard: this follow-up must stay in frontend/tests and must not
    # introduce model/training/settlement/Supabase hooks into the ownership layer.
    forbidden = [
        "supabase", "fit(", "train(", "model_weight", "threshold=", "settlement",
    ]
    lowered = PLAYABLE.lower()
    for token in forbidden:
        assert token not in lowered
