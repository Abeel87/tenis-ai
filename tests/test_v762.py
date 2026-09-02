from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_navigation_tools_restore_controls():
    s=(ROOT/"frontend/navigation-tools.js").read_text(encoding="utf-8")
    assert "Zwiń wszystko" in s
    assert "Rozwiń wszystko" in s
    assert "Statystyki / skuteczność" in s
    assert ".p751-group" in s


def test_navigation_tools_keep_clickable_players():
    s=(ROOT/"frontend/navigation-tools.js").read_text(encoding="utf-8")
    assert ".p751-names > b, .p751-matchup > b" in s
    assert "openPlayer" in s
    assert "stopImmediatePropagation" in s


def test_retired_restore_runtime_stays_deleted():
    assert not (ROOT/"frontend/restore-v762.js").exists()
    assert not (ROOT/"frontend/restore-v762.css").exists()
