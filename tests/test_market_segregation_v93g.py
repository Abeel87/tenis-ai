from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "frontend" / "market-segregation-v93g.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-list-visibility-v916.js").read_text(encoding="utf-8")


def test_market_segregation_mirrors_decision_center_style_filters():
    for marker in (
        "['all','Wszystkie'",
        "['result','Wynik'",
        "['games','Gemy'",
        "['checkpoints','Po 2/4/6'",
        "['handicap','Handicap'",
        "['special','Specjalne'",
    ):
        assert marker in UI


def test_raw_and_superbet_keep_independent_filter_state():
    assert "state={raw:'all',book:'all'}" in UI
    assert "text.includes('superbet')?'book':'raw'" in UI
    assert "data-rp93g-layer" in UI
    assert "[data-rp921-match] details" in UI


def test_market_groups_cover_current_large_lists():
    for marker in (
        "game state",
        "handicap",
        "total|gemy|games|over|under|parity",
        "winner|wygr|match score|exact .*score",
    ):
        assert marker in UI
    assert "rp93g-group-head" in UI
    assert "countsFor(rows)" in UI


def test_segregation_is_presentation_only_and_loaded_after_raw_layer():
    assert "market-segregation-v93g.js?v=93g&contract=raw-playable-ui-only" in LOADER
    assert "rawPlayableReady" in LOADER
    assert "loadMarketSegregationV93G" in LOADER
    assert "fetch(" not in UI
    assert "setInterval(" not in UI
    assert "TENIS_AI_MARKET_SEGREGATION_V93G" in UI
