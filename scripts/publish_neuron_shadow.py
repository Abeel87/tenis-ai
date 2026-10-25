#!/usr/bin/env python3
"""Publish only Neuron-owned artifacts on fresh main, without rebasing JSON.

The generated candidate is preserved by the workflow artifact even if this
publication fails. Concurrent source/model changes fail closed. Other owners'
files always come from the freshly fetched main tree.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import neuron

ARTIFACTS = tuple(f'frontend/data/neuron_{name}.json' for name in ('model', 'metrics', 'current'))
LEDGER_PREFIX = 'data/neuron_predictions/'
OWNERS = ('backend/neuron.py', 'backend/history_hygiene_v78a.py',
          'backend/signal_settlement.py', 'backend/prediction_ledger_settlement_shadow.py',
          'scripts/publish_neuron_shadow.py', '.github/workflows/neuron-shadow.yml',
          'requirements.txt', 'requirements.lock')


def git(root, *args, input=None, env=None, check=True):
    result = subprocess.run(['git', *args], cwd=root, input=input, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={**os.environ, **(env or {})})
    if check and result.returncode:
        raise RuntimeError(f'git {args[0]} failed: {result.stderr.strip()}')
    return result


def object_id(root, ref, path):
    result = git(root, 'rev-parse', '--verify', f'{ref}:{path}', check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def remote_document(root, ref, path):
    if object_id(root, ref, path) is None:
        return None
    return json.loads(git(root, 'show', f'{ref}:{path}').stdout)


def merge_ledger(remote, incoming):
    documents = [doc for doc in (remote, incoming) if doc is not None]
    rows = {}
    for doc in documents:
        if doc.get('schema') != 'neuron-predictions-1' or doc.get('mode') != neuron.MODE:
            raise ValueError('INVALID_NEURON_LEDGER')
        for item in doc['predictions']:
            neuron.validate_prediction(item)
            old = rows.get(item['prediction_id'])
            if old:
                if old['snapshot_sha256'] != item['snapshot_sha256']:
                    raise ValueError('CONCURRENT_IMMUTABLE_PREDICTION_CONFLICT')
                if old.get('settlement', {}).get('status') == 'SETTLED':
                    new_fact = item.get('settlement', {})
                    if new_fact.get('status') == 'SETTLED' and old['settlement'] != new_fact:
                        raise ValueError('CONCURRENT_TERMINAL_EVIDENCE_CONFLICT')
                    continue
            rows[item['prediction_id']] = item
    return {**neuron.flags(), 'schema': 'neuron-predictions-1',
            'predictions': sorted(rows.values(), key=lambda row: row['prediction_id'])}


def publish(root=ROOT, attempts=3, before_push=None):
    root = Path(root)
    original = git(root, 'rev-parse', 'HEAD').stdout.strip()
    incoming = {path: json.loads((root / path).read_text()) for path in ARTIFACTS}
    ledger_dir = root / LEDGER_PREFIX
    local_ledgers = {str(path.relative_to(root)): json.loads(path.read_text())
                    for path in ledger_dir.glob('*.json')}
    model, report, current = (incoming[path] for path in ARTIFACTS)
    model_id = neuron.model_identity(model)
    if report.get('quality_gate', {}).get('passed') is not True:
        raise ValueError('ACTIVE_MODEL_HAS_NO_PASSED_QUALITY_GATE')
    if current.get('model_id') != model_id:
        raise ValueError('CURRENT_USES_DIFFERENT_MODEL')
    if report.get('model_id') is not None and report['model_id'] != model_id:
        raise ValueError('METRICS_USE_DIFFERENT_MODEL')
    original_model = remote_document(root, original, ARTIFACTS[0])
    original_model_id = neuron.model_identity(original_model) if original_model else None
    for attempt in range(1, attempts + 1):
        git(root, 'fetch', '--no-tags', 'origin', 'main')
        base = git(root, 'rev-parse', 'FETCH_HEAD').stdout.strip()
        for path in OWNERS:
            if object_id(root, original, path) != object_id(root, base, path):
                raise RuntimeError('NEURON_SOURCE_CHANGED_DURING_RUN: ' + path)
        live_model = remote_document(root, base, ARTIFACTS[0])
        live_id = neuron.model_identity(live_model) if live_model else None
        if live_id not in (original_model_id, model_id):
            raise RuntimeError('NEWER_DIFFERENT_MODEL_ALREADY_PUBLISHED')
        live_current = remote_document(root, base, ARTIFACTS[2]) or {}
        live_time = neuron.utc(live_current.get('generated_at'))
        own_time = neuron.utc(current.get('generated_at'))
        if own_time is None:
            raise ValueError('INVALID_SCORING_TIME')
        if live_time and live_time > own_time:
            raise RuntimeError('NEWER_SCORING_ALREADY_PUBLISHED')

        documents = dict(incoming)
        remote_paths = git(root, 'ls-tree', '-r', '--name-only', base, '--', LEDGER_PREFIX).stdout.splitlines()
        all_rows = []
        for path in sorted(set(remote_paths) | set(local_ledgers)):
            if not path.startswith(LEDGER_PREFIX) or not path.endswith('.json'):
                continue
            merged = merge_ledger(remote_document(root, base, path), local_ledgers.get(path))
            documents[path] = merged
            all_rows.extend(merged['predictions'])
        documents[ARTIFACTS[2]] = {**current, 'prospective': {
            **neuron.summarize_predictions(all_rows),
            'evaluated_at': current.get('prospective', {}).get('evaluated_at')}}

        with tempfile.TemporaryDirectory(prefix='neuron-index-') as directory:
            env = {'GIT_INDEX_FILE': str(Path(directory) / 'index')}
            git(root, 'read-tree', base, env=env)
            for path, document in documents.items():
                content = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
                blob = git(root, 'hash-object', '-w', '--stdin', input=content).stdout.strip()
                git(root, 'update-index', '--add', '--cacheinfo', '100644', blob, path, env=env)
            tree = git(root, 'write-tree', env=env).stdout.strip()
        old_tree = git(root, 'rev-parse', f'{base}^{{tree}}').stdout.strip()
        if tree == old_tree:
            return {'status': 'UNCHANGED', 'commit': base, 'attempts': attempt}
        commit = git(root, 'commit-tree', tree, '-p', base,
                     '-m', 'data: publish verified Neuron SHADOW evidence').stdout.strip()
        if before_push:
            before_push(attempt)
        pushed = git(root, 'push', 'origin', f'{commit}:refs/heads/main', check=False)
        if pushed.returncode == 0:
            return {'status': 'PUBLISHED', 'commit': commit, 'attempts': attempt}
        if not any(token in pushed.stderr.lower() for token in ('rejected', 'non-fast-forward', 'fetch first')):
            raise RuntimeError('NEURON_PUBLISH_FAILED: ' + pushed.stderr.strip())
    raise RuntimeError('NEURON_MAIN_MOVED_DURING_ALL_PUBLICATION_ATTEMPTS; artifacts preserved')


if __name__ == '__main__':
    print(json.dumps(publish(), indent=2))
