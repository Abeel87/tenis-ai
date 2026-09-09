from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_live_recovery_layer_is_bootstrapped():
    meta = (ROOT / "frontend" / "app-meta.js").read_text(encoding="utf-8")
    assert "symphony2-live-ui.js" in meta
    assert "symphony2-live-ui-v201.js" not in meta


def test_live_recovery_exposes_symphony_on_match_cards_and_details():
    js = (ROOT / "frontend" / "symphony2-live-ui.js").read_text(encoding="utf-8")
    assert "SYMFONIA 2.0" in js
    assert "data-s2-live-card" in js
    assert "#app[data-match-key]" in js
    assert "#p751-match-overlay" not in js
    assert "TENIS_AI_SYMPHONY2.renderMatchDetail" in js
    assert "data-p751-open" in js


def test_symphony_live_ui_no_longer_owns_scenario_runtime():
    js = (ROOT / "frontend" / "symphony2-live-ui.js").read_text(encoding="utf-8")
    assert "MutationObserver" not in js
    assert "data-sc-generate" not in js
    assert "TENIS_AI_GENERATOR_QUALITY_V888" not in js
    assert "TENIS_AI_SCENARIOS" not in js


def test_sym2_feed_parser_rejects_empty_or_invalid_payloads():
    js = (ROOT / "frontend" / "symphony2-live-ui.js").read_text(encoding="utf-8")
    assert "Symphony2 empty feed" in js
    assert "Symphony2 invalid feed" in js
    assert "JSON.parse(text)" in js


def test_live_ui_uses_only_recommended_final_playable_composition():
    js = (ROOT / "frontend" / "symphony2-live-ui.js").read_text(encoding="utf-8")
    assert "recommended_leg_count" in js
    assert "layer.final_playable_authority!==true" in js
    assert "layer.playable!==true" in js
    assert "published!==recommended" in js
    assert "api.compositionPlayable(match,comp)!==true" in js
    assert "projected.length!==legs.length" in js
    assert "Object.keys(row.compositions||{})" not in js
    assert "for(const n of keys)" not in js


def test_live_ui_expires_stale_snapshot_exactly_at_scheduled_start():
    js = (ROOT / "frontend" / "symphony2-live-ui.js").read_text(encoding="utf-8")
    assert "function rowPreMatch(row,match=null,now=Date.now())" in js
    assert "scheduled<=Number(now)" in js
    assert "TENIS_AI_PLAYABLE_UI_V917" in js
    assert "api.active(match,now)!==true" in js
    assert "if(!rowPreMatch(row,match))return ''" in js
    assert "SYMFONIA 2.0 · NIEAKTYWNA" in js
    assert "Snapshot pre-match lub oferta operatora wygasła" in js
    assert "Dane MODEL/RAW pozostają bez zmian." in js



def test_live_symphony_no_composition_state_is_not_labeled_playable():
    js = (ROOT / "frontend" / "symphony2-live-ui.js").read_text(encoding="utf-8")
    assert "SYMFONIA 2.0 · BRAK PLAYABLE" in js
    assert "SYMFONIA 2.0 · PLAYABLE</small><h3>Brak kompozycji" not in js


def test_live_playable_requires_current_results_authority_and_matching_feed_generation():
    js = (ROOT / "frontend" / "symphony2-live-ui.js").read_text(encoding="utf-8")
    assert "match?.symphony2_playable" in js
    assert "String(layer.source_generated_at||'')!==String(data.generated_at)" in js
    assert "api.playableSignals?.(match,100)" in js
