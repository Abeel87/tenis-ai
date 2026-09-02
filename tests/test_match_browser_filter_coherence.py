from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "frontend" / "match-browser-v945.js"
PLAYABLE = ROOT / "frontend" / "playable-ui-coherence-v917.js"


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


def test_match_browser_keeps_navigation_state_across_detail_return():
    text = BROWSER.read_text(encoding="utf-8")
    assert "returnScroll" in text
    assert "returnPending" in text
    assert "captureOpenGroups" in text
    assert "restoreReturnScroll" in text
    assert "sessionStorage" in text
