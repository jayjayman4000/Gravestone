"""Host preparation uses synthetic local data, never owner inventories."""
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def preparation():
    path = ROOT / 'host_prepare' / '__init__.py'
    if not path.exists():
        raise AssertionError('Host preparation pack builder is not implemented')
    spec = importlib.util.spec_from_file_location('host_preparation_test_module', path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HostPreparationTests(unittest.TestCase):
    def test_portable_pack_preserves_original_and_private_inventory(self):
        prep = preparation()
        raw = b'%PDF-1.4\nsynthetic fixture\n%%EOF\n'
        equipment = {key: '' for key in prep.FIELDS}
        equipment.update(category='tools', exact_model='Fixture only',
                         official_manual_link='https://example.org/manual', local_filename='fixture.pdf')
        payload = {'equipment': [equipment], 'rights_acknowledged': True,
                   'pdfs': [{'name': 'fixture.pdf', 'title': 'Fixture only',
                             'base64': base64.b64encode(raw).decode()}]}
        packed = prep.build_pack(payload)
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            doc = manifest['documents'][0]
            self.assertEqual(doc['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(archive.read(doc['path']), raw)
            self.assertEqual(doc['source_id'], 'other')
            self.assertEqual(json.loads(archive.read('inventory.json'))['equipment'], [equipment])
            self.assertIn(b'Fixture only', archive.read('MY_EQUIPMENT.md'))
            self.assertIn(b'not', archive.read('TRANSFER.md'))
            self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))
            self.assertTrue(all(not name.startswith('/') and '..' not in name.split('/')
                                for name in archive.namelist()))
        self.assertEqual(payload['pdfs'][0]['base64'], base64.b64encode(raw).decode())


    def test_markdown_inventory_does_not_execute_user_html(self):
        prep = preparation()
        item = dict.fromkeys(prep.FIELDS, '')
        item.update(category='tools', exact_model='<script>alert(1)</script>',
                    unknowns='[link](javascript:alert(1))\n# forged heading')
        packed = prep.build_pack({'equipment': [item], 'pdfs': [], 'rights_acknowledged': True})
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            markdown = archive.read('MY_EQUIPMENT.md').decode()
            self.assertNotIn('<script>', markdown)
            self.assertNotIn('[link](', markdown)
            self.assertNotIn('\n# forged heading', markdown)
            self.assertEqual(json.loads(archive.read('inventory.json'))['equipment'], [item])

    def test_rejects_unsafe_input_and_bounds_without_partial_output(self):
        import copy
        prep = preparation()
        raw = b'%PDF-1.4\nfixture\n%%EOF'
        item = dict.fromkeys(prep.FIELDS, '')
        item.update(category='tools', official_manual_link='https://example.org/manual')
        good = {'equipment': [item], 'rights_acknowledged': True,
                'pdfs': [{'name': '../../fixture.pdf', 'title': 'Fixture',
                          'base64': base64.b64encode(raw).decode()}]}
        changes = [lambda p: p.update(rights_acknowledged=False),
                   lambda p: p['equipment'][0].update(category='secret'),
                   lambda p: p['equipment'][0].update(official_manual_link='javascript:alert(1)'),
                   lambda p: p['equipment'][0].update(official_manual_link='https://user:pass@example.org'),
                   lambda p: p['equipment'][0].update(exact_model=42),
                   lambda p: p['equipment'][0].update(unknowns='x' * 4001),
                   lambda p: p['pdfs'][0].update(base64='not base64'),
                   lambda p: p['pdfs'][0].update(base64=base64.b64encode(b'<html>').decode()),
                   lambda p: p['pdfs'][0].update(title='bad\nheader'),
                   lambda p: p['pdfs'].append(p['pdfs'][0]),
                   lambda p: p.update(equipment=[item] * 101)]
        for change in changes:
            payload = copy.deepcopy(good)
            change(payload)
            with self.subTest(payload=str(payload)[:80]), self.assertRaises(ValueError):
                prep.build_pack(payload)
        prep.MAX_PDF = len(raw) - 1
        with self.assertRaises(ValueError):
            prep.build_pack(good)
        prep.MAX_PDF = len(raw)
        prep.MAX_TOTAL = len(raw) - 1
        with self.assertRaises(ValueError):
            prep.build_pack(good)
        # Original filename is metadata only, never a ZIP member pathname.
        prep.MAX_TOTAL = len(raw)
        with zipfile.ZipFile(io.BytesIO(prep.build_pack(good))) as archive:
            self.assertFalse(any('..' in n for n in archive.namelist()))


if __name__ == '__main__':
    unittest.main()
