from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_files_exist():
    assert (ROOT/'frontend/ui-v75.js').exists()
    assert (ROOT/'frontend/ui-v75.css').exists()
def test_key_sections_present():
    s=(ROOT/'frontend/ui-v75.js').read_text(encoding='utf-8')
    for x in ['Szybki werdykt','Typy meczowe','Statystyki zawodników','Early Hold · PBP','Asy i podwójne błędy','Market Lab','renderHistory=function','renderMatches=function']:
        assert x in s
