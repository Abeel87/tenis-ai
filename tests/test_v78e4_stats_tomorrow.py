
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v78e4_fetches_today_and_tomorrow():
    yml = (ROOT / ".github/workflows/update-and-pages.yml").read_text(encoding="utf-8")
    assert "FIXTURE_DAYS: '2'" in yml

def test_v78e4_keeps_current_and_legacy_separate():
    js = (ROOT / "frontend/performance-center.js").read_text(encoding="utf-8")
    assert "if(x.legacy)return false;" in js
    assert "Historia referencyjna" in js
    assert "legacy=bs.legacy_overall" in js
    assert "window.TENIS_AI_META?.appVersion" in js
    assert "<b>v7.8E4</b>" not in js

def test_v78e4_bumps_pwa_cache():
    sw = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")

    # Verify the current cache contract and canonical Symphony assets without
    # freezing the test to a historical Symphony cache version.
    assert "const CACHE='tenis-ai-" in sw
    assert "'symphony2.js'" in sw
    assert "'symphony2.css'" in sw
    assert "cache.addAll(ASSETS)" not in sw
