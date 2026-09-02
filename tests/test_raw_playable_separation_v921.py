from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
LOADER = (FRONTEND / "match-list-visibility-v916.js").read_text(encoding="utf-8")
APP_META = (FRONTEND / "app-meta.js").read_text(encoding="utf-8")
PLAYABLE = (FRONTEND / "playable-ui.js").read_text(encoding="utf-8")
COVERAGE = (FRONTEND / "superbet-model-coverage.js").read_text(encoding="utf-8")
SEGREGATION = (FRONTEND / "market-segregation.js").read_text(encoding="utf-8")


def test_legacy_raw_playable_runtime_is_gone():
    assert not (FRONTEND / "raw-playable-separation-v921.js").exists()
    assert "loadRawPlayableV921" not in LOADER
    assert "raw-playable-separation-v921" not in LOADER
    assert "symphony_match_cards_v90" not in LOADER + PLAYABLE + COVERAGE + SEGREGATION


def test_current_loader_chain_has_single_owners():
    assert "playable-ui.js" in APP_META
    assert "playable-freshness.js" in APP_META
    assert "loadPlayableUiV917" not in LOADER
    assert "loadSuperbetModelCoverage" in LOADER
    assert "loadMarketSegregation" in LOADER
    assert "setTimeout(loadSuperbetModelCoverage,0)" in LOADER
    assert "script.addEventListener('load',loadMarketSegregation,{once:true})" in LOADER


def test_model_raw_and_playable_are_still_separate():
    assert "MODEL/RAW analytics stay independent" in PLAYABLE
    assert "MODEL / RAW bez zmian" in PLAYABLE
    assert "playableSignals:modelSignals" in PLAYABLE
    assert "finally{if(strictApi)window.TENIS_AI_PLAYABLE_UI_V917=strictApi}" in PLAYABLE


def test_operator_coverage_owns_full_superbet_offer_without_fabrication():
    assert "SUPERBET — pełna aktualna oferta" in COVERAGE
    assert "canonical_selections" in COVERAGE
    assert "MODEL: niepokryty" in COVERAGE
    assert "brak pokrycia oznacza „niepokryty”, a nie wymyślony wynik" in COVERAGE
    assert "data-superbet-model-coverage-v922" in SEGREGATION
    assert "sbmc922-line" in SEGREGATION
