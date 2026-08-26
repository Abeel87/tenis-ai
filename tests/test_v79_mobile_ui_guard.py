import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def test_adaptive_panel_has_mobile_overflow_guardrails():
    css = (ROOT / "frontend/adaptive-learning-v79.css").read_text(encoding="utf-8")
    compact = _compact(css)

    assert ".v79-live-panel*,.v79-health*{box-sizing:border-box;min-width:0}" in compact
    assert ".v79-live-panel,.v79-health{overflow:hidden}" in compact
    assert "overflow-wrap:anywhere" in css
    assert "word-break:break-word" in css
    assert ".v79-model-list" in css and "flex-wrap:wrap" in css
    assert "@media(max-width:560px)" in compact
    assert "@media(max-width:360px)" in compact
    assert ".v79-health-grid{grid-template-columns:1fr}" in compact
    assert ".v79-score-flowem{grid-column:1/-1" in compact


def test_adaptive_ui_uses_controlled_prod_contract_and_keeps_shadows_separate():
    ui = (ROOT / "frontend/adaptive-learning-v79.js").read_text(encoding="utf-8")

    # New production payload is preferred, but old snapshots remain readable.
    for token in (
        "adaptive_prod_v79",
        "ensemble_raw",
        "final_score",
        "learned_score",
        "adaptive_delta_pp",
        "cap_pp",
    ):
        assert token in ui

    for label in (
        "KONTROLOWANY PROD",
        "COLLECTING",
        "EARLY",
        "STRONG",
        "RAW",
        "PO ADAPTIVE",
        "Player SH",
        "Accuracy Lab",
        "SHADOW",
    ):
        assert label in ui

    assert 'class="v79-health-models"' in ui
    assert 'class="v79-model-list"' in ui
    assert 'v79-state-chip warn">SHADOW' not in ui

