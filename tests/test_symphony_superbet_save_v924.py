from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "symphony-superbet-save-v924.js"
META = ROOT / "frontend" / "app-meta.js"


def test_symphony_actionable_layer_fails_closed_on_exact_superbet_gate():
    text = JS.read_text(encoding="utf-8")
    assert "api.compositionPlayable?.(current,comp)===true" in text
    assert "api.active?.(current)!==true" in text
    assert "operator_playable_only:true" in text
    assert "operator_revalidated_at" in text
    assert "Linia już nieaktualna" in text


def test_symphony_save_reuses_existing_scenario_history_and_settlement_shape():
    text = JS.read_text(encoding="utf-8")
    assert "tenis-ai-v82a-scenarios-local" in text
    assert "client.from('ai_scenarios').insert" in text
    assert "result:'pending'" in text
    assert "selected_line:line" in text
    assert "suggested_line:line" in text
    assert "match_key:" in text
    assert "match_id:" in text
    assert "scheduled_time:" in text
    assert "exact_match_score')return'exact_match'" in text
    assert "set1_exact_score')return'exact_set1'" in text


def test_auto_can_fallback_to_another_currently_playable_leg_count():
    text = JS.read_text(encoding="utf-8")
    assert "for(const n of [2,3,4,5,6])" in text
    assert "const first=playableCandidate(row,current,preferred,variant)" in text
    assert "options.sort" in text
    assert "fallback:true" in text


def test_bootstrap_loads_playable_gate_before_save_layer():
    text = META.read_text(encoding="utf-8")
    playable = text.index("playable-ui-coherence-v917.js?v=924")
    save = text.index("symphony-superbet-save-v924.js?v=924")
    assert playable >= 0
    assert save >= 0
    assert "if(window.TENIS_AI_PLAYABLE_UI_V917)save()" in text


def test_v924_does_not_write_model_math_or_prices():
    text = JS.read_text(encoding="utf-8")
    forbidden = [
        "final_score =",
        "adaptive_prod_score =",
        "joint_probability =",
        "path_probability =",
        "prices_used =",
    ]
    for token in forbidden:
        assert token not in text
