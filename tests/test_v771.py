from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_frontend_scope_and_paths():
    s=(ROOT/"frontend/early-hold-paths.js").read_text(encoding="utf-8")
    for x in [
        "DANE ZAWODNIKA",
        "PORÓWNANIE MECZU",
        "HOLD–HOLD",
        "BREAK–BREAK",
        "CZYSTYCH HOLDÓW",
        "oba warianty po 50%",
    ]:
        assert x in s

def test_math_example():
    ha,hb=.80,.75
    clean=ha*hb
    breaks=(1-ha)*(1-hb)
    total=clean+breaks
    assert round(clean*100,1)==60.0
    assert round(breaks*100,1)==5.0
    assert round(total*100,1)==65.0
