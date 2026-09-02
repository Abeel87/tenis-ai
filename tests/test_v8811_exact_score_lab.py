from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_exact_score_is_visible_but_explicitly_lab_only():
    js = read("frontend/market-quality.js")
    assert "EXACT_LAB_VERSION='v8.8.11'" in js
    assert "installExactScoreLabLabels" in js
    assert "window.exactSet=match=>" in js
    assert "window.exactMatch=match=>" in js
    assert "MODEL LAB" in js
    assert "brak osobnej telemetrii FINAL" in js
    assert "Nie wchodzi do CORE" in js
    assert "TENIS_AI_EXACT_SCORE_LAB_V8811" in js


def test_exact_score_lab_change_is_presentation_only():
    js = read("frontend/market-quality.js")
    assert "Selection/presentation only" in js
    assert "match.exact_first_set" in js
    assert "match.exact_match_score" in js
    assert "m[\"exact_first_set\"]=" not in js
    assert "m[\"exact_match_score\"]=" not in js
