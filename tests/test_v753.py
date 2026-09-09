from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_readability_features_live_in_canonical_project_ui():
    ui=(ROOT/'frontend/project-ui.js').read_text(encoding='utf-8')
    css=(ROOT/'frontend/style.css').read_text(encoding='utf-8')
    idx=(ROOT/'frontend/index.html').read_text(encoding='utf-8')

    for token in ('matchGamesPreview','matchGamesLines','Najlepszy typ','match-tile-score','match-page'):
        assert token in ui
    assert '.match-tile' in css
    assert '.match-page' in css
    assert 'href="style.css"' in idx
    assert not (ROOT/'frontend/project-readability.css').exists()

    for retired in ('readability-v753.js','readability-v753.css','ui-v751.js'):
        assert retired not in idx
        assert not (ROOT/'frontend'/retired).exists()
