from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "frontend" / "market-segregation.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-visibility.js").read_text(encoding="utf-8")


def test_market_segregation_keeps_readable_filters():
    for marker in (
        "['all','Wszystkie'",
        "['result','Wynik'",
        "['games','Gemy'",
        "['checkpoints','Po 2/4/6'",
        "['handicap','Handicap'",
        "['special','Specjalne'",
    ):
        assert marker in UI


def test_segregation_groups_only_current_superbet_coverage_panel():
    assert "[data-superbet-model-coverage-v922]" in UI
    assert ":scope > .sbmc922-lines" in UI
    assert "sbmc922-line" in UI
    assert "dataset.sbmc922Market" in UI
    assert "[data-rp921-match]" not in UI
    assert ".rp921-line" not in UI


def test_market_groups_cover_current_large_lists():
    for marker in (
        "game state",
        "handicap",
        "total|gemy|games|over|under|parity",
        "winner|wygr|match score|exact .*score",
    ):
        assert marker in UI
    assert "rp93g-group-head" in UI
    assert "marketGroup" in UI


def test_segregation_is_presentation_only_and_loaded_after_coverage():
    assert "script.src='market-segregation.js'" in LOADER
    assert "loadMarketSegregation" in LOADER
    assert "script.addEventListener('load',loadMarketSegregation,{once:true})" in LOADER
    assert "loadSuperbetModelCoverage" in LOADER
    assert "market-segregation-v93g.js" not in LOADER
    assert "raw-playable-separation-v921" not in LOADER
    assert "fetch(" not in UI
    assert "setInterval(" not in UI
    assert "TENIS_AI_MARKET_SEGREGATION_V93G" in UI
