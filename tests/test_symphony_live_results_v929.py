from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYMPHONY = ROOT / "frontend" / "symphony-v90.js"


def test_symphony_refreshes_current_results_before_actionable_render():
    src = SYMPHONY.read_text(encoding="utf-8")
    assert "const RESULTS_URL = './data/results.json';" in src
    assert "refreshCurrentResults(true), loadData(true)" in src
    assert "window.TENIS_AI_FAST_BOOT_V888?.clear?.();" in src
    assert "all = rows;" in src
    assert "Nie pokazuję starej kompozycji" in src


def test_generate_revalidates_results_and_symphony_report():
    src = SYMPHONY.read_text(encoding="utf-8")
    assert "await refreshCurrentResults(true);" in src
    assert "const latest = await loadData(true);" in src
    assert "resultsHtml(latest, matchCount, legs, variant)" in src
