from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_live_recovery_layer_is_bootstrapped():
    meta = (ROOT / "frontend" / "app-meta.js").read_text(encoding="utf-8")
    assert "symphony2-live-ui.js?v=201" in meta
    assert "symphony2-live-ui" in meta


def test_live_recovery_exposes_symphony_on_match_cards_and_details():
    js = (ROOT / "frontend" / "symphony2-live-ui.js").read_text(encoding="utf-8")
    assert "SYMFONIA 2.0" in js
    assert "data-s2-live-card" in js
    assert "#p751-match-overlay:not([hidden])" in js
    assert "TENIS_AI_SYMPHONY2.renderMatchDetail" in js
    assert "data-p751-open" in js


def test_symphony_live_ui_no_longer_owns_scenario_runtime():
    js = (ROOT / "frontend" / "symphony2-live-ui.js").read_text(encoding="utf-8")
    assert "MutationObserver" not in js
    assert "data-sc-generate" not in js
    assert "TENIS_AI_GENERATOR_QUALITY_V888" not in js
    assert "TENIS_AI_SCENARIOS" not in js


def test_sym2_feed_parser_rejects_empty_or_invalid_payloads():
    js = (ROOT / "frontend" / "symphony2-live-ui.js").read_text(encoding="utf-8")
    assert "Symphony2 empty feed" in js
    assert "Symphony2 invalid feed" in js
    assert "JSON.parse(text)" in js
