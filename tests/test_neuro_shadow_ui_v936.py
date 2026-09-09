from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_neuro_ui_is_lazy_loaded_through_clean_shell_and_shadow_labeled():
    meta = (ROOT / "frontend" / "app-meta.js").read_text(encoding="utf-8")
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    style = (ROOT / "frontend" / "style.css").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "neuro-shadow.js").read_text(encoding="utf-8")

    assert "neuro-shadow.js" in meta
    assert "neuro-shadow.css" not in meta
    assert "loadStyle(" not in meta
    assert not (ROOT / "frontend" / "neuro-shadow.css").exists()
    assert ".neuro936-hub" in style

    assert 'id="neuro-open"' in index
    assert 'phase11-technical' in index
    assert "Neural Meta Model" in js
    assert "SHADOW" in js
    assert "#p751-bottom-nav" not in js
    assert "#p751-match-overlay" not in js
    assert "operator_playable" not in js or "PLAYABLE" in js


def test_neuro_uses_clean_topbar_and_in_app_match_root():
    js = (ROOT / "frontend" / "neuro-shadow.js").read_text(encoding="utf-8")
    assert "document.querySelector('#neuro-open')" in js
    assert "button.closest('#app[data-match-key]')" in js
    assert ".sbmc922-panel .sbmc922-head" in js
    assert "neuro936-brain phase11-technical" in js
    assert "observer.observe(app,{subtree:true,childList:true})" in js
    assert "observer.observe(document.documentElement" not in js


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
    assert "bindTrigger" in js
    assert "bindNav" not in js
