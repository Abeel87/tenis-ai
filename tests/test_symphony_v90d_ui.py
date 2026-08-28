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
    assert 'symphony-stats-v90d.css?v=90d2' in html
    assert 'symphony-stats-v90d.js?v=90d2' in html
    assert 'symphony-surface-v90.js?v=90e1' in html
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
    assert "v !== null" in js


def test_stats_chart_is_mobile_responsive_and_pro_can_close():
    css = read("frontend/symphony-stats-v90d.css")
    assert "@media(max-width:900px)" in css
    assert "@media(max-width:600px)" in css
    assert ".symstats-chart__row" in css
    assert ".symstats-kpis" in css
    assert ".pc12-pro:not([open])>.pc12-pro-body{display:none!important}" in css
    assert ".pc12-pro[open]>.pc12-pro-body{display:grid!important}" in css


def test_late_surface_restores_stats_and_decorates_match_cards_and_detail():
    js = read("frontend/symphony-surface-v90.js")
    css = read("frontend/symphony-surface-v90.css")
    generator = read("scripts/compact_frontend_data_v853.py")
    assert "card.parentElement !== root" in js
    assert "pc882-dash" in js
    assert "symphony-performance-v90d" in js
    assert "symphony_match_cards_v90.json" in js
    assert "recommended_leg_count" in js
    assert "row?.composition" in js
    assert "symphony_score" in js
    assert "/100" in js
    assert ".p751-match-card[data-p751-open]" in js
    assert "data-symphony-match-mini" in js
    assert "symphony_v90.json" in js
    assert "fullComposition" in js
    assert "[6, 5, 4, 3, 2]" in js
    assert "decorateOpenMatch" in js
    assert "#p751-match-overlay:not([hidden])" in js
    assert "data-symphony-match-detail" in js
    assert "PEŁNA SYMFONIA" in js
    assert "Najbardziej krucha noga" in js
    assert "symphony_match_cards_v90.json" in generator
    assert "build_symphony_match_cards" in generator
    assert "recommended_leg_count" in generator
    assert "_card_leg" in generator
    assert ".symmatch-mini" in css
    assert ".symmatch-detail__legs" in css
    assert ".symmatch-detail__metrics" in css
    assert "@media(max-width:520px)" in css
