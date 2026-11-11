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
import shutil


# The exact publication sources exceeded the former 1 GiB ceiling on 2026-11-11.
# Keep a bounded expansion budget while reading one stream at a time.
MAX_EXPANDED_BYTES = 4 * 1024**3
MAX_MANIFEST_BYTES = 4 * 1024**2


def pack(source: Path, target: Path) -> dict:
    files = {p.name: p for p in sorted(source.glob('*.json')) if p.is_file() and not p.is_symlink()}
    if not files:
        raise ValueError('No runtime JSON files found')
    if 'manifest.json' in files:
        raise ValueError('Reserved runtime snapshot filename: manifest.json')
    metadata = {}
    for name, path in files.items():
        with path.open('rb') as stream:
            metadata[name] = {'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}
    manifest = {'schema': 1, 'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'scope': 'published-runtime-only; not a complete training-cache archive',
                'files': metadata}
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    if len(manifest_bytes) > MAX_MANIFEST_BYTES or sum(x['bytes'] for x in metadata.values()) + len(manifest_bytes) > MAX_EXPANDED_BYTES:
        raise ValueError('Runtime snapshot exceeds expanded-byte budget')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as gz, tarfile.open(fileobj=gz, mode='w|') as tar:
        info = tarfile.TarInfo('manifest.json')
        info.size = len(manifest_bytes)
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(manifest_bytes))
        for name, path in files.items():
            info = tarfile.TarInfo(name)
            info.size = metadata[name]['bytes']
            info.mode = 0o644
            with path.open('rb') as stream:
                tar.addfile(info, stream)
    return manifest


def verify(archive: Path, destination: Path | None = None) -> dict:
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate snapshot entries')
        if sum(m.size for m in members) > MAX_EXPANDED_BYTES:
            raise ValueError('Runtime snapshot exceeds expanded-byte budget')
        if any(not m.isfile() or PurePosixPath(m.name).name != m.name or '\\' in m.name or ':' in m.name for m in members):
            raise ValueError('Only flat regular files are accepted')
        if 'manifest.json' not in names:
            raise ValueError('Manifest missing')
        if tar.getmember('manifest.json').size > MAX_MANIFEST_BYTES:
            raise ValueError('Snapshot manifest too large')
        manifest = json.load(tar.extractfile('manifest.json'))
        if manifest.get('schema') != 1 or set(names) != {'manifest.json', *manifest['files']}:
            raise ValueError('Manifest membership mismatch')
        # Verify every byte before making the first destination write.
        for name, item in manifest['files'].items():
            with tar.extractfile(name) as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if tar.getmember(name).size != item['bytes'] or digest != item['sha256']:
                raise ValueError('Snapshot checksum mismatch: '+name)
        if destination is not None:
            if destination.exists() and any(destination.iterdir()):
                raise ValueError('Restore requires an empty destination; existing data is never overwritten')
            destination.mkdir(parents=True, exist_ok=True)
            for name in manifest['files']:
                with tar.extractfile(name) as source, (destination / name).open('wb') as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
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
    print(json.dumps({'source_sha': result['source_sha'], 'files': len(result['files']), 'scope': result['scope'],
                      'source_bytes': sum(x['bytes'] for x in result['files'].values()), 'max_expanded_bytes': MAX_EXPANDED_BYTES}))

