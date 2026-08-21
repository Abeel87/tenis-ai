from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_runtime_restores_controls():
    s=(ROOT/"frontend/restore-v762.js").read_text(encoding="utf-8")
    assert "Zwiń wszystko" in s
    assert "Rozwiń wszystko" in s
    assert "Statystyki / skuteczność" in s
    assert ".p751-group" in s

def test_runtime_clickable_players():
    s=(ROOT/"frontend/restore-v762.js").read_text(encoding="utf-8")
    assert ".p751-names > b, .p751-matchup > b" in s
    assert "openPlayer" in s
    assert "stopImmediatePropagation" in s

def test_installer_fixes_player_and_analytics():
    s=(ROOT/"install_v762.py").read_text(encoding="utf-8")
    assert "window.tenisAIPlayerProfileOpen=selectPlayer;" in s
    assert "setInterval(inject,700);" in s
    assert "Skuteczność modelu · zielone sygnały" in s

def test_assets_and_cache():
    s=(ROOT/"install_v762.py").read_text(encoding="utf-8")
    assert "restore-v762.css" in s
    assert "restore-v762.js" in s
    assert "tenis-ai-v762-ui-restore-player-fix" in s
