import json
from pathlib import Path
import subprocess

import pytest

from backend import neuron
from scripts import publish_neuron_shadow as publisher


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, stderr=subprocess.PIPE).strip()


def configure(root):
    git(root, 'config', 'user.name', 'Neuron test')
    git(root, 'config', 'user.email', 'neuron-test@example.invalid')


def store(root, path, payload):
    file = root / path; file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(payload))


def setup_repositories(tmp_path):
    remote = tmp_path / 'remote.git'; local = tmp_path / 'local'; writer = tmp_path / 'writer'
    git(tmp_path, 'init', '--bare', '--initial-branch=main', str(remote))
    git(tmp_path, 'clone', str(remote), str(local)); configure(local)
    model = {'format': 'tenis-ai-neuron-siamese', 'W1': [[1.]], 'generated_at': '2026-10-22T10:00:00Z'}
    model_id = neuron.model_identity(model)
    store(local, publisher.ARTIFACTS[0], model)
    store(local, publisher.ARTIFACTS[1], {'model_id': model_id, 'quality_gate': {'passed': True}})
    store(local, publisher.ARTIFACTS[2], {'model_id': model_id, 'generated_at': '2026-10-24T10:00:00Z'})
    store(local, 'backend/neuron.py', 'source baseline')
    git(local, 'add', '.'); git(local, 'commit', '-m', 'baseline'); git(local, 'push', 'origin', 'main')
    git(tmp_path, 'clone', str(remote), str(writer)); configure(writer)
    return local, writer, model


def test_publication_recovers_json_race_preserving_candidate_and_other_owners(tmp_path):
    local, writer, model = setup_repositories(tmp_path)
    candidate = {**model, 'W1': [[2.]], 'generated_at': '2026-10-25T08:00:00Z'}
    model_id = neuron.model_identity(candidate)
    store(local, publisher.ARTIFACTS[0], candidate)
    store(local, publisher.ARTIFACTS[1], {'model_id': model_id, 'quality_gate': {'passed': True}})
    store(local, publisher.ARTIFACTS[2], {'model_id': model_id, 'generated_at': '2026-10-25T10:00:00Z'})
    def race(attempt):
        if attempt != 1: return
        store(writer, publisher.ARTIFACTS[2], {'model_id': neuron.model_identity(model),
                                            'generated_at': '2026-10-25T09:00:00Z'})
        store(writer, 'other-owner.json', {'must_survive': True})
        git(writer, 'add', '.'); git(writer, 'commit', '-m', 'concurrent scoring and unrelated owner')
        git(writer, 'push', 'origin', 'main')
    result = publisher.publish(local, before_push=race)
    assert result['status'] == 'PUBLISHED' and result['attempts'] == 2
    git(writer, 'fetch', 'origin', 'main')
    assert json.loads(git(writer, 'show', 'FETCH_HEAD:' + publisher.ARTIFACTS[0])) == candidate
    assert json.loads(git(writer, 'show', 'FETCH_HEAD:other-owner.json')) == {'must_survive': True}
    assert json.loads(git(writer, 'show', 'FETCH_HEAD:' + publisher.ARTIFACTS[2]))['model_id'] == model_id


def test_publication_rejects_concurrent_source_change(tmp_path):
    local, writer, model = setup_repositories(tmp_path)
    store(local, publisher.ARTIFACTS[2], {'model_id': neuron.model_identity(model),
                                       'generated_at': '2026-10-25T10:00:00Z'})
    store(writer, 'backend/neuron.py', 'new source must not receive old artifacts')
    git(writer, 'add', '.'); git(writer, 'commit', '-m', 'source change'); git(writer, 'push', 'origin', 'main')
    with pytest.raises(RuntimeError, match='SOURCE_CHANGED'):
        publisher.publish(local)


def test_publication_never_overwrites_newer_scoring_or_failed_quality(tmp_path):
    local, writer, model = setup_repositories(tmp_path)
    store(local, publisher.ARTIFACTS[2], {'model_id': neuron.model_identity(model),
                                       'generated_at': '2026-10-23T10:00:00Z'})
    with pytest.raises(RuntimeError, match='NEWER_SCORING'):
        publisher.publish(local)
    store(local, publisher.ARTIFACTS[1], {'quality_gate': {'passed': False}})
    with pytest.raises(ValueError, match='QUALITY_GATE'):
        publisher.publish(local)


def test_workflow_gates_every_training_and_archives_failures():
    text = Path('.github/workflows/neuron-shadow.yml').read_text()
    training = text.split('- name: Train from Tenis AI raw history')[1].split('- name:')[0]
    gate = text.split('- name: Candidate quality gate against pre-match Elo')[1].split('- name:')[0]
    condition = lambda section: next(line.strip() for line in section.splitlines() if line.strip().startswith('if:'))
    assert condition(training) == condition(gate)
    assert "github.event_name == 'workflow_run'" not in condition(training)
    assert 'python backend/neuron.py gate' in gate
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert 'if: always()' in text and 'artifacts/neuron/' in text
    assert 'python scripts/publish_neuron_shadow.py' in text
    assert 'git rebase' not in text
