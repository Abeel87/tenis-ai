"""Run the shipped publication steps against competing real Git producers."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest

from backend import readiness_engine_shadow as readiness
from scripts import publish_player_dna_reports as publisher

ROOT = Path(__file__).resolve().parents[1]
REPORTS = (
    'player_dna_point_dataset_summary.json', 'player_dna_profile_readiness.json',
    'player_dna_shadow_profile_summary.json', 'player_dna_point_scorer.json',
    'player_dna_current_shadow.json', 'player_dna_current_dynamic_shadow.json',
    'player_dna_current_simulation.json', 'player_dna_market_backtest.json',
    'player_dna_hold_calibration_audit.json', 'player_dna_hold_walk_forward.json',
    'player_dna_prospective_validation.json',
)


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def write(root, name, value):
    path = root / 'frontend/data' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return path.read_bytes()


def report(results, timestamp):
    return {
        'mode': readiness.MODE, 'status': readiness.STATUS, 'network_calls': 0,
        **{key: False for key in readiness.OBSERVABILITY_ISOLATION_FIELDS},
        'generated_at': timestamp,
        'source_snapshot': {
            'results_snapshot_contract': readiness.SNAPSHOT_CONTRACT,
            'results_snapshot_sha256': readiness.results_snapshot_sha256(results),
            'history_coverage_snapshot_aligned': True,
            'player_state_snapshot_aligned': True,
            'legacy_model_ready_reference_mismatches': 0,
        },
        'summary': {'matches': len(results), 'dimension_status_counts': {
            'identity': {'READY': len(results), 'NOT_READY': 0, 'UNKNOWN': 0}},
            'pbp_market_status_counts': {}},
    }


@pytest.fixture
def producers(tmp_path):
    remote = tmp_path / 'remote.git'
    git(tmp_path, 'init', '--bare', '--initial-branch=main', str(remote))
    source = tmp_path / 'source'
    git(tmp_path, 'clone', str(remote), str(source))
    git(source, 'config', 'user.name', 'test')
    git(source, 'config', 'user.email', 'test@example.invalid')
    results = [{'id': 101, 'model_ready': True}]
    write(source, 'results.json', results)
    write(source, 'readiness_engine_shadow.json', report(results, 'baseline'))
    write(source, 'meta.json', {'updated_at': 'original', 'foreign': 'original'})
    for name in REPORTS:
        write(source, name, {'generation': 'baseline'})
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'baseline')
    git(source, 'push', 'origin', 'main')
    worker = tmp_path / 'worker'
    git(tmp_path, 'clone', remote.as_uri(), str(worker))
    git(worker, 'config', 'user.name', 'test')
    git(worker, 'config', 'user.email', 'test@example.invalid')
    backend = worker / 'backend'
    backend.mkdir()
    for name in ('snapshot_digest.py', 'readiness_engine_shadow.py'):
        shutil.copyfile(ROOT / 'backend' / name, backend / name)
    publisher = ROOT / 'scripts/publish_player_dna_reports.py'
    if publisher.exists():
        (worker / 'scripts').mkdir()
        shutil.copyfile(publisher, worker / 'scripts' / publisher.name)
    return remote, source, worker, results


def run_step(worker, mode):
    name = ('Publish exact LOGIC-08 readiness before long backtests'
            if mode == 'readiness' else 'Publish Player DNA SHADOW reports')
    workflow = (ROOT / '.github/workflows/player-dna-shadow-refresh.yml').read_text()
    step = workflow.split('- name: ' + name, 1)[1].split('\n      - ', 1)[0]
    command = textwrap.dedent(step.split('run: |\n', 1)[1])
    output = worker / 'action-output'
    env = {**os.environ, 'GITHUB_OUTPUT': str(output),
           'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH']}
    result = subprocess.run(['bash', '-e', '-c', command], cwd=worker, env=env,
                            text=True, capture_output=True, timeout=30)
    return result, output.read_text() if output.exists() else ''


@pytest.mark.parametrize('mode', ['readiness', 'full'])
def test_concurrent_readiness_preserves_latest_metadata_and_exact_local_reports(producers, mode):
    remote, source, worker, results = producers
    local = report(results, 'new-local')
    exact = write(worker, 'readiness_engine_shadow.json', local)
    write(worker, 'meta.json', readiness.project_observability_meta(
        results, local, {'updated_at': 'original', 'foreign': 'original'}))
    own_reports = {name: write(worker, name, {'generation': 'local'}) for name in REPORTS}
    (worker / 'staged.txt').write_text('keep unrelated staged work local')
    git(worker, 'add', 'staged.txt')
    initial_index = (worker / '.git/index').read_bytes()
    initial_head = git(worker, 'rev-parse', 'HEAD')
    write(source, 'readiness_engine_shadow.json', report(results, 'parallel'))
    write(source, 'meta.json', {'updated_at': 'new-remote', 'foreign': 'keep',
                              'semantic_readiness_shadow': {'generated_at': 'parallel'}})
    (source / 'unrelated.txt').write_text('keep concurrent publisher')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'parallel readiness and other metadata')
    latest = git(source, 'rev-parse', 'HEAD')
    git(source, 'push', 'origin', 'main')
    result, output = run_step(worker, mode)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'changed=true' in output
    assert git(remote, 'merge-base', latest, 'main') == latest
    assert git(remote, 'show', 'main:unrelated.txt') == 'keep concurrent publisher'
    assert git(remote, 'show', 'main:frontend/data/readiness_engine_shadow.json') == exact.decode().strip()
    meta = json.loads(git(remote, 'show', 'main:frontend/data/meta.json'))
    assert meta['updated_at'] == 'new-remote'
    assert meta['foreign'] == 'keep'
    assert meta['semantic_readiness_shadow']['generated_at'] == 'new-local'
    assert git(worker, 'rev-parse', 'HEAD') == initial_head
    assert (worker / '.git/index').read_bytes() == initial_index
    assert 'staged.txt' not in git(remote, 'ls-tree', '--name-only', 'main')
    for name, content in own_reports.items():
        assert (worker / 'frontend/data' / name).read_bytes() == content
        published = json.loads(git(remote, 'show', 'main:frontend/data/' + name))
        assert published['generation'] == ('local' if mode == 'full' else 'baseline')


@pytest.mark.parametrize('mode', ['readiness', 'full'])
def test_newer_results_stop_publication_without_touching_main(producers, mode):
    remote, source, worker, results = producers
    write(source, 'results.json', [{'id': 202, 'model_ready': False}])
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'new results snapshot')
    git(source, 'push', 'origin', 'main')
    before = git(remote, 'rev-parse', 'main')
    result, output = run_step(worker, mode)
    assert result.returncode == 0, result.stderr
    assert 'stale=true' in output and 'changed=false' in output
    assert git(remote, 'rev-parse', 'main') == before


@pytest.mark.parametrize('change_results', [False, True])
def test_push_race_rechecks_snapshot_and_reprojects_latest_metadata(producers, monkeypatch, change_results):
    remote, source, worker, results = producers
    exact = write(worker, 'readiness_engine_shadow.json', report(results, 'captured-local'))
    real_git = publisher.git
    pushes = []

    def racing_git(root, *args, **kwargs):
        if args[0] == 'push':
            pushes.append(args)
            if len(pushes) == 1:
                write(source, 'meta.json', {'updated_at': 'racing-main', 'foreign': 'preserve'})
                if change_results:
                    write(source, 'results.json', [{'id': 202}])
                git(source, 'add', '.')
                git(source, 'commit', '-m', 'main advances after fetch')
                git(source, 'push', 'origin', 'main')
                # Subsequent attempts must keep the captured publication bytes.
                write(worker, 'readiness_engine_shadow.json', {'mutated': True})
        return real_git(root, *args, **kwargs)

    monkeypatch.setattr(publisher, 'git', racing_git)
    monkeypatch.setattr(publisher.time, 'sleep', lambda _: None)
    outcome = publisher.publish(worker, 'readiness')
    assert outcome['stale'] is change_results
    assert len(pushes) == (1 if change_results else 2)
    meta = json.loads(git(remote, 'show', 'main:frontend/data/meta.json'))
    assert meta['updated_at'] == 'racing-main' and meta['foreign'] == 'preserve'
    if not change_results:
        assert git(remote, 'show', 'main:frontend/data/readiness_engine_shadow.json') == exact.decode().strip()
        assert meta['semantic_readiness_shadow']['generated_at'] == 'captured-local'


def test_failed_push_is_bounded_and_preserves_worktree_index_and_main(producers, monkeypatch):
    remote, source, worker, results = producers
    staged = worker / 'staged.txt'
    staged.write_text('keep staged work')
    git(worker, 'add', 'staged.txt')
    before_index = (worker / '.git/index').read_bytes()
    before_head = git(worker, 'rev-parse', 'HEAD')
    before_main = git(remote, 'rev-parse', 'main')
    real_git = publisher.git
    calls = []

    def rejecting_git(root, *args, **kwargs):
        if args[0] == 'push':
            calls.append(args)
            raise subprocess.CalledProcessError(1, ['git', *args], stderr=b'rejected')
        return real_git(root, *args, **kwargs)

    monkeypatch.setattr(publisher, 'git', rejecting_git)
    monkeypatch.setattr(publisher.time, 'sleep', lambda _: None)
    with pytest.raises(subprocess.CalledProcessError):
        publisher.publish(worker, 'readiness')
    assert len(calls) == 3
    assert all(not any('force' in arg for arg in call) for call in calls)
    assert git(remote, 'rev-parse', 'main') == before_main
    assert git(worker, 'rev-parse', 'HEAD') == before_head
    assert (worker / '.git/index').read_bytes() == before_index
    assert staged.read_text() == 'keep staged work'


def test_identical_publication_does_not_create_another_commit(producers):
    remote, source, worker, results = producers
    first = publisher.publish(worker, 'readiness')
    second = publisher.publish(worker, 'readiness')
    assert first['changed'] is True
    assert second['changed'] is False and second['stale'] is False
    assert git(remote, 'rev-parse', 'main') == first['commit']


@pytest.mark.parametrize('invalid', ['snapshot', 'isolation', 'missing'])
def test_invalid_or_missing_report_cannot_publish(producers, invalid):
    remote, source, worker, results = producers
    value = report(results, 'invalid')
    if invalid == 'snapshot':
        value['source_snapshot']['results_snapshot_sha256'] = '0' * 64
    elif invalid == 'isolation':
        value['production_influence'] = True
    write(worker, 'readiness_engine_shadow.json', value)
    if invalid == 'missing':
        (worker / 'frontend/data/readiness_engine_shadow.json').unlink()
    before = git(remote, 'rev-parse', 'main')
    with pytest.raises((ValueError, FileNotFoundError)):
        publisher.publish(worker, 'readiness')
    assert git(remote, 'rev-parse', 'main') == before


def test_publication_fetch_does_not_download_unrelated_branches_or_tags(producers):
    remote, source, worker, results = producers
    git(source, 'switch', '-c', 'unrelated-archive')
    (source / 'archive').write_text('do not fetch')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'unrelated archive')
    unrelated = git(source, 'rev-parse', 'HEAD')
    git(source, 'tag', 'unrelated-tag')
    git(source, 'push', 'origin', 'unrelated-archive', '--tags')
    publisher.publish(worker, 'readiness')
    assert 'unrelated-archive' not in git(worker, 'branch', '-r')
    assert not git(worker, 'tag')
    assert subprocess.run(['git', 'cat-file', '-e', unrelated], cwd=worker,
                          stderr=subprocess.DEVNULL).returncode != 0
