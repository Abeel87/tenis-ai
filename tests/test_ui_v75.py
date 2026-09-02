from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_history_ui_assets_exist():
    assert (ROOT/'frontend/history-ui.js').exists()
    assert (ROOT/'frontend/history-ui.css').exists()
    assert not (ROOT/'frontend/ui-v75.js').exists()
    assert not (ROOT/'frontend/ui-v75.css').exists()


def test_history_ui_owns_history_only():
    s=(ROOT/'frontend/history-ui.js').read_text(encoding='utf-8')
    for x in ['Historia jest jeszcze pusta.','Rozliczone ✓','Specjalne !','window.renderHistory=render']:
        assert x in s
    assert 'renderMatches=function' not in s
    assert 'Top sygnały' not in s
    assert 'filteredReady' not in s
