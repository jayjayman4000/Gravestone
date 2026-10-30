"""Exercise source extraction on stock bookworm Python without tar filters."""
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_packager():
    spec = importlib.util.spec_from_file_location('ai_packager_extraction', ROOT / 'ai/package.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceExtractionTests(unittest.TestCase):
    def test_regular_source_extracts_without_new_tarfile_filter_api(self):
        module = load_packager()
        self.assertTrue(callable(getattr(module, 'extract_source', None)),
                        'need an extractor compatible with stock bookworm Python')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / 'source.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                member = tarfile.TarInfo('source-commit/build.sh')
                member.size = 8
                member.mode = 0o4755
                tar.addfile(member, io.BytesIO(b'original'))
            target = base / 'out'
            target.mkdir()
            with patch.object(tarfile.TarFile, 'extractall', side_effect=AssertionError('no extractall/filter API')):
                module.extract_source(archive, target, 'source-commit')
            output = target / 'source-commit/build.sh'
            self.assertEqual(output.read_bytes(), b'original')
            self.assertEqual(output.stat().st_mode & 0o7777, 0o755)
            with self.assertRaises(ValueError):
                module.extract_source(archive, target, 'source-commit')

    def test_rejects_traversal_links_devices_and_unexpected_roots_before_writing(self):
        module = load_packager()
        self.assertTrue(callable(getattr(module, 'extract_source', None)))
        cases = [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                 ('source-commit/../escape', tarfile.REGTYPE), ('wrong-root/file', tarfile.REGTYPE),
                 ('source-commit/link', tarfile.SYMTYPE), ('source-commit/hard', tarfile.LNKTYPE),
                 ('source-commit/device', tarfile.CHRTYPE), ('source-commit/fifo', tarfile.FIFOTYPE)]
        for name, kind in cases:
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                archive = base / 'source.tar'
                with tarfile.open(archive, 'w') as tar:
                    good = tarfile.TarInfo('source-commit/first')
                    tar.addfile(good, io.BytesIO(b''))
                    bad = tarfile.TarInfo(name)
                    bad.type = kind
                    bad.linkname = '/etc/passwd'
                    tar.addfile(bad)
                target = base / 'out'
                target.mkdir()
                with self.assertRaises(ValueError):
                    module.extract_source(archive, target, 'source-commit')
                self.assertEqual(list(target.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
