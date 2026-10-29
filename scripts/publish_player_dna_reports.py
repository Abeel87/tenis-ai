"""Publish exact run-local DNA reports onto current main without rebasing data.

Both workflow publication stages use this single owner. A temporary Git index
starts from fresh main; only the declared reports and the canonical SHADOW meta
projection are replaced. The long-running audit worktree and index stay intact.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.readiness_engine_shadow import project_observability_meta
from backend.snapshot_digest import canonical_json_sha256

DATA = 'frontend/data/'
READINESS = 'readiness_engine_shadow.json'
FULL_REPORTS = (
    'player_dna_point_dataset_summary.json', 'player_dna_profile_readiness.json',
    'player_dna_shadow_profile_summary.json', 'player_dna_point_scorer.json',
    'player_dna_current_shadow.json', 'player_dna_current_dynamic_shadow.json',
    'player_dna_current_simulation.json', 'player_dna_market_backtest.json',
    'player_dna_hold_calibration_audit.json', 'player_dna_hold_walk_forward.json',
    'player_dna_prospective_validation.json',
)


def git(root: Path, *args: str, data: bytes | None = None,
        env: dict[str, str] | None = None) -> bytes:
    return subprocess.run(['git', *args], cwd=root, input=data, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True).stdout


def publish(root: Path, mode: str) -> dict:
    if mode not in ('readiness', 'full'):
        raise ValueError('unknown publication mode')
    results = json.loads((root / DATA / 'results.json').read_bytes())
    names = (READINESS,) if mode == 'readiness' else (*FULL_REPORTS, READINESS)
    payloads = {name: (root / DATA / name).read_bytes() for name in names}
    report = json.loads(payloads[READINESS])
    # Reuse the canonical exact-snapshot and SHADOW isolation contract.
    project_observability_meta(results, report, {})
    expected = canonical_json_sha256(results)
    blobs = {name: git(root, 'hash-object', '-w', '--stdin', data=raw).decode().strip()
             for name, raw in payloads.items()}
    message = ('data: publish exact LOGIC-08 readiness' if mode == 'readiness'
               else 'data: refresh Player DNA SHADOW')
    with tempfile.TemporaryDirectory(prefix='dna-publication-') as directory:
        index_env = {**os.environ, 'GIT_INDEX_FILE': str(Path(directory) / 'index')}
        for attempt in range(3):
            git(root, 'fetch', 'origin', '--no-tags', 'main:refs/remotes/origin/main')
            base = git(root, 'rev-parse', 'origin/main').decode().strip()
            latest_results = json.loads(git(root, 'show', f'{base}:{DATA}results.json'))
            if canonical_json_sha256(latest_results) != expected:
                return {'changed': False, 'stale': True, 'source': base}
            meta = json.loads(git(root, 'show', f'{base}:{DATA}meta.json'))
            projected = project_observability_meta(results, report, meta)
            meta_bytes = (json.dumps(projected, ensure_ascii=False, indent=2) + '\n').encode()
            meta_blob = git(root, 'hash-object', '-w', '--stdin', data=meta_bytes).decode().strip()
            git(root, 'read-tree', base, env=index_env)
            for name, blob in {**blobs, 'meta.json': meta_blob}.items():
                git(root, 'update-index', '--add', '--cacheinfo', '100644', blob,
                    DATA + name, env=index_env)
            tree = git(root, 'write-tree', env=index_env).decode().strip()
            if tree == git(root, 'rev-parse', base + '^{tree}').decode().strip():
                return {'changed': False, 'stale': False, 'source': base}
            commit = git(root, 'commit-tree', tree, '-p', base, '-m', message).decode().strip()
            try:
                # A normal fast-forward push rejects a concurrent newer main.
                git(root, 'push', 'origin', f'{commit}:refs/heads/main')
            except subprocess.CalledProcessError:
                if attempt == 2:
                    raise
                time.sleep((attempt + 1) * 2)
                continue
            return {'changed': True, 'stale': False, 'source': base, 'commit': commit}
    raise RuntimeError('publication did not complete')  # pragma: no cover


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('readiness', 'full'))
    args = parser.parse_args()
    result = publish(Path.cwd(), args.mode)
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a', encoding='utf-8') as handle:
            for key in ('changed', 'stale'):
                handle.write(f'{key}={str(result[key]).lower()}\n')
    print('PLAYER_DNA_PUBLISH_OK ' + json.dumps({'mode': args.mode, **result}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
