from backend.adaptive_learning_v79 import (
    build_cells, adjust_score, explain_signal, collect_training_rows
)

def _row(hit, raw=0.80, source="adaptive", market="set1_total", key="set1_total|8.5|over", weight=1.0):
    return {
        "source_model": source, "market": market, "key": key,
        "tour": "ATP", "surface": "hard", "band": "80-89",
        "raw": raw, "hit": float(hit), "weight": weight,
    }

def test_small_sample_does_not_move_score():
    cells = build_cells([_row(0) for _ in range(3)])
    sig = {"market":"set1_total","line":8.5,"pick":"over","score":80}
    got = adjust_score(80, "adaptive", sig, cells, "ATP", "hard")
    assert abs(got["delta"]) < 0.1
    assert got["evidence"] == "COLLECTING"

def test_repeated_misses_lower_score():
    rows = [_row(1) for _ in range(5)] + [_row(0) for _ in range(15)]
    cells = build_cells(rows)
    sig = {"market":"set1_total","line":8.5,"pick":"over","score":80}
    got = adjust_score(80, "adaptive", sig, cells, "ATP", "hard")
    assert got["learned_score"] < 80
    assert got["action"] == "downgrade"

def test_repeated_hits_raise_conservative_score():
    rows = [_row(1, raw=.65, key="set1_total|8.5|over") for _ in range(18)] + [
        _row(0, raw=.65, key="set1_total|8.5|over") for _ in range(2)
    ]
    cells = build_cells(rows)
    sig = {"market":"set1_total","line":8.5,"pick":"over","score":65}
    got = adjust_score(65, "adaptive", sig, cells, "ATP", "hard")
    assert got["learned_score"] > 65
    assert got["learned_score"] < 90

def test_explanation_is_factual_for_set_total():
    entry = {
        "p1":"A", "p2":"B",
        "result":{"sets":[[6,2],[6,4]], "winner":"A", "score_text":"6-2 6-4"}
    }
    sig={"market":"set1_total","line":8.5,"pick":"over","result":"miss"}
    text=explain_signal(entry,sig)
    assert "6:2" in text and "8 gemów" in text

def test_pbp_uses_confidence_as_training_score():
    pbp=[{
        "status":"settled","tour":"ATP","surface":"hard",
        "signals":[{"market":"lead_after6","pick":"A","prob":.72,"confidence":.72,"result":"miss"}]
    }]
    rows=collect_training_rows([],pbp)
    assert len(rows)==1
    assert round(rows[0]["raw"],2)==.72
    assert rows[0]["source_model"]=="early_hold_pbp"
