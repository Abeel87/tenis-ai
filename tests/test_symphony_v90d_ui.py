from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_stats_loader_wires_symphony_assets_without_new_main_tab():
    ranking = read("frontend/stats-ranking-v886.js")
    html = read("frontend/index.html")
    assert "symphony-stats-v90d.css" in ranking
    assert "symphony-stats-v90d.js" in ranking
    assert "loadSymphonyStats" in ranking
    # Symphony performance lives inside existing Statystyki, not as another main tab.
    assert html.count('data-view="stats"') >= 1
    assert 'data-view="symphony-stats"' not in html


def test_stats_chart_has_2_to_6_leg_rows_and_sample_gates():
    js = read("frontend/symphony-stats-v90d.js")
    assert "[2, 3, 4, 5, 6]" in js
    assert "history_weight_ready" in js
    assert "próba ${n}/20" in js
    assert "pełna Symfonia" in js
    assert "pojedyncze nogi" in js
    assert "Brak danych = N/D" in js


def test_stats_chart_is_mobile_responsive():
    css = read("frontend/symphony-stats-v90d.css")
    assert "@media(max-width:900px)" in css
    assert "@media(max-width:600px)" in css
    assert ".symstats-chart__row" in css
    assert ".symstats-kpis" in css
