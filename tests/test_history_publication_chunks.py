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


def test_corrupt_chunk_refuses_restore(tmp_path, monkeypatch):
    monkeypatch.setattr(publication, 'CHUNK_BYTES', 16)
    (tmp_path / 'history.json').write_bytes(b'1234567890' * 10)
    publication.pack(tmp_path)
    (tmp_path / 'history_chunks' / '0000.part').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='Corrupt history chunk'):
        publication.restore(tmp_path)
    assert not (tmp_path / 'history.json').exists()
