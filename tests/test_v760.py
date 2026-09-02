from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_frontend_has_pro_sections():
    s=(ROOT/'frontend/player-analytics.js').read_text(encoding='utf-8')
    for x in ['Player Analytics PRO','SERWIS','RETURN','FORMA','EARLY','MENTAL','NAWIERZCHNIA','Nie są prawdopodobieństwem']:
        assert x in s
