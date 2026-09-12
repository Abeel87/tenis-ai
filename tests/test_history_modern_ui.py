from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_history_modern_styles_are_loaded_and_scoped():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "history-modern.css").read_text(encoding="utf-8")

    assert 'href="history-modern.css"' in index
    assert "[data-rich-history-root]" in css
    assert ".history-day" in css
    assert ".history-match" in css
    assert ".history-match .event" in css
    assert "!important" not in css


def test_history_modern_styles_do_not_change_model_sources():
    css = (ROOT / "frontend" / "history-modern.css").read_text(encoding="utf-8")
    forbidden = ("probability", "settlement", "playable_signals", "autolearn_signals", "symphony2_history.json")
    assert not any(token in css for token in forbidden)
