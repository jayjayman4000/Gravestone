"""HTTP integration for source-only command retrieval; model failure is explicit."""
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from app import make_server

class CommandAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.content = base / 'content'
        self.content.mkdir()
        (self.content / 'fixture.pdf').write_bytes(b'%PDF-fixture')
        (self.content / 'fixture.txt').write_text('Water index fixture.\n\f\nPower index fixture.\n')
        (self.content / 'manifest.json').write_text(json.dumps({'documents': [
            {'id': 'fixture', 'title': 'Test fixture', 'publisher': 'Test', 'file': 'fixture.pdf', 'text_file': 'fixture.txt'}], 'map': {}}))
        self.env = patch.dict(os.environ, {'GRAVESTONE_MODEL_URL': 'http://127.0.0.1:9'})
        self.env.start()
        self.server = make_server(content_dir=self.content, data_dir=base / 'notes', port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.env.stop()
        self.temp.cleanup()
    def get(self, path):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request('GET', path)
        result = conn.getresponse()
        status, body = result.status, json.loads(result.read())
        conn.close()
        return status, body
    def test_command_exposes_exact_source_results_and_honest_model_fallback(self):
        status, body = self.get('/api/command?q=water')
        self.assertEqual(status, 200)
        self.assertEqual(body['mode'], 'keyword-only')
        self.assertEqual(body['query'], 'water')
        self.assertTrue(body['results'])
        self.assertIn(body['results'][0]['excerpt'], (self.content / 'fixture.txt').read_text())
        self.assertEqual(body['results'][0]['page'], 1)
        self.assertIn('not verified', body['warning'])
        for query in ('/api/command', '/api/command?q=', '/api/command?q=' + 'a'*201):
            self.assertEqual(self.get(query)[0], 400)
        status, body = self.get('/api/command?q=zyxnonexistenttopic')
        self.assertEqual(status, 200)
        self.assertEqual(body['results'], [])

if __name__ == '__main__':
    unittest.main()
