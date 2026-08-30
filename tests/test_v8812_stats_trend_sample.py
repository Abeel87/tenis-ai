from pathlib import Path


def test_latest_trend_sample_is_visible_without_changing_math():
    src = Path("frontend/stats-ranking-v886.js").read_text(encoding="utf-8")

    assert "patchTrendSampleContext" in src
    assert "circle title" in src
    assert "n=(\\d+)" in src
    assert "data-v886-trend-sample" in src
    assert "BARDZO MAŁA PRÓBA" in src
    assert "MAŁA PRÓBA" in src
    assert "pojedynczy skok nie oznacza jeszcze trwałej poprawy modelu" in src

    # UI-only audit fix: no new data request and no writes to model/stat source fields.
    patch = src[src.index("function patchTrendSampleContext"):src.index("function promoteMainTrend")]
    assert "fetch(" not in patch
    assert "historyRows" not in patch
    assert "statsData" not in patch
    assert "score=" not in patch
    assert "probability=" not in patch
    assert "weight=" not in patch
