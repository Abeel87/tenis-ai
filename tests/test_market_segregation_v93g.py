from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "frontend" / "market-segregation-v93g.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-list-visibility-v916.js").read_text(encoding="utf-8")


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
    assert "data-sbmc922-market" in UI
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
    assert "market-segregation-v93g.js?v=933&contract=superbet-coverage-ui-only" in LOADER
    assert "loadMarketSegregationV93G" in LOADER
    assert "script.addEventListener('load',loadMarketSegregationV93G,{once:true})" in LOADER
    assert "loadSuperbetModelCoverageV922" in LOADER
    assert "raw-playable-separation-v921" not in LOADER
    assert "fetch(" not in UI
    assert "setInterval(" not in UI
    assert "TENIS_AI_MARKET_SEGREGATION_V93G" in UI
