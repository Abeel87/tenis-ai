from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "frontend" / "raw-playable-separation-v921.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-list-visibility-v916.js").read_text(encoding="utf-8")


def test_raw_layer_is_loaded_after_playable_gate():
    assert "raw-playable-separation-v921.js?v=921" in LOADER
    assert "script.addEventListener('load',loadRawPlayableV921" in LOADER
    assert "if(window.TENIS_AI_PLAYABLE_UI_V917){loadRawPlayableV921();return}" in LOADER


def test_match_cards_keep_model_raw_beside_superbet():
    assert "MODEL / RAW · analiza" in UI
    assert "Niezależne od Superbet" in UI
    assert "rawSignals(m,1)" in UI
    assert "SUPERBET — realne rynki i linie" in UI
    assert "canonical_selections" in UI


def test_match_detail_preserves_raw_lines_when_book_feed_is_missing():
    assert "Brak świeżej oferty Superbet — analiza MODEL / RAW nadal jest ważna." in UI
    assert "Modelowe sygnały i linie" in UI
    assert "Brak gotowych linii modelowych" in UI
    assert "window.TENIS_AI_PLAYABLE_UI_V917?.active?.(m)" in UI


def test_model_symphony_is_rendered_as_analysis_beside_playable():
    assert "symphony_match_cards_v90.json?raw=921" in UI
    assert "SYMFONIA MODELOWA · RAW" in UI
    assert "analiza niezależna od Superbet" in UI
    assert "play?play.before(sym):panel.after(sym)" in UI  # insert RAW panel beside guarded PLAYABLE panel


def test_basic_stats_iterate_every_tracked_model_and_keep_shadow_visible():
    assert "model_telemetry_v84c.json?raw=921" in UI
    assert "Object.keys(t.models||{}).map" in UI
    assert "Player Model + CatBoost" in UI
    assert "Ensemble + Player Learning" in UI
    assert "CatBoost + Player + Surface Elo" in UI
    assert "Ensemble + Player + Surface Elo" in UI
    assert "TabPFN + Surface Elo" in UI
    assert "Superbet PLAYABLE ma osobną próbkę" in UI


def test_ui_layer_does_not_poll_dom_or_change_model_math_contract():
    assert "MutationObserver" not in UI
    assert "setInterval" not in UI
    assert "production_influence" not in UI
    assert "selection_threshold" not in UI


def test_v921_javascript_syntax():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for JavaScript syntax check")
    subprocess.run(
        [node, "--check", "frontend/raw-playable-separation-v921.js"],
        cwd=ROOT,
        check=True,
    )
