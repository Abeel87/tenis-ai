from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

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
