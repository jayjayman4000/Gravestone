"""Disposable loopback-only host wizard acceptance, stdlib only."""
import base64
import hashlib
import http.client
import io
import json
from pathlib import Path
import threading
import unittest
import zipfile
import host_prepare as prep


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(prep, 'make_server', None)), 'Local wizard server missing')
        self.server = prep.make_server(0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = '127.0.0.1:' + str(self.server.server_port)
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        conn.request(method, path, body, headers or {})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_local_browser_flow_preserves_bytes_and_uses_distinct_download_names(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        status, headers, page = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'Create private pack', page)
        self.assertIn(b'unknowns', page)
        self.assertIn('no-store', headers['Cache-Control'])
        raw = b'%PDF-1.4\nDisposable fixture\n%%EOF\n'
        equipment = dict.fromkeys(prep.FIELDS, '')
        equipment.update(category='tools', exact_model='<script>alert(1)</script>')
        payload = json.dumps({'equipment': [equipment], 'rights_acknowledged': True,
                              'pdfs': [{'name': '../../fixture.pdf', 'title': 'Fixture',
                                        'base64': base64.b64encode(raw).decode()}]})
        names = []
        for _ in range(2):
            status, headers, data = self.request('POST', '/pack', payload,
                {'Origin': 'http://' + self.host, 'Content-Type': 'application/json',
                 'X-Preparation-Token': self.server.token})
            self.assertEqual(status, 200, data)
            names.append(headers['Content-Disposition'])
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                doc = json.loads(archive.read('manifest.json'))['documents'][0]
                self.assertEqual(archive.read(doc['path']), raw)
                self.assertEqual(doc['sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(json.loads(archive.read('inventory.json'))['equipment'], [equipment])
        self.assertNotEqual(*names)
        self.assertEqual(self.request('GET', '/../../etc/passwd')[0], 404)

    def test_module_cli_starts_on_loopback(self):
        import subprocess
        import sys
        process = subprocess.Popen([sys.executable, '-u', '-m', 'host_prepare', '--port', '0'],
                                   cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            # A bounded subprocess exercises the actual entry point, not a mocked launcher.
            import select
            readable, _, _ = select.select([process.stdout], [], [], 4)
            self.assertTrue(readable, 'CLI did not print its local URL')
            line = process.stdout.readline()
            self.assertTrue(line.startswith('Open http://127.0.0.1:'), line)
        finally:
            process.terminate()
            process.communicate(timeout=4)

    def test_rejects_cross_origin_rebinding_and_oversized_body_before_read(self):
        good = {'Origin': 'http://' + self.host, 'Content-Type': 'application/json',
                'X-Preparation-Token': self.server.token}
        for changes, expected in [({'Origin': 'https://evil.example'}, 403),
                                  ({'Host': 'evil.example'}, 403),
                                  ({'X-Preparation-Token': 'wrong'}, 403),
                                  ({'Content-Type': 'text/plain'}, 415),
                                  ({'Content-Length': str(prep.MAX_REQUEST + 1)}, 413),
                                  ({'Transfer-Encoding': 'chunked'}, 400)]:
            with self.subTest(changes=changes):
                self.assertEqual(self.request('POST', '/pack', '{}', good | changes)[0], expected)
        for body in ['{', '[]', '{"equipment": [', '{"rights_acknowledged":true,"equipment":[],"pdfs":[null]}']:
            self.assertEqual(self.request('POST', '/pack', body, good)[0], 400)
        self.assertEqual(self.request('GET', '/', headers={'Host': 'evil.example'})[0], 403)


if __name__ == '__main__':
    unittest.main()
