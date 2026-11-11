"""Streaming publication archive and bounded expansion regression."""
import io
import json
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from scripts import runtime_snapshot as snapshot


class SnapshotCapacityTests(TestCase):
    def test_streaming_pack_is_reproducible_and_restores_exact_bytes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); source = root/'source'; source.mkdir()
            body = b'[{"p":-0.0,"source":"exact"}]'
            (source/'results.json').write_bytes(body)
            archive = root/'runtime.tar.gz'
            # pack must not accumulate every growing ledger in memory.
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('whole-file read')):
                snapshot.pack(source, archive)
                snapshot.verify(archive, root/'restored')
            first = archive.read_bytes(); snapshot.pack(source, archive)
            self.assertEqual(archive.read_bytes(), first)
            self.assertEqual((root/'restored/results.json').read_bytes(), body)
            with self.assertRaisesRegex(ValueError, 'empty destination'):
                snapshot.verify(archive, root/'restored')

    def test_expanded_byte_budget_applies_before_pack_and_restore(self):
        self.assertEqual(snapshot.MAX_EXPANDED_BYTES, 4*1024**3)
        with TemporaryDirectory() as folder:
            root=Path(folder); source=root/'source'; source.mkdir()
            (source/'results.json').write_text('[]')
            archive=root/'runtime.tar.gz'; snapshot.pack(source, archive)
            with patch.object(snapshot, 'MAX_EXPANDED_BYTES', 1):
                with self.assertRaisesRegex(ValueError, 'expanded-byte budget'):
                    snapshot.pack(source, root/'too-large.tar.gz')
                with self.assertRaisesRegex(ValueError, 'expanded-byte budget'):
                    snapshot.verify(archive, root/'restored')
            self.assertFalse((root/'restored').exists())
            self.assertFalse((root/'too-large.tar.gz').exists())

    def test_duplicates_and_corruption_are_rejected_before_any_write(self):
        for duplicate in (True, False):
            with self.subTest(duplicate=duplicate), TemporaryDirectory() as folder:
                root=Path(folder); archive=root/'bad.tar.gz'
                manifest={'schema':1,'files':{'results.json':{'bytes':2,'sha256':'0'*64}}}
                with tarfile.open(archive,'w:gz') as tar:
                    rows=[('manifest.json',json.dumps(manifest).encode()),('results.json',b'[]')]
                    if duplicate: rows.append(('results.json',b'[]'))
                    for name,body in rows:
                        entry=tarfile.TarInfo(name);entry.size=len(body);tar.addfile(entry,io.BytesIO(body))
                with self.assertRaisesRegex(ValueError, 'Duplicate|checksum'):
                    snapshot.verify(archive,root/'restored')
                self.assertFalse((root/'restored').exists())
