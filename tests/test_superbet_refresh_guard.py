import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('guard', ROOT / '.github/scripts/superbet_refresh_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
NOW = datetime(2026, 9, 16, 22, tzinfo=timezone.utc)


def run(status='completed', conclusion='success', minutes=1, **extra):
    return dict(id=1, head_branch='main', event='schedule', status=status,
                conclusion=conclusion, updated_at=(NOW - timedelta(minutes=minutes)).isoformat(), **extra)


def jobs(start_minutes=2, publish='success'):
    return [{'conclusion': 'success', 'steps': [
        {'name': guard.WORK_STEP, 'conclusion': 'success',
         'started_at': (NOW - timedelta(minutes=start_minutes)).isoformat()},
        {'name': guard.PUBLISH_STEP, 'conclusion': publish},
    ]}]


@pytest.mark.parametrize('state', sorted(guard.ACTIVE))
def test_active_superbet_blocks_watchdog(state):
    assert guard.watchdog_block([run(state, None)], [], NOW) == 'refresh_already_active'


@pytest.mark.parametrize('state', sorted(guard.ACTIVE))
def test_active_full_blocks_watchdog(state):
    assert guard.watchdog_block([], [run(state, None)], NOW) == 'full_already_active'


def test_successful_full_has_bounded_propagation_grace():
    assert guard.watchdog_block([], [run(minutes=4)], NOW) == 'successful_full_propagation_grace'
    assert guard.watchdog_block([], [run(minutes=5)], NOW) is None


@pytest.mark.parametrize('conclusion', ['failure', 'cancelled'])
def test_unsuccessful_full_does_not_block_stale_fallback(conclusion):
    assert guard.watchdog_block([run(minutes=60)], [run(conclusion=conclusion)], NOW) is None
    assert not guard.completed_refresh(run(minutes=60), jobs(61), NOW)


def test_normal_stale_fallback_and_missing_history():
    assert guard.watchdog_block([], [], NOW) is None
    assert guard.watchdog_block([run(minutes=55)], [], NOW) is None
    assert not guard.completed_refresh(run(minutes=55), jobs(56), NOW)


def test_fresh_successful_refresh_after_full_suppresses_duplicate():
    full_finished = NOW - timedelta(minutes=3)
    assert guard.completed_refresh(run(), jobs(), NOW, after=full_finished)
    # A run queued before FULL can execute on new main after the concurrency wait.
    assert guard.completed_refresh(run(run_started_at=(NOW-timedelta(hours=1)).isoformat()),
                                   jobs(), NOW, after=full_finished)


def test_refresh_started_before_full_is_not_equivalent():
    assert not guard.completed_refresh(run(), jobs(10), NOW, after=NOW-timedelta(minutes=3))


@pytest.mark.parametrize('publish', ['skipped', 'failure'])
def test_noop_or_unpublished_refresh_does_not_renew_freshness(publish):
    assert not guard.completed_refresh(run(), jobs(publish=publish), NOW)
    assert not guard.completed_refresh(run(), [], NOW)


def test_pr_and_other_branch_are_not_production_evidence():
    for field, value in [('head_branch', 'feature'), ('event', 'pull_request')]:
        row = run(); row[field] = value
        assert not guard.completed_refresh(row, jobs(), NOW)
        row['status'] = 'in_progress'
        assert guard.watchdog_block([row], [row], NOW) is None


def test_workflow_gates_all_expensive_steps_and_retains_triggers():
    refresh = (ROOT / '.github/workflows/superbet-market-refresh.yml').read_text()
    watchdog = (ROOT / '.github/workflows/superbet-market-watchdog.yml').read_text()
    assert "cron: '5 * * * *'" in refresh
    assert "workflows: ['Update tennis data and deploy Pages']" in refresh
    assert "|| 'tennis-data-build'" in refresh
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in refresh
    assert refresh.index('superbet_refresh_guard.py refresh') < refresh.index('actions/setup-python')
    import re
    downstream = refresh[refresh.index('      - uses: actions/setup-python'):]
    for step in re.split(r'(?=^      - (?:name:|uses:))', downstream, flags=re.M):
        if step.strip():
            assert "if: steps.freshness.outputs.refresh == 'true'" in step
    assert 'superbet_refresh_guard.py watchdog' in watchdog
    assert 'gh workflow run "$TARGET_WORKFLOW"' in watchdog
    assert "if: steps.inspect.outputs.dispatch == 'true'" in watchdog


def test_cli_noop_and_stale_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'schedule')
    monkeypatch.setenv('GITHUB_OUTPUT', str(tmp_path / 'output'))
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(tmp_path / 'summary'))
    monkeypatch.setattr(guard, 'runs', lambda workflow: [])
    monkeypatch.setattr('sys.argv', ['guard', 'watchdog'])
    guard.main()
    assert 'dispatch=true' in (tmp_path / 'output').read_text()
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'pull_request')
    monkeypatch.setattr('sys.argv', ['guard', 'refresh'])
    guard.main()
    assert 'refresh=true' in (tmp_path / 'output').read_text()


def test_delayed_workflow_run_noop_before_runtime(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    full_finished = now - timedelta(minutes=3)
    source = tmp_path / 'event.json'
    import json
    source.write_text(json.dumps({'workflow_run': {
        'head_branch': 'main', 'conclusion': 'success',
        'updated_at': full_finished.isoformat(),
    }}))
    row = run()
    row['updated_at'] = (now - timedelta(minutes=1)).isoformat()
    evidence = jobs()
    evidence[0]['steps'][0]['started_at'] = (now - timedelta(minutes=2)).isoformat()
    monkeypatch.setattr(guard, 'runs', lambda workflow: [row])
    monkeypatch.setattr(guard, 'api', lambda path: {'jobs': evidence})
    monkeypatch.setattr('sys.argv', ['guard', 'refresh'])
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'workflow_run')
    monkeypatch.setenv('GITHUB_EVENT_PATH', str(source))
    monkeypatch.setenv('GITHUB_RUN_ID', '2')
    monkeypatch.setenv('GITHUB_OUTPUT', str(tmp_path / 'output'))
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(tmp_path / 'summary'))
    guard.main()
    assert 'refresh=false' in (tmp_path / 'output').read_text()
    assert 'fresh_completed_refresh_1' in (tmp_path / 'output').read_text()
    # A successful run whose costly step was skipped cannot perpetuate NO-OPs.
    evidence[0]['steps'][0]['conclusion'] = 'skipped'
    (tmp_path / 'output').write_text('')
    guard.main()
    assert 'refresh=true' in (tmp_path / 'output').read_text()


def test_guard_api_failure_stops_before_dispatch(monkeypatch, tmp_path):
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'schedule')
    monkeypatch.setattr('sys.argv', ['guard', 'watchdog'])
    def unavailable(workflow):
        raise RuntimeError('API unavailable')
    monkeypatch.setattr(guard, 'runs', unavailable)
    with pytest.raises(RuntimeError, match='API unavailable'):
        guard.main()
