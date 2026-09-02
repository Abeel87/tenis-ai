from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_performance_center_simple_first():
    js = (ROOT / "frontend/performance-center.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/performance-center.css").read_text(encoding="utf-8")

    assert "Czy modelowi można dziś ufać?" in js
    assert "Najlepiej działające rynki" in js
    assert "Statystyki PRO" in js
    assert "Jak to czytać?" in js
    assert "Mocna próba" in js
    assert "Za mało danych" in js
    assert "n=" not in js[js.find("function sampleBadge"):js.find("function ciText")]
    assert ".pc12-summary" in css
    assert ".pc12-market-grid" in css
