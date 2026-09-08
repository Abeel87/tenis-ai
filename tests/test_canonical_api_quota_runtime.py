from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ACTIVE_PATHS = (
    ROOT / "backend" / "update.py",
    ROOT / "backend" / "pbp_enrich.py",
    ROOT / "backend" / "pbp_tracker.py",
    ROOT / "backend" / "live_history_settle.py",
    ROOT / "backend" / "history_backfill_v83.py",
    ROOT / ".github" / "workflows" / "update-and-pages.yml",
)


def test_active_runtime_uses_canonical_api_quota_only():
    for path in ACTIVE_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "api_quota_v83b" not in text, path
    workflow = (ROOT / ".github" / "workflows" / "update-and-pages.yml").read_text(
        encoding="utf-8"
    )
    assert "python backend/api_quota.py begin" in workflow
    assert "python backend/api_quota.py report" in workflow


def test_backfill_workflow_uses_same_canonical_policy_namespace():
    workflow = (ROOT / ".github" / "workflows" / "update-and-pages.yml").read_text(
        encoding="utf-8"
    )
    assert "API_QUOTA_HISTORY_BACKFILL_DAILY_FRACTION: '0.12'" in workflow
    assert "API_QUOTA_HISTORY_BACKFILL_RESERVE_FRACTION: '0.45'" in workflow
    assert "API_QUOTA_HISTORY_BACKFILL_RUN_CAP: '120'" in workflow
    lines = {line.strip() for line in workflow.splitlines()}
    assert not any(line.startswith("HISTORY_BACKFILL_DAILY_FRACTION:") for line in lines)
    assert not any(line.startswith("HISTORY_BACKFILL_HARD_RESERVE_FRACTION:") for line in lines)



def test_active_consumers_enforce_canonical_budget_and_provider_pacing():
    update = (ROOT / "backend" / "update.py").read_text(encoding="utf-8")
    tracker = (ROOT / "backend" / "pbp_tracker.py").read_text(encoding="utf-8")
    settle = (ROOT / "backend" / "live_history_settle.py").read_text(encoding="utf-8")

    assert "quota_budget('fixtures',12)" in update
    assert "request_interval_seconds(per_minute,utilization=0.90)" in update
    assert "quota-safe-skip" in update

    assert 'MAX_REMOTE_SETTLES_PER_RUN = 36' in tracker
    assert 'quota_budget("pbp_tracker", MAX_REMOTE_SETTLES_PER_RUN)' in tracker
    assert 'request_interval_seconds(per_minute,utilization=0.90)' in tracker

    assert 'MAX_CALLS_PER_RUN = 48' in settle
    assert 'quota_budget("history_settle", MAX_CALLS_PER_RUN)' in settle
    assert 'request_interval_seconds(per_minute, utilization=0.90)' in settle


def test_no_active_consumer_keeps_private_usage_owner():
    for rel in (
        "backend/pbp_tracker.py",
        "backend/live_history_settle.py",
        "backend/history_backfill_v83.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "def _usage_remaining" not in text, rel
        assert 'BASE_URL + "/usage"' not in text, rel
