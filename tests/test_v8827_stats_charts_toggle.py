from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_model_trends_own_their_expand_toggle():
    js = (ROOT / "frontend/model-trends.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/style.css").read_text(encoding="utf-8")

    assert "data-mt84e2-toggle" in js
    assert "Pokaż wykresy modeli" in js
    assert "Ukryj wykresy modeli" in js
    assert "v853c-collapsed" in js
    assert "#mt84e2.v853c-collapsed > :not(.mt84e2-head):not(.v853c-toggle)" in css
    assert "#mt84e2.v853c-collapsed > .v853c-toggle" in css
    assert not (ROOT / "frontend/ui-organizer.js").exists()
