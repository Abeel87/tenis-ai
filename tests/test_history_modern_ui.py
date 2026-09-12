from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HISTORY_MARKER = "/* History: canonical new-shell presentation, scoped and read-only. */"


def _history_css():
    css = (ROOT / "frontend" / "style.css").read_text(encoding="utf-8")
    assert HISTORY_MARKER in css
    return css.split(HISTORY_MARKER, 1)[1]


def test_history_modern_styles_are_in_canonical_stylesheet_and_scoped():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = _history_css()

    assert index.count('rel="stylesheet"') == 1
    assert 'href="style.css"' in index
    assert 'history-modern.css' not in index
    assert not (ROOT / "frontend" / "history-modern.css").exists()
    assert "[data-rich-history-root]" in css
    assert ".history-day" in css
    assert ".history-match" in css
    assert ".history-match .event" in css
    assert "!important" not in css


def test_history_modern_styles_do_not_change_model_sources():
    css = _history_css()
    forbidden = ("probability", "settlement", "playable_signals", "autolearn_signals", "symphony2_history.json")
    assert not any(token in css for token in forbidden)
