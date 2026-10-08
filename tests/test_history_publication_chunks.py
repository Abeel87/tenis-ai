import hashlib
import json

import pytest

from scripts import history_publication_chunks as publication


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


@pytest.mark.parametrize('filename', ['history.json', 'prediction_ledger_shadow.json'])
def test_corrupt_chunk_refuses_restore(tmp_path, monkeypatch, filename):
    monkeypatch.setattr(publication, 'CHUNK_BYTES', 16)
    (tmp_path / filename).write_bytes(b'1234567890' * 10)
    publication.pack(tmp_path, filename)
    (publication.paths(tmp_path, filename)[1] / '0000.part').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='Corrupt history chunk'):
        publication.restore(tmp_path, filename)
    assert not (tmp_path / filename).exists()


def test_cli_preserves_prediction_ledger_across_publication(tmp_path):
    import subprocess
    import sys

    ledger = b'{"rows":[{"id":"frozen", "probability":0.713}],"mode":"SHADOW_ONLY"}\n'
    (tmp_path / 'history.json').write_bytes(b'[]\n')
    target = tmp_path / 'prediction_ledger_shadow.json'
    target.write_bytes(ledger)
    command = [sys.executable, str(publication.ROOT / 'scripts/history_publication_chunks.py')]
    subprocess.run(command + ['pack', '--data', str(tmp_path)], check=True)
    assert not target.exists(), 'Ledger must not remain a growing Git blob'
    subprocess.run(command + ['verify', '--data', str(tmp_path)], check=True)
    subprocess.run(command + ['restore', '--data', str(tmp_path)], check=True)
    assert target.read_bytes() == ledger


def test_prediction_ledger_multiple_chunks_and_repack(tmp_path, monkeypatch):
    monkeypatch.setattr(publication, 'CHUNK_BYTES', 32)
    name = 'prediction_ledger_shadow.json'
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
