"""Personal PDF vertical-slice acceptance; fixtures contain no survival advice."""
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from app import make_server


def pdf_bytes():
    # Small, valid one-page PDF with searchable fixture text, no extra packages.
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    text = b'BT /F1 12 Tf 10 100 Td (Quasar fixture text) Tj ET'
    objects.append(b'<< /Length ' + str(len(text)).encode() + b' >>\nstream\n' + text + b'\nendstream')
    raw = b'%PDF-1.4\n'; offsets = [0]
    for n, obj in enumerate(objects, 1):
        offsets.append(len(raw)); raw += str(n).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
    start = len(raw)
    raw += b'xref\n0 6\n0000000000 65535 f \n'
    raw += b''.join(f'{off:010d} 00000 n \n'.encode() for off in offsets[1:])
    return raw + b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(start).encode() + b'\n%%EOF\n'


class PersonalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.content = self.root / 'content'; self.content.mkdir()
        (self.content / 'manifest.json').write_text(json.dumps({'documents': [], 'map': {}}))
        self.data = self.root / 'data'
        self.start()

    def start(self):
        self.server = make_server(content_dir=self.content, data_dir=self.data, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def tearDown(self):
        self.stop(); self.tmp.cleanup()

    def request(self, path, body=None, headers=None, method=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=20)
        defaults = {'Origin': f'http://127.0.0.1:{self.server.server_port}', 'Content-Type': 'application/pdf',
                    'X-Personal-Rights': 'acknowledged', 'X-Document-Title': 'Personal fixture'}
        defaults.update(headers or {})
        connection.request(method or ('POST' if body is not None else 'GET'), path, body=body, headers=defaults)
        response = connection.getresponse(); raw = response.read(); status = response.status
        connection.close()
        return status, raw

    def test_corrupt_metadata_is_ignored_not_a_path_source(self):
        status, body = self.request('/api/personal/import', pdf_bytes())
        self.assertEqual(status, 201)
        doc = json.loads(body)
        meta = self.data / 'personal' / doc['sha256'] / 'metadata.json'
        for invalid in [[], dict(doc, text_file='../notes.txt'), dict(doc, personal=False), dict(doc, pages='1')]:
            meta.write_text(json.dumps(invalid))
            self.assertEqual(self.server.personal.documents(), [])

    def test_request_guards_and_malformed_pdf_never_publish(self):
        from app.personal import MAX_PDF
        cases = [({'Origin': 'https://attacker.invalid'}, pdf_bytes(), 403),
                 ({'Content-Type': 'text/plain'}, pdf_bytes(), 415),
                 ({'X-Personal-Rights': ''}, pdf_bytes(), 400),
                 ({'Content-Length': str(MAX_PDF + 1)}, b'', 413),
                 ({'Transfer-Encoding': 'chunked'}, b'', 400),
                 ({}, b'%PDF-1.4\ninvalid\n%%EOF', 400),
                 ({}, b'<html>not a PDF</html>', 400),
                 ({'X-Source-Id': 'http://127.0.0.1/secret'}, pdf_bytes(), 400),
                 ({'X-Document-Title': '%00bad'}, pdf_bytes(), 400)]
        for headers, body, expected in cases:
            with self.subTest(headers=headers, body=body[:20]):
                self.assertEqual(self.request('/api/personal/import', body, headers)[0], expected)
        self.assertEqual(json.loads(self.request('/api/library')[1])['documents'], [])
        self.assertFalse(any(self.data.rglob('original.pdf')))

    def test_collision_preserves_original_and_title_is_literal(self):
        raw = pdf_bytes()
        status, body = self.request('/api/personal/import', raw, {'X-Document-Title': '%3Cimg%20src=x%20onerror=alert(1)%3E/../../notes.txt'})
        self.assertEqual(status, 201, body)
        doc = json.loads(body)
        self.assertIn('<img', doc['title'])
        before = (self.data / doc['file']).read_bytes()
        self.assertEqual(self.request('/api/personal/import', raw)[0], 409)
        self.assertEqual((self.data / doc['file']).read_bytes(), before)
        for path in ['/personal/../notes.txt', '/personal/' + 'a' * 64 + '/metadata.json',
                     '/personal/%2e%2e/notes.txt', '/personal/' + 'a' * 64 + '/original.pdf/other']:
            self.assertNotEqual(self.request(path)[0], 200)

    def test_symlink_and_ancestor_swaps_are_confined_and_cleanup(self):
        from unittest.mock import patch
        import app.personal as module
        for swap_ancestor in (False, True):
            root = self.data / 'personal'
            if root.exists():
                root.rmdir()
            outside = self.root / ('outside-' + str(swap_ancestor)); outside.mkdir()
            original_extract = module.extract
            def swapped(raw):
                if swap_ancestor:
                    self.data.rename(self.root / 'moved-data')
                    self.data.symlink_to(outside, target_is_directory=True)
                else:
                    root.rename(self.data / 'moved-personal')
                    root.symlink_to(outside, target_is_directory=True)
                return original_extract(raw)
            with patch.object(module, 'extract', side_effect=swapped):
                with self.assertRaises(OSError):
                    module.PersonalLibrary(self.data).install(pdf_bytes(), 'race')
            self.assertEqual(list(outside.iterdir()), [])
            self.assertEqual(list(self.root.rglob('.import-*')), [])
            if swap_ancestor:
                self.data.unlink(); (self.root / 'moved-data').rename(self.data)
            else:
                root.unlink(); (self.data / 'moved-personal').rename(root)

    def test_write_failure_cleans_staging_and_descriptors(self):
        from unittest.mock import patch
        from app.personal import PersonalLibrary
        import os
        count = len(os.listdir('/proc/self/fd'))
        with patch('app.personal.os.fsync', side_effect=OSError('injected fsync')):
            with self.assertRaises(OSError):
                PersonalLibrary(self.data).install(pdf_bytes(), 'failure')
        self.assertEqual(list((self.data / 'personal').iterdir()), [])
        self.assertEqual(len(os.listdir('/proc/self/fd')), count)

    def test_boot_and_catalog_do_not_connect_to_network(self):
        from unittest.mock import patch
        self.stop()
        with patch('socket.socket.connect', side_effect=AssertionError('Unexpected outbound network')):
            self.start()
            self.assertEqual(self.server.personal.documents(), [])

    def test_staging_collision_does_not_remove_existing_directory(self):
        from unittest.mock import patch
        from app.personal import PersonalLibrary
        root = self.data / 'personal'; root.mkdir()
        target = root / ('.import-' + 'b' * 32); target.mkdir()
        with patch('app.personal.secrets.token_hex', return_value='b' * 32):
            with self.assertRaises(FileExistsError):
                PersonalLibrary(self.data).install(pdf_bytes(), 'collision')
        self.assertTrue(target.is_dir(), 'Existing staging belongs to another operation')

    def test_setup_is_generic_and_new_imports_have_no_catalog_provenance(self):
        status, raw = self.request('/api/setup')
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw), {'automatic_downloads': False, 'import_kind': 'local-personal-pdf'})
        for source in ['uv5r', 'ic2300h', 'ic718-basic', 'ic718-advanced', 'unknown']:
            self.assertEqual(self.request('/api/personal/import', pdf_bytes(), {'X-Source-Id': source})[0], 400)
        status, raw = self.request('/api/personal/import', pdf_bytes(), {'X-Source-Id': 'other'})
        self.assertEqual(status, 201, raw)
        doc = json.loads(raw)
        self.assertEqual(doc['url'], '')
        self.assertEqual(doc['source_id'], 'other')

    def test_existing_catalog_metadata_stays_readable_after_restart(self):
        status, raw = self.request('/api/personal/import', pdf_bytes())
        self.assertEqual(status, 201, raw)
        doc = json.loads(raw)
        # An older private import retains its owner's recorded provenance unchanged.
        doc.update(source_id='ic718-basic', url='https://example.invalid/legacy-owner-provenance')
        metadata = self.data / 'personal' / doc['sha256'] / 'metadata.json'
        metadata.write_text(json.dumps(doc))
        self.stop(); self.start()
        self.assertEqual(json.loads(self.request('/api/library')[1])['documents'], [doc])
        self.assertEqual(self.request('/' + doc['file']), (200, pdf_bytes()))

    def test_command_search_includes_personal_source(self):
        self.assertEqual(self.request('/api/personal/import', pdf_bytes())[0], 201)
        status, raw = self.request('/api/command?q=Quasar')
        self.assertEqual(status, 200, raw)
        self.assertTrue(json.loads(raw)['results'], raw)
        self.assertTrue(json.loads(raw)['results'][0]['id'].startswith('personal-'))

    def test_import_library_read_search_restart(self):
        raw = pdf_bytes()
        status, response = self.request('/api/personal/import', raw)
        self.assertEqual(status, 201, response)
        doc = json.loads(response)
        self.assertTrue(doc['personal'])
        self.assertEqual(doc['sha256'], hashlib.sha256(raw).hexdigest())
        for restart in (False, True):
            if restart:
                self.stop(); self.start()
            status, library = self.request('/api/library')
            self.assertEqual(json.loads(library)['documents'][0], doc)
            self.assertEqual(self.request('/' + doc['file']), (200, raw))
            self.assertEqual(self.request('/' + doc['file'], method='HEAD')[0], 200)
            status, result = self.request('/api/search?q=Quasar')
            self.assertEqual(json.loads(result)['results'][0]['id'], doc['id'])
        self.assertEqual(json.loads((self.content / 'manifest.json').read_text())['documents'], [])
        self.assertEqual((self.data / doc['file']).read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
