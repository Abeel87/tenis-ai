
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v78e4_fetches_today_and_tomorrow():
    yml = (ROOT / ".github/workflows/update-and-pages.yml").read_text(encoding="utf-8")
    assert "FIXTURE_DAYS: '2'" in yml

def test_v78e4_keeps_current_and_legacy_separate():
    js = (ROOT / "frontend/performance-center-v77.js").read_text(encoding="utf-8")
    assert "if(x.legacy)return false;" in js
    assert "Historia referencyjna" in js
    assert "legacy=bs.legacy_overall" in js
    assert "v7.8E4" in js

def test_v78e4_bumps_pwa_cache():
    sw = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")

    # E10 replaced the historical chained cache name with one
    # resilient current cache version. The test should verify that
    # the cache was bumped, not freeze the project on an old name.
    assert "const CACHE = 'tenis-ai-" in sw
    assert "cache.addAll(ASSETS)" not in sw
