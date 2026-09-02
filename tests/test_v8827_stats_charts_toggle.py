from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_collapsed_model_trends_keep_expand_toggle_visible():
    js = (ROOT / "frontend/ui-organizer.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/ui-cleanup.css").read_text(encoding="utf-8")

    assert "btn.textContent='Pokaż wykresy modeli'" in js
    assert "trend.append(btn)" in js
    assert "#mt84e2.v853c-collapsed > .v853c-toggle" in css
    assert "display:inline-flex!important" in css
