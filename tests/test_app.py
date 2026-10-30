"""Offline dashboard contract tests; fixtures are test-only, not source advice."""
import importlib.util
import json
import subprocess
import shutil
import sys
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.content = self.root / 'content'
        self.content.mkdir()
        self.data = self.root / 'private'
        self.server = None

    def start(self):
        self.assertIsNotNone(importlib.util.find_spec('app'), 'app package is not implemented')
        from app import make_server
        self.server = make_server(content_dir=self.content, data_dir=self.data, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(self.stop)

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join()
            self.server = None

    def request(self, path, body=None, headers=None, method=None):
        req = Request(self.base + path, data=body, headers=headers or {}, method=method)
        try:
            response = urlopen(req, timeout=3)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, response.headers, response.read()

    def manifest(self):
        document = {'id': 'fixture', 'title': 'Test <document>', 'publisher': 'Test publisher',
                    'url': 'https://example.invalid/source', 'file': 'original.pdf',
                    'sha256': '0' * 64, 'rights': 'test fixture', 'retrieved_at': 'test',
                    'text_file': 'text/source.txt', 'extraction_status': 'unverified'}
        self.content.joinpath('manifest.json').write_text(json.dumps({
            'documents': [document], 'map': {'file': 'maps/world.geojson'}}))
        return document

    def test_library_returns_unmodified_manifest_documents_and_map(self):
        document = self.manifest()
        self.start()
        status, _, body = self.request('/api/library')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['documents'], [document])
        self.assertEqual(json.loads(body)['map']['file'], 'maps/world.geojson')

    def test_search_returns_only_source_substrings_with_unverified_warning(self):
        document = self.manifest()
        source = 'Prefix: Mixed CASE needle <tag>\nSecond needle line.\nFinal.'
        (self.content / 'text').mkdir()
        (self.content / document['text_file']).write_text(source)
        self.start()
        status, _, body = self.request('/api/search?q=NEEDLE')
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result['warning'], 'Machine-extracted search preview — not verified; open the original document and read full context.')
        self.assertTrue(result['results'])
        for hit in result['results']:
            self.assertEqual(hit['id'], document['id'])
            self.assertEqual(hit['title'], document['title'])
            self.assertIn(hit['excerpt'], source)
            self.assertIn('needle', hit['excerpt'].lower())
        self.assertEqual(json.loads(self.request('/api/search?q=absent')[2])['results'], [])
        self.assertEqual(json.loads(self.request('/api/search?q=')[2])['results'], [])
        (self.content / document['text_file']).unlink()
        self.assertEqual(json.loads(self.request('/api/search?q=needle')[2])['results'], [])

    def test_notes_store_plain_text_atomically_and_survive_server_restart(self):
        self.start()
        self.assertEqual(json.loads(self.request('/api/notes')[2]), {'text': ''})
        text = '<img src=x onerror=alert(1)>\nPrivate note: 雪'
        status, _, body = self.request('/api/notes', json.dumps({'text': text}).encode(),
                                       {'Content-Type': 'application/json', 'Origin': self.base})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'text': text})
        self.assertEqual((self.data / 'notes.txt').read_text(), text)
        self.assertEqual([p.name for p in self.data.iterdir()], ['notes.txt'])
        self.stop()
        self.start()
        self.assertEqual(json.loads(self.request('/api/notes')[2]), {'text': text})

    def test_note_mutations_validate_route_origin_type_size_and_json(self):
        self.start()
        good = {'Content-Type': 'application/json', 'Origin': self.base}
        cases = [
            ('/api/nope', b'{"text":"x"}', good, 404),
            ('/api/notes', b'{"text":"x"}', {}, 403),
            ('/api/notes', b'{"text":"x"}', {**good, 'Origin': 'https://evil.invalid'}, 403),
            ('/api/notes', b'{"text":"x"}', {**good, 'Host': 'evil.invalid'}, 403),
            ('/api/notes', b'{"text":"x"}', {**good, 'Sec-Fetch-Site': 'cross-site'}, 403),
            ('/api/notes', b'{"text":"x"}', {**good, 'Content-Type': 'text/plain'}, 415),
            ('/api/notes', b'not json', good, 400),
            ('/api/notes', b'[' * 2000 + b']' * 2000, good, 400),
            ('/api/notes', b'{"text":"\\ud800"}', good, 400),
            ('/api/notes', b'{"text":42}', good, 400),
            ('/api/notes', b'[]', good, 400),
            ('/api/notes', b'{"other":"x"}', good, 400),
            ('/api/notes', b'{"text":"x", "extra":1}', good, 400),
            ('/api/notes', b'\xff', good, 400),
            ('/api/notes', json.dumps({'text': 'x' * (256 * 1024 + 1)}).encode(), good, 413),
            ('/api/notes', b'{}', {**good, 'Content-Length': '-1'}, 400),
            ('/api/notes', b'{}', {**good, 'Transfer-Encoding': 'chunked'}, 400),
        ]
        for path, body, headers, expected in cases:
            with self.subTest(expected=expected, headers=headers, path=path, body=body[:40]):
                self.assertEqual(self.request(path, body, headers)[0], expected)
        self.assertEqual(json.loads(self.request('/api/notes')[2]), {'text': ''})
        limit = 'x' * (256 * 1024)
        self.assertEqual(self.request('/api/notes', json.dumps({'text': limit}).encode(), good)[0], 200)

    def test_content_serves_original_bytes_but_blocks_traversal_and_symlinks(self):
        original = b'%PDF-1.7\nTest-only fixture\x00'
        (self.content / 'original.pdf').write_bytes(original)
        secret = self.root / 'secret.txt'
        secret.write_text('not public')
        (self.content / 'leak').symlink_to(secret)
        (self.content / 'linked-dir').symlink_to(self.root, target_is_directory=True)
        self.start()
        status, headers, body = self.request('/content/original.pdf')
        self.assertEqual(status, 200)
        self.assertEqual(body, original)
        self.assertEqual(headers['Content-Type'], 'application/pdf')
        for path in ['/content/../secret.txt', '/content/%2e%2e/secret.txt',
                     '/content/%2Fetc/passwd', '/content/leak', '/content/linked-dir/secret.txt',
                     '/content/%00', '/content/a%5c..%5csecret.txt']:
            with self.subTest(path=path):
                self.assertIn(self.request(path)[0], (400, 403, 404))
        self.assertEqual(self.request('/content/missing.pdf')[0], 404)
        self.assertEqual(self.request('/content/')[0], 404)

    def test_storage_rejects_symlinks_and_repository_data_directories(self):
        from app import make_server
        repo = Path(__file__).resolve().parents[1]
        for data in [repo / 'app' / 'private', self.content / 'private']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                server = make_server(content_dir=self.content, data_dir=data, port=0)
                server.server_close()
        real = self.root / 'real'
        real.mkdir()
        linked = self.root / 'linked'
        linked.symlink_to(real, target_is_directory=True)
        for data in [linked, linked / 'child']:
            with self.subTest(data=data), self.assertRaises((ValueError, OSError)):
                server = make_server(content_dir=self.content, data_dir=data, port=0)
                server.server_close()
        self.start()
        target = self.root / 'private-target'
        target.write_text('unchanged')
        (self.data / 'notes.txt').symlink_to(target)
        self.assertEqual(self.request('/api/notes')[0], 503)
        self.assertEqual(self.request('/api/notes', b'{"text":"overwrite"}',
                         {'Content-Type': 'application/json', 'Origin': self.base})[0], 503)
        self.assertEqual(target.read_text(), 'unchanged')
        self.assertTrue((self.data / 'notes.txt').is_symlink())
        (self.data / 'notes.txt').unlink()
        self.data.rmdir()
        self.data.symlink_to(real, target_is_directory=True)
        self.assertEqual(self.request('/api/notes')[0], 503)

    def test_manifest_failure_is_explicit_and_search_cannot_escape_content(self):
        self.start()
        for bad in [None, 'not json', '[]', '{"documents": "wrong"}']:
            if bad is not None:
                (self.content / 'manifest.json').write_text(bad)
            for endpoint in ['/api/library', '/api/search?q=secret']:
                with self.subTest(bad=bad, endpoint=endpoint):
                    self.assertEqual(self.request(endpoint)[0], 503)
        doc = self.manifest()
        outside = self.root / 'outside.txt'
        outside.write_text('secret needle')
        (self.content / 'alias.txt').symlink_to(outside)
        for text_file in ['../outside.txt', str(outside), 'alias.txt']:
            doc['text_file'] = text_file
            (self.content / 'manifest.json').write_text(json.dumps({'documents': [doc], 'map': {}}))
            with self.subTest(text_file=text_file):
                self.assertEqual(json.loads(self.request('/api/search?q=secret')[2])['results'], [])
        self.assertEqual(self.request('/api/search?q=' + 'x' * 201)[0], 400)
        (self.content / 'manifest.json').unlink()
        (self.content / 'manifest.json').symlink_to(outside)
        self.assertEqual(self.request('/api/library')[0], 503)
        (self.content / 'manifest.json').unlink()
        moved = self.root / 'moved'
        self.content.rename(moved)
        self.content.symlink_to(moved, target_is_directory=True)
        self.assertEqual(self.request('/api/library')[0], 503)
        self.assertEqual(self.request('/content/alias.txt')[0], 404)

    def test_loopback_only_and_response_security_headers(self):
        from app import make_server
        with self.assertRaises(ValueError):
            server = make_server(content_dir=self.content, data_dir=self.data, host='0.0.0.0', port=0)
            server.server_close()
        self.start()
        self.assertEqual(self.request('/api/notes', headers={'Host': 'evil.invalid'})[0], 403)
        status, headers, _ = self.request('/api/status')
        self.assertEqual(status, 200)
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn("default-src 'self'", headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['Referrer-Policy'], 'no-referrer')

    def test_module_cli_accepts_documented_options_and_serves(self):
        import selectors
        repo = Path(__file__).resolve().parents[1]
        help_result = subprocess.run([sys.executable, '-m', 'app', '--help'], cwd=repo,
                                     capture_output=True, text=True, timeout=5)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        for option in ['--data-dir', '--host', '--port']:
            self.assertIn(option, help_result.stdout)
        process = subprocess.Popen([sys.executable, '-m', 'app', '--data-dir', str(self.data),
                                    '--host', '127.0.0.1', '--port', '0'], cwd=repo,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert process.stdout is not None
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(5), 'CLI did not report startup')
            line = process.stdout.readline().strip()
            self.assertIn('http://127.0.0.1:', line)
            self.base = line.split()[-1]
            self.assertEqual(self.request('/api/status')[0], 200)
        finally:
            process.terminate()
            process.communicate(timeout=5)

    def test_dashboard_has_accessible_offline_library_search_and_notebook(self):
        self.start()
        status, _, body = self.request('/')
        self.assertEqual(status, 200)
        html = body.decode()
        for expected in ['<html lang="en">', 'Gravestone', '<main', 'href="#main"',
                         'id="library"', 'id="search-form"', 'id="notebook"',
                         'for="note-text"', 'aria-live="polite"', '/static/app.js', '/static/style.css']:
            self.assertIn(expected, html)
        self.assertNotIn('https://', html)
        status, _, script = self.request('/static/app.js')
        self.assertEqual(status, 200)
        self.assertIn(b'textContent', script)
        self.assertNotIn(b'innerHTML', script)
        self.assertNotIn(b'insertAdjacentHTML', script)
        self.assertIn(b'encodeURIComponent', script)
        self.assertIn('Machine-extracted search preview — not verified; open the original document and read full context.', script.decode())
        self.assertEqual(self.request('/static/style.css')[0], 200)
        self.assertIn(self.request('/static/../__init__.py')[0], (400, 404))

    def test_reference_map_has_keyboard_controls_and_local_renderer(self):
        self.start()
        html = self.request('/')[2].decode()
        for expected in ['id="world-map"', 'id="map-center-form"', 'for="latitude"',
                         'for="longitude"', 'id="zoom-in"', 'id="zoom-out"',
                         'id="map-reset"', 'not a navigation or street map', '/static/map.js']:
            self.assertIn(expected, html)
        status, _, body = self.request('/static/map.js')
        self.assertEqual(status, 200)
        for expected in [b'Polygon', b'MultiPolygon', b'pointermove', b'wheel', b'keydown']:
            self.assertIn(expected, body)

    @unittest.skipUnless(shutil.which('node'), 'Optional Node.js map-math verification')
    def test_map_math_projects_pan_zoom_and_validates_coordinates(self):
        path = Path(__file__).resolve().parents[1] / 'app/static/map.js'
        self.assertTrue(path.exists(), 'Map renderer not implemented')
        script = r"""
const assert = require('node:assert/strict');
const {projectPoint, changeView, parseCoordinates, rings, labelFits} = require(process.argv[1]);
assert.equal(typeof labelFits, 'function', 'Country labels need collision avoidance');
assert.equal(labelFits([10, 10, 60, 12], [[20, 15, 60, 12]]), false);
assert.equal(labelFits([10, 10, 60, 12], [[100, 100, 60, 12]]), true);
const view = {lon:0, lat:0, zoom:1};
assert.deepEqual(projectPoint(0, 0, view, 720, 360), [360, 180]);
assert.deepEqual(projectPoint(-180, 90, view, 720, 360), [0, 0]);
assert.deepEqual(projectPoint(180, -90, view, 720, 360), [720, 360]);
const moved = changeView(view, 20, 10, 2);
assert.deepEqual(projectPoint(20, 10, moved, 720, 360), [360, 180]);
assert.equal(moved.zoom, 2);
assert.equal(changeView(moved, 0, 100, 100).zoom, 16);
assert.equal(changeView(view, 0, 0, 0.001).zoom, 1);
assert.equal(changeView(view, 1000, 1000, 1).lat, 90);
assert.deepEqual(parseCoordinates('35.2', '-111.6'), {lat:35.2, lon:-111.6});
for (const args of [['','0'], ['90.1','0'], ['0','181'], ['abc','0'], ['Infinity','0']]) {
  assert.throws(() => parseCoordinates(...args));
}
assert.equal(rings({type:'Polygon',coordinates:[[[0,0],[1,1],[0,0]]]}).length, 1);
assert.equal(rings({type:'MultiPolygon',coordinates:[[[[0,0],[1,1],[0,0]]]]}).length, 1);
assert.deepEqual(rings({type:'Point',coordinates:[0,0]}), []);
console.log('Map projection, pan/zoom, coordinate bounds, Polygon/MultiPolygon: OK');
"""
        result = subprocess.run(['node', '-e', script, str(path)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_notebook_nonregular_storage_is_unavailable_not_empty(self):
        import os
        self.start()
        target = self.data / 'notes.txt'
        target.mkdir()
        self.assertEqual(self.request('/api/notes')[0], 503)
        target.rmdir()
        os.mkfifo(target)
        self.assertEqual(self.request('/api/notes')[0], 503)
        target.unlink()
        target.write_bytes(b'\xff')
        self.assertEqual(self.request('/api/notes')[0], 503)
        target.write_bytes(b'x' * (256 * 1024 + 1))
        self.assertEqual(self.request('/api/notes')[0], 503)

    def test_status_identifies_prototype_without_claiming_persistence(self):
        self.start()
        status, headers, body = self.request('/api/status')
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data['status'], 'prototype')
        self.assertIn('not verified', data['persistence_note'])
        self.assertEqual(headers['Content-Type'], 'application/json; charset=utf-8')


if __name__ == '__main__':
    unittest.main()
