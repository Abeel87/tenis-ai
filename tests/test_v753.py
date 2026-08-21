from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_assets():
    js=(ROOT/'frontend/readability-v753.js').read_text(encoding='utf-8')
    css=(ROOT/'frontend/readability-v753.css').read_text(encoding='utf-8')
    assert 'Liczba gemów · cały mecz' in js
    assert 'match_over_under' in js
    assert 'p753-match-total-preview' in js
    assert 'font-size:18px' in css
def test_installer():
    s=(ROOT/'install_v753.py').read_text(encoding='utf-8')
    assert 'readability-v753.css' in s and 'readability-v753.js' in s
