from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_project_ui_assets():
    js=(ROOT/'frontend/project-ui.js').read_text(encoding='utf-8')
    css=(ROOT/'frontend/project-ui.css').read_text(encoding='utf-8')
    for x in ['Szybki werdykt','Szczegóły meczu','Top sygnały','Społeczność','Profil','openMatch','signalPage']:
        assert x in js
    assert '.p751-overlay' in css and '.p751-bottom-nav' in css
    assert not (ROOT/'frontend/ui-v751.js').exists()
    assert not (ROOT/'frontend/ui-v751.css').exists()


def test_project_ui_is_the_match_list_owner():
    js=(ROOT/'frontend/project-ui.js').read_text(encoding='utf-8')
    history=(ROOT/'frontend/history-ui.js').read_text(encoding='utf-8')
    assert 'renderMatches=function' in js
    assert 'window.TENIS_AI_PROJECT_UI' in js
    assert 'renderMatches=function' not in history
