from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_registration_script_query_is_valid():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "registration-ux-v752.js" not in html
    assert 'src="registration-ux.js"' in html


def test_primary_boot_does_not_fetch_heavy_history_payload():
    js = (ROOT / "frontend/app.js").read_text(encoding="utf-8")
    primary = js.split("async function load(){", 1)[1].split("document.querySelectorAll('#tour-nav", 1)[0]
    assert "Promise.all([safeJson('data/results.json',[]),safeJson('data/meta.json',{})])" in primary
    assert "if(view==='stats'||view==='history')await loadSecondaryData()" in primary
    secondary = js.split("async function loadSecondaryData", 1)[1].split("async function load(){", 1)[0]
    assert "data/history.json" in secondary
    assert "data/history_stats.json" in secondary
