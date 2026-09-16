"""Reproducible runtime snapshot with verified, traversal-safe offline restoration.

This is the migration preparation step. It does not disable any current writer.
Only published JSON files are included; training/API caches need a private durable
archive before the production pipeline can stop using their existing storage.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile


def pack(source: Path, target: Path) -> dict:
    files = {p.name: p.read_bytes() for p in sorted(source.glob('*.json')) if p.is_file() and not p.is_symlink()}
    if not files:
        raise ValueError('No runtime JSON files found')
    manifest = {'schema': 1, 'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'scope': 'published-runtime-only; not a complete training-cache archive',
                'files': {n: {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for n, b in files.items()}}
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as gz, tarfile.open(fileobj=gz, mode='w|') as tar:
        for name, body in {'manifest.json': json.dumps(manifest, sort_keys=True).encode(), **files}.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(body))
    return manifest


def verify(archive: Path, destination: Path | None = None) -> dict:
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)) or sum(m.size for m in members) > 1024**3:
            raise ValueError('Duplicate entries or archive larger than 1 GiB')
        if any(not m.isfile() or PurePosixPath(m.name).name != m.name or '\\' in m.name for m in members):
            raise ValueError('Only flat regular files are accepted')
        if 'manifest.json' not in names:
            raise ValueError('Manifest missing')
        manifest = json.load(tar.extractfile('manifest.json'))
        if manifest.get('schema') != 1 or set(names) != {'manifest.json', *manifest['files']}:
            raise ValueError('Manifest membership mismatch')
        # Verify every byte before making the first destination write.
        for name, item in manifest['files'].items():
            body = tar.extractfile(name).read()
            if len(body) != item['bytes'] or hashlib.sha256(body).hexdigest() != item['sha256']:
                raise ValueError('Snapshot checksum mismatch: '+name)
        if destination is not None:
            if destination.exists() and any(destination.iterdir()):
                raise ValueError('Restore requires an empty destination; existing data is never overwritten')
            destination.mkdir(parents=True, exist_ok=True)
            for name in manifest['files']:
                (destination / name).write_bytes(tar.extractfile(name).read())
        return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['pack', 'verify', 'restore'])
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('frontend/data'))
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.command == 'restore' and args.destination is None:
        parser.error('restore requires --destination')
    result = pack(args.source, args.archive) if args.command == 'pack' else verify(args.archive, args.destination if args.command == 'restore' else None)
    print(json.dumps({'source_sha': result['source_sha'], 'files': len(result['files']), 'scope': result['scope']}))
