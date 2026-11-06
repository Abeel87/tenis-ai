"""Pages may omit raw research only after its complete archive is verified."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest

from scripts.runtime_snapshot import pack, verify


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / '.github/actions/prepare-pages/action.yml'
STEP = 'Exclude verified archived research ledgers from Pages'
LEDGERS = (
    'prediction_ledger_shadow.json',
    'prediction_ledger_selection_shadow.json',
    'prediction_ledger_settlement_shadow.json',
)


@pytest.fixture
def publication(tmp_path):
    data = tmp_path / 'frontend/data'
    data.mkdir(parents=True)
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    shutil.copyfile(ROOT / 'scripts/runtime_snapshot.py', scripts / 'runtime_snapshot.py')
    original = {name: json.dumps({'rows': [{'p': 0.1234567890123456,
        'id': name, 'missing': None, 'zero': 0, 'flag': False}]}).encode() for name in LEDGERS}
    original.update({
        'history.json': b'[{"frozen":true}]',
        'neuron_current.json': b'{"mode":"SHADOW_RESEARCH","production_influence":false}',
        'prediction_ledger_future.json': b'{"preserve":true}',
    })
    for name, body in original.items():
        (data / name).write_bytes(body)
    archive = tmp_path / 'runner/tenis-runtime.tar.gz'
    pack(data, archive)
    return tmp_path, data, archive, original


def run_exclusion(root):
    action = ACTION.read_text()
    assert f'- name: {STEP}' in action, 'Pages still contains unused raw research ledgers'
    step = action.split(f'- name: {STEP}', 1)[1].split('\n    - name:', 1)[0]
    script = textwrap.dedent(step.split('run: |\n', 1)[1])
    return subprocess.run(['bash', '-e', '-c', script], cwd=root,
        env={**os.environ, 'RUNNER_TEMP': str(root / 'runner')}, capture_output=True, text=True)


def test_pages_excludes_only_research_and_archive_restores_every_byte(publication):
    root, data, archive, original = publication
    before = hashlib.sha256(archive.read_bytes()).hexdigest()
    result = run_exclusion(root)
    assert result.returncode == 0, result.stderr
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == before
    assert {p.name for p in data.iterdir()} == set(original) - set(LEDGERS)
    for name in set(original) - set(LEDGERS):
        assert (data / name).read_bytes() == original[name]
    restored = root / 'restored'
    verify(archive, restored)
    assert {p.name: p.read_bytes() for p in restored.iterdir()} == original
    report = json.loads(result.stdout)
    assert report['excluded_bytes'] == sum(len(original[name]) for name in LEDGERS)


@pytest.mark.parametrize('damage', ['mismatch', 'missing_source', 'missing_member',
                                  'missing_archive', 'corrupt_archive', 'symlink'])
def test_unverified_archive_never_removes_any_publication_copy(publication, damage):
    root, data, archive, original = publication
    last = data / LEDGERS[-1]
    if damage == 'mismatch':
        last.write_bytes(b'{"changed":true}')
    elif damage == 'missing_source':
        last.unlink()
    elif damage == 'missing_member':
        last.unlink()
        pack(data, archive)
        last.write_bytes(original[last.name])
    elif damage == 'missing_archive':
        archive.unlink()
    elif damage == 'corrupt_archive':
        archive.write_bytes(archive.read_bytes()[:40])
    elif damage == 'symlink':
        outside = root / 'outside.json'
        outside.write_bytes(original[last.name])
        last.unlink()
        last.symlink_to(outside)
    before = {p.name: p.read_bytes() for p in data.iterdir()}
    result = run_exclusion(root)
    assert result.returncode != 0
    assert {p.name: p.read_bytes() for p in data.iterdir()} == before
    if damage == 'symlink':
        assert outside.read_bytes() == original[last.name]


def test_all_pages_producers_preserve_archive_before_excluding_research():
    action = ACTION.read_text()
    assert action.index('scripts/history_publication_chunks.py restore') < action.index('runtime_snapshot.py pack')
    assert action.index('runtime_snapshot.py verify') < action.index('actions/upload-artifact@v4')
    assert action.index('actions/upload-artifact@v4') < action.index(STEP)
    assert action.index('node scripts/build_delivery.mjs') < action.index(STEP)
    assert 'retention-days: 90' in action
    for name in ('update-and-pages.yml', 'neuron-shadow.yml', 'deploy-pages-fast.yml'):
        workflow = (ROOT / '.github/workflows' / name).read_text()
        assert workflow.index('uses: ./.github/actions/prepare-pages') < workflow.index('uses: actions/upload-pages-artifact@v4')
