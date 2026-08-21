from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_profile_bridge():
    s=(ROOT/"install_v761.py").read_text(encoding="utf-8")
    assert "window.tenisAIPlayerProfileOpen=selectPlayer;" in s
    assert "openPlayerProfile761" in s

def test_both_match_views_clickable():
    s=(ROOT/"install_v761.py").read_text(encoding="utf-8")
    assert "p751-names" in s
    assert "p751-matchup" in s
    assert "data-p761-player" in s
    assert "bindPlayerLinks761(o)" in s

def test_cache_and_version():
    s=(ROOT/"install_v761.py").read_text(encoding="utf-8")
    assert "tenis-ai-v761-clickable-players" in s
    assert "Tenis AI v7.6.1 · Klikalne profile" in s
