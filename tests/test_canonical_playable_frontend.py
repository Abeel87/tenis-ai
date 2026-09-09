from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYABLE_UI = ROOT / "frontend" / "playable-ui.js"
MATCH_BROWSER = ROOT / "frontend" / "match-browser.js"


def test_playable_ui_uses_only_final_symphony_projection():
    text = PLAYABLE_UI.read_text(encoding="utf-8")

    assert "function projectionSignals(match)" in text
    assert "match?.symphony2_playable" in text
    assert "layer.final_playable_authority!==true" in text
    assert "layer.playable!==true" in text
    assert "return projectionSignals(match).slice(0,max);" in text
    assert "match?.superbet_playable_v912" not in text
    assert "Backward-compatible fallback only for datasets produced before the additive" not in text
    assert "return modelSignals(match,Math.max(100,max))" not in text


def test_decision_center_uses_same_final_symphony_playable_projection():
    text = PLAYABLE_UI.read_text(encoding="utf-8")

    assert "function decisionRows(match,api)" in text
    assert "const projected=active(match)?playableSignals(match,100):[];" in text
    assert "const rows=decisionRows(match,api);" in text
    assert "symphony2_playable" in text


def test_match_browser_and_top_strip_share_final_symphony_playable_gate():
    playable = PLAYABLE_UI.read_text(encoding="utf-8")
    browser = MATCH_BROWSER.read_text(encoding="utf-8")

    assert "const signal=match?playableSignals(match,1)[0]:null;" in playable
    assert "TENIS_AI_PLAYABLE_UI_V917?.playableSignals?.(m,100)" in browser
    assert "const isPlayable=m=>playableSignals(m).length>0;" in browser
    assert "match?.symphony2_playable" in playable
