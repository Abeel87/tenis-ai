import hashlib
import json

import pytest

from scripts import history_publication_chunks as publication

LEDGER_FILES = [
    'prediction_ledger_shadow.json',
    'prediction_ledger_selection_shadow.json',
    'prediction_ledger_settlement_shadow.json',
]


def test_history_survives_repository_publication(tmp_path, monkeypatch):
    monkeypatch.setattr(publication, 'CHUNK_BYTES', 128)
    original = json.dumps([{'id': i, 'value': 'ą' * 15} for i in range(20)], ensure_ascii=False).encode()
    (tmp_path / 'history.json').write_bytes(original)
    publication.pack(tmp_path)
    assert not (tmp_path / 'history.json').exists()
    assert len(list((tmp_path / 'history_chunks').glob('*.part'))) > 1
    publication.restore(tmp_path)
    assert (tmp_path / 'history.json').read_bytes() == original
    # A later build restores from tracked chunks without needing the old file.
    (tmp_path / 'history.json').unlink()
    publication.restore(tmp_path)
    assert hashlib.sha256((tmp_path / 'history.json').read_bytes()).digest() == hashlib.sha256(original).digest()


@pytest.mark.parametrize('filename', ['history.json', *LEDGER_FILES])
def test_corrupt_chunk_refuses_restore(tmp_path, monkeypatch, filename):
    monkeypatch.setattr(publication, 'CHUNK_BYTES', 16)
    (tmp_path / filename).write_bytes(b'1234567890' * 10)
    publication.pack(tmp_path, filename)
    (publication.paths(tmp_path, filename)[1] / '0000.part').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='Corrupt history chunk'):
        publication.restore(tmp_path, filename)
    assert not (tmp_path / filename).exists()


@pytest.mark.parametrize('filename', LEDGER_FILES)
def test_cli_preserves_prediction_ledger_across_publication(tmp_path, filename):
    import subprocess
    import sys

    ledger = b'{"rows":[{"id":"frozen", "probability":0.713}],"mode":"SHADOW_ONLY"}\n'
    (tmp_path / 'history.json').write_bytes(b'[]\n')
    target = tmp_path / filename
    target.write_bytes(ledger)
    command = [sys.executable, str(publication.ROOT / 'scripts/history_publication_chunks.py')]
    subprocess.run(command + ['pack', '--data', str(tmp_path)], check=True)
    assert not target.exists(), 'Ledger must not remain a growing Git blob'
    subprocess.run(command + ['verify', '--data', str(tmp_path)], check=True)
    subprocess.run(command + ['restore', '--data', str(tmp_path)], check=True)
    assert target.read_bytes() == ledger


@pytest.mark.parametrize('name', LEDGER_FILES)
def test_prediction_ledger_multiple_chunks_and_repack(tmp_path, monkeypatch, name):
    monkeypatch.setattr(publication, 'CHUNK_BYTES', 32)
    target = tmp_path / name
    original = json.dumps({'rows': [{'id': i, 'probability': 0.713} for i in range(20)]}).encode()
    target.write_bytes(original)
    publication.pack(tmp_path, name)
    folder = publication.paths(tmp_path, name)[1]
    assert all(part.stat().st_size <= 32 for part in folder.glob('*.part'))
    publication.restore(tmp_path, name)
    assert target.read_bytes() == original
    target.write_bytes(b'{"rows":[]}')
    publication.pack(tmp_path, name)
    assert len(list(folder.glob('*.part'))) == 1
    publication.restore(tmp_path, name)
    assert target.read_bytes() == b'{"rows":[]}'


def test_pages_retains_all_ledger_bytes_but_removes_repository_parts(tmp_path):
    import subprocess
    import sys
    from scripts import runtime_snapshot

    data = tmp_path / 'frontend/data'
    data.mkdir(parents=True)
    originals = {name: json.dumps({'report': name, 'rows': [{'p': 0.713}]}).encode()
                 for name in ['history.json', *LEDGER_FILES]}
    for name, body in originals.items():
        (data / name).write_bytes(body)
        publication.pack(data, name)
    command = [sys.executable, str(publication.ROOT / 'scripts/history_publication_chunks.py')]
    subprocess.run(command + ['restore', '--data', str(data)], check=True)
    archive = tmp_path / 'runtime.tar.gz'
    runtime_snapshot.pack(data, archive)
    manifest = runtime_snapshot.verify(archive)
    for name, body in originals.items():
        assert manifest['files'][name]['sha256'] == hashlib.sha256(body).hexdigest()
    action = (publication.ROOT / '.github/actions/prepare-pages/action.yml').read_text()
    cleanup = next(line.strip().removeprefix('run: ') for line in action.splitlines()
                   if line.strip().startswith('run: rm -rf '))
    subprocess.run(['bash', '-e', '-c', cleanup], cwd=tmp_path, check=True)
    assert not list(data.glob('*_chunks')), 'Pages must not ship redundant repository parts'
    assert {name: (data / name).read_bytes() for name in originals} == originals
