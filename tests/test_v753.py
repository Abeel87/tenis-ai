from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_v753_features_migrated_to_current_ui():
    ui=(ROOT/'frontend/ui-detail.js').read_text(encoding='utf-8')
    css=(ROOT/'frontend/readability.css').read_text(encoding='utf-8')
    idx=(ROOT/'frontend/index.html').read_text(encoding='utf-8')

    # Whole-match totals still exist, but are now owned by current UI.
    assert 'function matchGamesPreview' in ui
    assert 'match_over_under' in ui
    assert 'p753-match-total-preview' in ui

    # Readability CSS remains useful for current p753 classes.
    assert 'font-size:18px' in css

    # The obsolete polling JS layer must stay retired.
    assert 'readability-v753.js' not in idx
    assert not (ROOT/'frontend/readability-v753.js').exists()
