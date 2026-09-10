
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v78e4_fetches_today_and_tomorrow():
    yml = (ROOT / ".github/workflows/update-and-pages.yml").read_text(encoding="utf-8")
    assert "FIXTURE_DAYS: '2'" in yml

def test_v78e4_keeps_current_and_legacy_separate():
    js = (ROOT / "frontend/performance-center.js").read_text(encoding="utf-8")
    assert "legacy:m.model_version!==CURRENT_MODEL_VERSION" in js
    assert "if(x.legacy)return false;" in js
    assert "Historia referencyjna" not in js
    assert "<b>v7.8E4</b>" not in js

