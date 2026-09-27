#!/usr/bin/env python3
"""Store the exact history bytes in small Git objects; restore for builds/Pages."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNK_BYTES = 16 * 1024 * 1024


def paths(data: Path):
    return data / 'history.json', data / 'history_chunks', data / 'history_chunks' / 'manifest.json'


def pack(data: Path) -> None:
    history, folder, manifest = paths(data)
    if not history.is_file():
        raise FileNotFoundError(history)
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    digest = hashlib.sha256()
    with history.open('rb') as source:
        for index, block in enumerate(iter(lambda: source.read(CHUNK_BYTES), b'')):
            name = f'{index:04d}.part'
            (folder / name).write_bytes(block)
            digest.update(block)
            entries.append({'name': name, 'bytes': len(block), 'sha256': hashlib.sha256(block).hexdigest()})
    if not entries:
        raise ValueError('Refusing to publish an empty history')
    document = {'format': 'exact-history-bytes-v1', 'bytes': history.stat().st_size,
                'sha256': digest.hexdigest(), 'chunks': entries}
    manifest.write_text(json.dumps(document, separators=(',', ':')) + '\n', encoding='utf-8')
    for stale in folder.glob('*.part'):
        if stale.name not in {entry['name'] for entry in entries}:
            stale.unlink()
    # Verify the complete round trip before deleting the only working copy.
    verify(data, history)
    history.unlink()


def verify(data: Path, history: Path | None = None) -> None:
    target, folder, manifest = paths(data)
    doc = json.loads(manifest.read_text(encoding='utf-8'))
    if doc.get('format') != 'exact-history-bytes-v1' or not isinstance(doc.get('chunks'), list):
        raise ValueError('Invalid history manifest')
    digest = hashlib.sha256()
    total = 0
    for index, entry in enumerate(doc['chunks']):
        name = f'{index:04d}.part'
        if entry.get('name') != name:
            raise ValueError('Invalid chunk order')
        block = (folder / name).read_bytes()
        if len(block) != entry['bytes'] or hashlib.sha256(block).hexdigest() != entry['sha256']:
            raise ValueError(f'Corrupt history chunk: {name}')
        digest.update(block)
        total += len(block)
    if total != doc['bytes'] or digest.hexdigest() != doc['sha256']:
        raise ValueError('History digest mismatch')
    if history is not None and hashlib.sha256(history.read_bytes()).hexdigest() != doc['sha256']:
        raise ValueError('History round trip mismatch')


def restore(data: Path) -> None:
    history, folder, manifest = paths(data)
    if not manifest.exists():
        if not history.exists():
            raise FileNotFoundError('Neither history nor chunk manifest exists')
        return
    verify(data)
    doc = json.loads(manifest.read_text(encoding='utf-8'))
    if history.exists() and history.stat().st_size == doc['bytes']:
        if hashlib.sha256(history.read_bytes()).hexdigest() == doc['sha256']:
            return
    temporary = history.with_suffix('.json.tmp')
    try:
        with temporary.open('wb') as output:
            for entry in doc['chunks']:
                with (folder / entry['name']).open('rb') as source:
                    while block := source.read(1024 * 1024):
                        output.write(block)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != doc['sha256']:
            raise ValueError('Restored history digest mismatch')
        temporary.replace(history)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('pack', 'restore', 'verify'))
    parser.add_argument('--data', type=Path, default=ROOT / 'frontend' / 'data')
    args = parser.parse_args()
    {'pack': pack, 'restore': restore, 'verify': verify}[args.action](args.data)


if __name__ == '__main__':
    main()
