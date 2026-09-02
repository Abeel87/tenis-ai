from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_runtime_restores_controls():
    s=(ROOT/"frontend/restore-ui.js").read_text(encoding="utf-8")
    assert "Zwiń wszystko" in s
    assert "Rozwiń wszystko" in s
    assert "Statystyki / skuteczność" in s
    assert ".p751-group" in s

def test_runtime_clickable_players():
    s=(ROOT/"frontend/restore-ui.js").read_text(encoding="utf-8")
    assert ".p751-names > b, .p751-matchup > b" in s
    assert "openPlayer" in s
    assert "stopImmediatePropagation" in s
