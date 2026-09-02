from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_early_hold_paths_use_stable_presentation_assets():
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND / "early-hold-paths.js").read_text(encoding="utf-8")
    assert (FRONTEND / "early-hold-paths.css").is_file()
    assert 'src="early-hold-paths.js"' in index
    assert 'href="early-hold-paths.css"' in index
    assert not (FRONTEND / "early-hold-paths-v771.js").exists()
    assert not (FRONTEND / "early-hold-paths-v771.css").exists()
    assert "window.TENIS_AI_EARLY_HOLD_PATHS_V81" in js
    assert "early_hold_v7" in js
    assert "decoratePlayerProfile" in js
    assert "decorateOverlay" in js


def test_early_hold_model_generation_remains_separate():
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert (FRONTEND / "early-hold-v7.js").is_file()
    assert 'src="early-hold-v7.js"' in index
