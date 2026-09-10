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

