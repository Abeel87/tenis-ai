from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_ui_assets():
    js=(ROOT/'frontend/ui-v751.js').read_text(encoding='utf-8')
    css=(ROOT/'frontend/ui-v751.css').read_text(encoding='utf-8')
    for x in ['Szybki werdykt','Szczegóły meczu','Top sygnały','Społeczność','Profil','openMatch','signalPage']:
        assert x in js
    assert '.p751-overlay' in css and '.p751-bottom-nav' in css
def test_installer():
    s=(ROOT/'install_v751.py').read_text(encoding='utf-8')
    assert 'ui-v751.css' in s and 'ui-v751.js' in s and 'tenis-ai-v751-project-ui' in s
