from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "TENIS_AI_LEARNING_INTEGRITY_AUDIT.md"


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _function(text: str, name: str, next_name: str | None = None) -> str:
    start = text.index(f"def {name}(")
    if next_name:
        end = text.index(f"def {next_name}(", start)
        return text[start:end]
    return text[start:]


def test_phase0_audit_records_real_population_mismatch_and_no_behavior_authorization():
    audit = AUDIT.read_text(encoding="utf-8")
    for token in ("12162", "1532", "5397", "31159", "2276", "ALL", "PLAYABLE", "SELECTED"):
        assert token in audit
    assert "ZERO BEHAVIOR CHANGE" in audit
    assert "does not change behavior" in audit
    assert "must not enter a comparative winner/ranking metric" in audit

def test_current_history_owner_is_selected_green_not_all_predictions():
    text = _text("backend/history_tracker.py")
    assert "GREEN_THRESHOLD = 72.0" in text
    assert "Freeze every market that is visually green" in text
    archive = _function(text, "archive_predictions", "settle_history")
    assert "extract_green_signals" in archive
    assert "scheduled <= now + timedelta(minutes=cutoff_minutes)" in archive


def test_autolearn_freeze_is_prematch_but_does_not_own_downstream_selection_state():
    text = _text("backend/autolearn_v84.py")
    freeze = _function(text, "_capture_frozen", "tracking_stats")
    assert "autolearn_captured_at" in freeze
    assert '"model_scores"' in freeze
    assert '"generator_selected"' in freeze
    for forbidden in ("operator_playable", "symphony_selected", "ineed_selected", "placement_snapshot"):
        assert forbidden not in freeze


def test_tabpfn_is_intentionally_sparse_and_missing_scores_are_not_invented():
    text = _text("backend/autolearn_v84.py")
    assert "TABPFN_CURRENT_CAP = 300" in text
    assert "current_ranked = sorted" in text
    assert "tab_probs = [None] * len(current_rows)" in text
    assert "Ensure missing challenger probabilities do not dilute" in text

def test_telemetry_has_model_specific_availability_and_selected_scope():
    text = _text("backend/model_telemetry_v84c.py")
    assert "SELECT_THRESHOLD = 65.0" in text
    assert '"selected_n"' in text
    assert '"all_accuracy"' in text
    assert "autolearn_captured_at" in text


def test_playable_and_symphony_are_separate_exact_frozen_owners():
    playable = _text("backend/superbet_playable.py")
    freeze = _function(playable, "freeze_playable_history", "_filter_shadow_feed")
    assert '"playable_autolearn_signals_v912"' in freeze
    assert '"playable_captured_at_v912"' in freeze
    assert "signal_signature" in playable

    symphony = _text("backend/symphony2_tracker.py")
    capture = _function(symphony, "capture", "settle")
    assert '"captured_at"' in capture
    assert '"selection_id"' in capture
    assert "fixture_line_verified" in capture
    assert 'HISTORY = DATA / "symphony2_history.json"' in symphony

def test_ineed_shadow_selection_has_separate_fingerprint_and_placement_snapshot():
    money = _text("backend/ineed_money.py")
    edge = _text("supabase/functions/ineed-sync/index.ts")
    risk_sql = _text("supabase/migrations/20260910222554_ineed_v1_risk_guards.sql")
    assert "def _stable_fingerprint" in money
    assert '"snapshot": snapshot' in money
    assert '"timestamp": now.isoformat()' in money
    assert '"automatic_real_betting": False' in money
    assert 'current_snapshot: protectedStatus ? current.current_snapshot : (evaluation.snapshot || {})' in edge
    assert 'placement_snapshot)' in risk_sql
    assert 's.current_snapshot) returning * into bet_row' in risk_sql


def test_prediction_integrity_guard_is_not_a_historical_ledger_owner():
    text = _text("backend/prediction_integrity_v78a.py")
    assert 'RESULTS = OUT / "results.json"' in text
    assert "history.json" not in text
    assert "def validate(results)" in text


def test_future_common_set_contract_fails_closed_on_missing_or_misaligned_rows():
    audit = AUDIT.read_text(encoding="utf-8")
    required = (
        "same frozen match/candidate identity",
        "all compared model scores were frozen",
        "missing challenger score",
        "capture at/after start",
        "unresolved settlement",
        "different population label",
    )
    for phrase in required:
        assert phrase in audit
