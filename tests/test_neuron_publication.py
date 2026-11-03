import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess

import pytest

from backend import neuron
from backend import prediction_ledger_shadow
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
    store(local, 'frontend/data/prediction_ledger_shadow.json', {
        'schema_version': prediction_ledger_shadow.SCHEMA_VERSION,
        'mode': prediction_ledger_shadow.MODE, 'rows': [],
    })
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


def paired_evidence(model, match_id=42):
    """Synthetic pre-match forecasts resolved through the actual settlement owner."""
    start = '2026-10-24T12:00:00+00:00'
    forecast = {'status': 'SHADOW_SCORE', 'match_id': match_id,
                'p1': 'Audit Alpha', 'p2': 'Audit Beta', 'scheduled_time': start,
                'p1_win_probability': .8, 'elo_p1_win_probability': .6,
                'feature_snapshot': {'A': [1.], 'B': [2.], 'C': [.5]}}
    rows = neuron.freeze_predictions({}, [forecast], neuron.model_identity(model),
                                     model['generated_at'], '2026-10-23T10:00:00Z', 'test-history')
    history = [{'match_key': f'id:{match_id}', 'match_id': match_id,
                'scheduled_time': start, 'status': 'settled',
                'settled_at': '2026-10-24T14:00:00Z',
                'settlement_source': 'synthetic_exact_source', 'settlement_version': 'test-1',
                'result': {'status': 'completed', 'p1': 'Audit Alpha', 'p2': 'Audit Beta',
                           'winner': 'Audit Alpha', 'sets': [[6, 4], [6, 4]]}}]
    rows = neuron.settle_predictions(rows, history, datetime(2026, 10, 25, tzinfo=timezone.utc))
    production = prediction_ledger_shadow.capture_rows(
        [{'match_key': f'id:{match_id}', 'candidate_key': 'match_winner|Audit Alpha',
          'market': 'match_winner', 'pick': 'Audit Alpha', 'line': -1, 'scheduled_time': start}],
        [.6], [.7], [None], ensemble_probs=[.9],
        now=datetime(2026, 10, 23, 9, tzinfo=timezone.utc))
    return list(rows.values()), production


def stage_evaluated_evidence(local, model, forecasts, production):
    ledger = {'schema_version': prediction_ledger_shadow.SCHEMA_VERSION,
              'mode': prediction_ledger_shadow.MODE, 'rows': production}
    store(local, 'frontend/data/prediction_ledger_shadow.json', ledger)
    store(local, 'data/neuron_predictions/2026-10.json', {
        **neuron.flags(), 'schema': 'neuron-predictions-1', 'predictions': forecasts})
    summary = neuron.summarize_predictions(forecasts, production_ledger=ledger)
    store(local, publisher.ARTIFACTS[2], {
        'model_id': neuron.model_identity(model), 'generated_at': '2026-10-25T10:00:00Z',
        'prospective': {**summary, 'evaluated_at': '2026-10-25T10:01:00Z'}})
    return summary


def test_publication_preserves_evaluated_frozen_production_comparison(tmp_path):
    local, writer, model = setup_repositories(tmp_path)
    forecasts, production = paired_evidence(model)
    evaluated = stage_evaluated_evidence(local, model, forecasts, production)
    assert evaluated['production_comparison']['settled_matches'] == 1
    result = publisher.publish(local)
    published = json.loads(git(local, 'show', result['commit'] + ':' + publisher.ARTIFACTS[2]))
    assert published['prospective'] == {**evaluated, 'evaluated_at': '2026-10-25T10:01:00Z'}
    assert published['prospective']['production_comparison']['production']['brier'] == pytest.approx(.01)
    assert published['prospective']['production_comparison']['promotion_authorized'] is False
    frozen = json.loads(git(local, 'show', result['commit'] + ':data/neuron_predictions/2026-10.json'))
    assert frozen['predictions'] == forecasts
    # The publisher never writes the production ledger, even when it is restored locally.
    assert json.loads(git(local, 'show', result['commit'] + ':frontend/data/prediction_ledger_shadow.json'))['rows'] == []


def test_publication_recomputes_pairs_after_concurrent_neuron_merge_using_run_local_baseline(tmp_path):
    local, writer, model = setup_repositories(tmp_path)
    first, production_first = paired_evidence(model, 42)
    second, production_second = paired_evidence(model, 43)
    stage_evaluated_evidence(local, model, first, production_first + production_second)
    def race(attempt):
        if attempt != 1:
            return
        store(writer, 'data/neuron_predictions/2026-10.json', {
            **neuron.flags(), 'schema': 'neuron-predictions-1', 'predictions': second})
        _, later = paired_evidence(model, 44)
        store(writer, 'frontend/data/prediction_ledger_shadow.json', {
            'schema_version': prediction_ledger_shadow.SCHEMA_VERSION,
            'mode': prediction_ledger_shadow.MODE, 'rows': later})
        git(writer, 'add', '.'); git(writer, 'commit', '-m', 'concurrent owned evidence')
        git(writer, 'push', 'origin', 'main')
        # Do not switch the evidence population midway through publication retries.
        store(local, 'frontend/data/prediction_ledger_shadow.json', {'unrelated_later_snapshot': True})
    result = publisher.publish(local, before_push=race)
    assert result['attempts'] == 2
    report = json.loads(git(local, 'show', result['commit'] + ':' + publisher.ARTIFACTS[2]))
    assert report['prospective']['settled_matches'] == 2
    assert report['prospective']['production_comparison']['settled_matches'] == 2
    assert report['prospective']['production_comparison']['production']['brier'] == pytest.approx(.01)
    retained = json.loads(git(local, 'show', result['commit'] + ':frontend/data/prediction_ledger_shadow.json'))
    assert [row['match_key'] for row in retained['rows']] == ['id:44']


@pytest.mark.parametrize('invalid', ['missing', 'malformed', 'wrong_schema', 'null'])
def test_publication_rejects_unavailable_or_invalid_production_ledger(tmp_path, invalid):
    local, writer, model = setup_repositories(tmp_path)
    forecasts, production = paired_evidence(model)
    stage_evaluated_evidence(local, model, forecasts, production)
    path = local / 'frontend/data/prediction_ledger_shadow.json'
    if invalid == 'missing':
        path.unlink()
    else:
        path.write_text({'malformed': '{', 'wrong_schema': '{"rows": []}', 'null': 'null'}[invalid])
    before = git(writer, 'rev-parse', 'HEAD')
    with pytest.raises((FileNotFoundError, ValueError)):
        publisher.publish(local)
    assert git(writer, 'ls-remote', 'origin', 'refs/heads/main').split()[0] == before


@pytest.mark.parametrize('unusable', ['legacy', 'post_start', 'other_fixture', 'other_schedule', 'wrong_selection'])
def test_publication_keeps_unproven_baselines_missing(tmp_path, unusable):
    local, writer, model = setup_repositories(tmp_path)
    forecasts, production = paired_evidence(model)
    if unusable == 'legacy':
        production[0]['model_scores'].pop('ensemble')
    else:
        field, value = {
            'post_start': ('captured_at', '2026-10-24T12:00:00+00:00'),
            'other_fixture': ('match_key', 'id:99'),
            'other_schedule': ('scheduled_time', '2026-10-24T13:00:00+00:00'),
            'wrong_selection': ('pick', 'Different Person'),
        }[unusable]
        production[0][field] = value
    stage_evaluated_evidence(local, model, forecasts, production)
    result = publisher.publish(local)
    report = json.loads(git(local, 'show', result['commit'] + ':' + publisher.ARTIFACTS[2]))
    paired = report['prospective']['production_comparison']
    assert paired['settled_matches'] == 0 and paired['missing_baseline_matches'] == 1
    assert paired['production'] is None and paired['historical_reconstruction'] is False


def test_publication_rejects_concurrent_production_evidence_contract_change(tmp_path):
    local, writer, model = setup_repositories(tmp_path)
    store(writer, 'backend/prediction_ledger_shadow.py', 'changed evidence contract')
    git(writer, 'add', '.'); git(writer, 'commit', '-m', 'contract change')
    git(writer, 'push', 'origin', 'main')
    with pytest.raises(RuntimeError, match='SOURCE_CHANGED'):
        publisher.publish(local)
