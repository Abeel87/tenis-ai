from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_model_trends_use_native_details_without_legacy_organizer_toggle():
    index = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/model-trends.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/style.css").read_text(encoding="utf-8")

    assert "ui-organizer.js" not in index
    assert not (ROOT / "frontend/ui-organizer.js").exists()
    assert '<details class="mt84e2-details">' in js
    assert "pokaż trendy" in js
    assert "v853c-collapsed" not in css
    assert ".v853c-toggle" not in css
