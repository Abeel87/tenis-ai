from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_readability_features_live_in_canonical_project_ui():
    ui=(ROOT/'frontend/project-ui.js').read_text(encoding='utf-8')
    css=(ROOT/'frontend/project-readability.css').read_text(encoding='utf-8')
    idx=(ROOT/'frontend/index.html').read_text(encoding='utf-8')

    assert 'function matchGamesPreview' in ui
    assert 'match_over_under' in ui
    assert 'p753-match-total-preview' in ui
    assert 'font-size:18px' in css
    assert 'href="project-readability.css"' in idx

    for retired in ('readability-v753.js','readability-v753.css','ui-v751.js'):
        assert retired not in idx
        assert not (ROOT/'frontend'/retired).exists()
