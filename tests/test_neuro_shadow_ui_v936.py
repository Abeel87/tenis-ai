from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_neuro_ui_is_lazy_loaded_and_shadow_labeled():
    meta = (ROOT / "frontend" / "app-meta.js").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "neuro-shadow.js").read_text(encoding="utf-8")
    assert "neuro-shadow.css" in meta
    assert "neuro-shadow.js" in meta
    assert "neuro-shadow-v936.css" not in meta
    assert "neuro-shadow-v936.js" not in meta
    assert "Neural Meta Model" in js
    assert "SHADOW" in js
    assert "data-p751-nav='neuro'" not in js  # dynamic assignment, not brittle HTML override
    assert "btn.dataset.p751Nav='neuro'" in js
    assert "operator_playable" not in js or "PLAYABLE" in js


def test_neuro_nav_is_placed_next_to_symphony_and_brain_targets_superbet_panel():
    js = (ROOT / "frontend" / "neuro-shadow.js").read_text(encoding="utf-8")
    assert "data-p751-nav=\"symphony2\"" in js
    assert "insertAdjacentElement('afterend',btn)" in js
    assert ".sbmc922-panel .sbmc922-head" in js
    assert "neuro936-brain" in js


def test_neuro_ui_never_formats_missing_neural_probability_as_a_number():
    js = (ROOT / "frontend" / "neuro-shadow.js").read_text(encoding="utf-8")
    assert "row.neural_probability==null" in js
    assert "NEURO ${pct(row.neural_probability)}" in js


def test_neuro_ui_never_shows_ready_from_incompatible_training_artifact():
    js = (ROOT / "frontend" / "neuro-shadow.js").read_text(encoding="utf-8")
    assert "c.training_artifact_compatible!==false" in js
    assert "compatible&&r.status==='SHADOW_MODEL_READY'" in js
    assert "STALE ARTIFACT" in js
    assert "STALE_MODEL_ARTIFACT" in js


def test_neuro_ui_preserves_zero_match_identity():
    js = (ROOT / "frontend" / "neuro-shadow.js").read_text(encoding="utf-8")
    assert "String(v??'')" in js
    assert "normalizeId(m.match_id)===id" in js
    assert "m.match_id||''" not in js


def test_neuro_ui_exports_canonical_runtime_only():
    js = (ROOT / "frontend" / "neuro-shadow.js").read_text(encoding="utf-8")
    assert "TENIS_AI_NEURO_SHADOW=Object.freeze" in js
    assert "TENIS_AI_NEURO_SHADOW_V936" not in js
