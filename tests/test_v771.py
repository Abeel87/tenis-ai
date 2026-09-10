from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def test_math_example():
    ha,hb=.80,.75
    clean=ha*hb
    breaks=(1-ha)*(1-hb)
    total=clean+breaks
    assert round(clean*100,1)==60.0
    assert round(breaks*100,1)==5.0
    assert round(total*100,1)==65.0
