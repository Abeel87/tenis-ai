from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_project_ui_assets():
    js=(ROOT/'frontend/project-ui.js').read_text(encoding='utf-8')
    css=(ROOT/'frontend/style.css').read_text(encoding='utf-8')
    for x in ['Najlepszy typ','Analiza meczu','Top sygnały','openMatch','signalPage']:
        assert x in js
    assert '.match-page' in css and '.main-tabs' in css
    assert 'p751-match-overlay' not in js
    assert 'p751-bottom-nav' not in js
    assert not (ROOT/'frontend/project-ui.css').exists()
    assert not (ROOT/'frontend/ui-v751.js').exists()
    assert not (ROOT/'frontend/ui-v751.css').exists()


def test_project_ui_is_the_match_list_owner():
    js=(ROOT/'frontend/project-ui.js').read_text(encoding='utf-8')
    history=(ROOT/'frontend/history-ui.js').read_text(encoding='utf-8')
    assert 'renderMatches=function' in js
    assert 'window.TENIS_AI_PROJECT_UI' in js
    assert 'renderMatches=function' not in history
