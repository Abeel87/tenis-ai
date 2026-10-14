from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_full_data_jobs_have_memory_headroom_and_live_diagnostics():
    for name, command in (
        ('player-dna-shadow-refresh.yml', 'player_dna_market_backtest.py'),
        ('point-tape-audit.yml', 'player_dna_opponent_adjustment_audit.py'),
    ):
        workflow = (ROOT / '.github/workflows' / name).read_text()
        assert workflow.index('sudo swapon /mnt/tenis-ai-validation.swap') < workflow.index('run: pip install')
        assert 'sudo chmod 600 /mnt/tenis-ai-validation.swap' in workflow
        assert f'/usr/bin/time -v python backend/{command} &' in workflow
        assert 'wait "$worker"' in workflow  # propagate validation failure
        assert 'while kill -0 "$worker"' in workflow
        assert "trap 'kill" in workflow
        for variable in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            assert f"{variable}: '1'" in workflow

def test_long_dna_run_is_not_cancelled_by_new_core_and_workers_are_bounded():
    workflow = (ROOT / '.github/workflows/player-dna-shadow-refresh.yml').read_text()
    cancel = next(line for line in workflow.splitlines() if 'cancel-in-progress:' in line)
    assert "github.event_name == 'pull_request'" in cancel
    assert "Superbet hourly market refresh" in cancel
    assert 'Update tennis data and deploy Pages' not in cancel
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        assert f"{name}: '1'" in workflow

def test_core_recovery_uses_snapshot_age_and_suppresses_active_work():
    workflow = (ROOT / '.github/workflows/tennis-data-stale-run-guard.yml').read_text()
    recovery = workflow.split('- name: Recover stale core snapshot')[1].split('- name: Ensure iNeed$')[0]
    assert 'contents/frontend/data/meta.json?ref=main' in recovery
    assert '.updated_at' in recovery
    assert '.status != "completed"' in recovery
    assert recovery.index('exit 0') < recovery.index('gh workflow run update-and-pages.yml')
    assert 'CORE_MAX_AGE_MINUTES' in recovery
    assert "github.event.workflow_run.head_branch == 'main'" in workflow
    assert 'cancel-in-progress: false' in workflow
