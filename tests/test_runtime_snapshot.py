import io
import json
import tarfile
import pytest
from scripts.runtime_snapshot import pack, verify


def test_snapshot_roundtrip_preserves_all_bytes_and_refuses_overwrite(tmp_path):
    source=tmp_path/'source';source.mkdir()
    (source/'results.json').write_bytes(b'[{"probability": -0.0, "value": 57.1}]')
    archive=tmp_path/'snapshot.gz';pack(source,archive)
    original=archive.read_bytes();pack(source,archive);assert archive.read_bytes()==original
    dest=tmp_path/'restored';verify(archive,dest)
    assert (dest/'results.json').read_bytes()==(source/'results.json').read_bytes()
    with pytest.raises(ValueError,match='empty destination'):verify(archive,dest)


def test_snapshot_rejects_traversal_without_writing(tmp_path):
    archive=tmp_path/'bad.gz'
    with tarfile.open(archive,'w:gz') as tar:
        info=tarfile.TarInfo('../outside.json');info.size=2;tar.addfile(info,io.BytesIO(b'{}'))
    with pytest.raises(ValueError,match='flat regular'):verify(archive,tmp_path/'restored')
    assert not (tmp_path/'restored').exists()


def test_snapshot_rejects_corrupt_content_before_restoring(tmp_path):
    archive=tmp_path/'bad.gz'
    manifest={'schema':1,'files':{'results.json':{'bytes':2,'sha256':'0'*64}}}
    with tarfile.open(archive,'w:gz') as tar:
        for name,body in [('manifest.json',json.dumps(manifest).encode()),('results.json',b'{}')]:
            info=tarfile.TarInfo(name);info.size=len(body);tar.addfile(info,io.BytesIO(body))
    with pytest.raises(ValueError,match='checksum'):verify(archive,tmp_path/'restored')
    assert not (tmp_path/'restored').exists()
