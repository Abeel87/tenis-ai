from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "frontend" / "match-browser.js"
PLAYABLE = ROOT / "frontend" / "playable-ui.js"
FRESHNESS = ROOT / "frontend" / "playable-freshness.js"


def test_playable_signal_is_analysis_evidence_for_z_danymi_filter():
    text = BROWSER.read_text(encoding="utf-8")
    assert "playableSignals(m).some" in text
    assert "function hasAnalysis(m)" in text
    assert "state.qualityOnly&&!hasAnalysis(m)" in text
    assert "state.mode==='playable'&&!isPlayable(m)" in text


def test_top_superbet_is_resynchronized_after_match_browser_filters():
    browser = BROWSER.read_text(encoding="utf-8")
    playable = PLAYABLE.read_text(encoding="utf-8")
    assert "TENIS_AI_PLAYABLE_UI_V917?.patchHome?.()" in browser
    assert ".p751-match-card[data-p751-open]:not([hidden])" in playable
    assert "Top sygnały · SUPERBET" in playable


def test_match_browser_loads_after_strict_playable_gate():
    text = FRESHNESS.read_text(encoding="utf-8")
    assert "script.src='match-browser.js'" in text
    assert "window.TENIS_AI_PLAYABLE_UI_V917=wrapped" in text
    assert text.index("window.TENIS_AI_PLAYABLE_UI_V917=wrapped") < text.index("script.src='match-browser.js'")


def test_match_browser_keeps_navigation_state_across_detail_return():
    text = BROWSER.read_text(encoding="utf-8")
    assert "returnScroll" in text
    assert "returnPending" in text
    assert "captureOpenGroups" in text
    assert "restoreReturnScroll" in text
    assert "sessionStorage" in text
