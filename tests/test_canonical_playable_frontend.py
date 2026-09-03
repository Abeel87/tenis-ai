from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYABLE_UI = ROOT / "frontend" / "playable-ui.js"
MATCH_BROWSER = ROOT / "frontend" / "match-browser.js"


def test_playable_ui_prefers_backend_projection_and_keeps_raw_fallback_separate():
    text = PLAYABLE_UI.read_text(encoding="utf-8")

    assert "function projectionSignals(match)" in text
    assert "match?.superbet_playable_v912" in text
    assert "if(projected!==null)return projected.slice(0,max);" in text
    assert "Backward-compatible fallback only for datasets produced before the additive" in text
    assert "return modelSignals(match,Math.max(100,max))" in text


def test_decision_center_uses_same_canonical_playable_projection():
    text = PLAYABLE_UI.read_text(encoding="utf-8")

    assert "function decisionRows(match,api)" in text
    assert "const projected=playableSignals(match,100);" in text
    assert "const rows=decisionRows(match,api);" in text


def test_match_browser_and_top_strip_share_playable_signals_gate():
    playable = PLAYABLE_UI.read_text(encoding="utf-8")
    browser = MATCH_BROWSER.read_text(encoding="utf-8")

    assert "const signal=match?playableSignals(match,1)[0]:null;" in playable
    assert "TENIS_AI_PLAYABLE_UI_V917?.playableSignals?.(m,100)" in browser
    assert "const isPlayable=m=>playableSignals(m).length>0;" in browser
