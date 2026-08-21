from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_installer_fixes_global_lexical_all():
    s=(ROOT/'install_v755.py').read_text(encoding='utf-8')
    assert "typeof all!=='undefined'" in s
    assert "window.all.find" in s  # searched/replaced old broken expression
    assert "rows().find" in s
    assert "tenis-ai-v755-match-games-hotfix" in s

def test_readme_documents_root_cause():
    s=(ROOT/'V7.5.5_README.txt').read_text(encoding='utf-8')
    assert 'window.all' in s
    assert 'top-level `let`' in s
    assert 'match_over_under' in s
