from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_central_quota_manager_is_wired_into_api_consumers():
    expected = {
        "backend/update.py": "record_calls('fixtures',1)",
        "backend/pbp_enrich.py": 'quota_budget("pbp_current", RUN_CALL_CAP)',
        "backend/pbp_tracker.py": 'quota_budget("pbp_tracker", MAX_REMOTE_SETTLES_PER_RUN)',
        "backend/live_history_settle.py": 'quota_budget("history_settle", MAX_CALLS_PER_RUN)',
        "backend/history_backfill_v83.py": 'quota_budget("history_backfill", run_cap)',
    }
    for rel, marker in expected.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert marker in text, f"missing v8.3B quota wiring in {rel}"


def test_fixture_ids_are_forwarded_to_pbp_to_avoid_detail_calls():
    text = (ROOT / "backend" / "update.py").read_text(encoding="utf-8")
    assert "'p1_id':p1o.get('id')" in text
    assert "'p2_id':p2o.get('id')" in text


def test_workflow_starts_guard_before_current_match_update():
    text = (ROOT / ".github" / "workflows" / "update-and-pages.yml").read_text(encoding="utf-8")
    begin = text.index("Central API Quota Guard v8.3B")
    update = text.index("- name: Update analysis")
    backfill = text.index("Historical backfill v8.3B")
    assert begin < update < backfill
