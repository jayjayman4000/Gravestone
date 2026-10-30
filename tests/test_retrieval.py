"""Retrieval contracts. All source/model fixtures are test-only, not advice."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
import time
import unittest
from unittest.mock import patch
import inspect


@contextmanager
def model_server(completion='{"terms":["filtration"]}', *, delay=0, status=200, location=None, raw=None):
    """A real HTTP fixture, explicitly not actual model inference."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            requests.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            time.sleep(delay)
            body = raw if raw is not None else json.dumps({'choices': [{'message': {'content': completion}}]}).encode()
            self.send_response(status)
            if location:
                self.send_header('Location', location)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.documents = []

    def document(self, text, ident='fixture'):
        original = self.root / (ident + '.pdf')
        original.write_bytes(b'%PDF-fixture')
        (self.root / (ident + '.txt')).write_text(text, encoding='utf-8')
        doc = {'id': ident, 'title': 'Fixture title', 'publisher': 'Fixture publisher',
               'file': original.name, 'text_file': ident + '.txt'}
        self.documents.append(doc)
        self.manifest()
        return doc

    def manifest(self):
        (self.root / 'manifest.json').write_text(json.dumps({'documents': self.documents, 'map': {}}))

    def search(self, query, **kwargs):
        self.assertIsNotNone(importlib.util.find_spec('app.retrieval'), 'retrieval module missing')
        from app.retrieval import command_search
        kwargs.setdefault('model_url', 'http://example.invalid')
        return command_search(self.root, query, **kwargs)

    def test_keyword_search_returns_exact_page_substring_not_an_answer(self):
        pages = ['Unrelated first page.', 'Prefix. Mixed CASE water filter fixture.\nExact <tag> bytes.']
        doc = self.document('\f'.join(pages))
        result = self.search('How can I find a water filter?')
        self.assertEqual(result['query'], 'How can I find a water filter?')
        self.assertEqual(result['mode'], 'keyword-only')
        self.assertTrue(result['results'])
        hit = result['results'][0]
        self.assertEqual(hit['id'], doc['id'])
        self.assertEqual(hit['file'], doc['file'])
        self.assertEqual(hit['page'], 2)
        self.assertIn(hit['excerpt'], pages[1])
        self.assertIn('water', hit['matched_terms'])
        self.assertGreater(hit['score'], 0)
        self.assertIn('not verified', result['warning'])
        self.assertIn('original', result['warning'])
        self.assertNotIn('answer', result)
        json.dumps(result, allow_nan=False)

    def test_successful_loopback_roundtrip_only_proposes_terms(self):
        self.document('Private corpus marker. Water filtration fixture.')
        with model_server() as (url, requests):
            result = self.search('water filter', model_url=url)
        self.assertEqual(result['mode'], 'ai-assisted')
        self.assertEqual(result['model_status'], 'available')
        self.assertIn('filtration', result['terms'])
        self.assertEqual(len(requests), 1)
        path, payload = requests[0]
        self.assertEqual(path, '/v1/chat/completions')
        self.assertEqual(payload.get('response_format'), {'type': 'json_object'})
        self.assertIs(payload['chat_template_kwargs']['enable_thinking'], False)
        self.assertIn('/no_think', json.dumps(payload))
        self.assertNotIn('Private corpus marker', json.dumps(payload))
        self.assertIn('JSON', payload['messages'][0]['content'])
        self.assertIn('no advice', payload['messages'][0]['content'].lower())
        self.assertNotIn('choices', result)

    def test_transport_failures_fall_back_plainly_without_raw_completion(self):
        self.document('Water fixture.')
        cases = [({'completion': 'RAW invented advice'}, 'invalid-response'),
                 ({'raw': b'{broken'}, 'invalid-response'),
                 ({'completion': '{"terms":"water"}'}, 'invalid-response'),
                 ({'raw': b'x' * 32769}, 'invalid-response'),
                 ({'completion': '[' * 1500 + '0' + ']' * 1500}, 'invalid-response'),
                 ({'delay': 0.12}, 'timeout'),
                 ({'status': 503}, 'unavailable'),
                 ({'status': 302, 'location': 'http://example.invalid/stolen'}, 'unavailable')]
        for options, status in cases:
            with self.subTest(options=str(options)[:80]):
                with model_server(**options) as (url, requests):
                    result = self.search('water', model_url=url, timeout=0.03)
                self.assertEqual(result['mode'], 'keyword-only')
                self.assertEqual(result['model_status'], status)
                self.assertIn('Keyword-only', result['message'])
                self.assertTrue(result['results'])
                self.assertEqual(len(requests), 1)
                self.assertNotIn('RAW invented', json.dumps(result))

    def test_ranking_prefers_original_phrase_and_ai_cannot_add_unanchored_pages(self):
        pages = ['Water ' + 'filler ' * 180 + 'filter.',
                 'Prefix ' + 'filler ' * 180 + 'water filter EXACT preview.',
                 'Filtration fixture unrelated to the original query words.']
        self.document('\f'.join(pages))
        with model_server() as (url, _):
            result = self.search('water filter', model_url=url)
        self.assertEqual(result['results'][0]['page'], 2)
        self.assertIn('water filter EXACT', result['results'][0]['excerpt'])
        self.assertNotIn(3, [hit['page'] for hit in result['results']])
        self.assertEqual(len(result['results']), 2)
        for hit in result['results']:
            self.assertIn(hit['excerpt'], pages[hit['page'] - 1])
            self.assertLessEqual(len(hit['excerpt']), 600)
        self.assertIn('Partial', result['message'])

    def test_unsafe_or_unavailable_sources_report_library_gap(self):
        doc = self.document('Water fixture.')
        scenarios = [('file', '../outside.pdf'), ('text_file', '../outside.txt'),
                     ('file', '/etc/passwd'), ('text_file', '/etc/passwd'),
                     ('file', 'linked.pdf'), ('text_file', 'linked.txt'),
                     ('text_file', 'oversized.txt'), ('text_file', None)]
        (self.root / 'linked.pdf').symlink_to(self.root / doc['file'])
        (self.root / 'linked.txt').symlink_to(self.root / doc['text_file'])
        with (self.root / 'oversized.txt').open('wb') as stream:
            stream.truncate(16 * 1024 * 1024 + 1)
        for key, value in scenarios:
            with self.subTest(key=key, value=value):
                saved = doc.get(key)
                doc[key] = value
                self.manifest()
                result = self.search('water')
                doc[key] = saved
                self.assertEqual(result['results'], [])
                self.assertIn('Library gap', result['message'])
        (self.root / 'manifest.json').write_text('{invalid')
        self.assertIn('Library gap', self.search('water')['message'])

    def test_queries_without_bounded_meaningful_terms_do_not_call_model(self):
        self.document('Water fixture.')
        with model_server() as (url, requests):
            for query in ('', 'How can I?', 'x' * 49, 'x' * 2049, None):
                with self.subTest(query=str(query)[:30]):
                    result = self.search(query, model_url=url)
                    self.assertEqual(result['results'], [])
                    self.assertEqual(result['mode'], 'keyword-only')
                    self.assertEqual(result['model_status'], 'not-called')
                    self.assertIn('Enter', result['message'])
                    self.assertEqual(result['terms'], [])
            self.assertEqual(requests, [])

    def test_document_page_grouping_deduplicates_manifest_entries_and_caps_results(self):
        doc = self.document('Water water.\fWater filter.', 'same')
        self.documents.append(dict(doc))
        self.manifest()
        result = self.search('water')
        self.assertEqual(len(result['results']), 2)
        self.document('\f'.join('Water fixture ' + str(i) for i in range(20)), 'many')
        result = self.search('water')
        self.assertEqual(len(result['results']), 10)
        keys = [(hit['file'], hit['page']) for hit in result['results']]
        self.assertEqual(len(keys), len(set(keys)))

    def test_preview_chooses_query_relevant_cluster_even_without_full_phrase(self):
        source = 'Water introduction. ' + 'filler ' * 200 + 'Water near filter fixture.'
        self.document(source)
        result = self.search('water filter maintenance')
        self.assertIn('Water near filter', result['results'][0]['excerpt'])
        self.assertIn(result['results'][0]['excerpt'], source)

    def test_default_timeout_and_environment_configuration_for_cpu_model(self):
        from app.retrieval import command_search
        self.document('Water fixture.')
        with model_server() as (url, requests), patch.dict('os.environ', {'GRAVESTONE_MODEL_URL': url}):
            result = command_search(self.root, 'water', timeout=0.1)
        self.assertEqual(result['mode'], 'ai-assisted')
        self.assertEqual(len(requests), 1)
        self.assertEqual(inspect.signature(command_search).parameters['timeout'].default, 20)

    def test_remote_or_ambiguous_model_urls_are_rejected_before_connection(self):
        self.document('Water fixture.')
        urls = ['http://example.invalid', 'http://192.168.1.1', 'http://0.0.0.0',
                'http://127.0.0.1.example.invalid', 'http://2130706433', 'http://127.1',
                'http://user:password@127.0.0.1', 'http://127.0.0.1:bad',
                'http://127.0.0.1/path', 'http://127.0.0.1?x=1', 'file:///etc/passwd',
                'http://[::ffff:192.168.1.1]', 'https://example.invalid']
        with patch('app.retrieval.http.client.HTTPConnection') as connection:
            for url in urls:
                with self.subTest(url=url):
                    result = self.search('water', model_url=url)
                    self.assertEqual(result['mode'], 'keyword-only')
                    self.assertEqual(result['model_status'], 'invalid-url')
                    self.assertTrue(result['results'])
            connection.assert_not_called()

    def test_model_terms_are_untrusted_bounded_keywords_not_completion_text(self):
        self.document('Water filtration fixture.')
        completion = '<think>PRIVATE hidden reasoning</think>\n```json\n' + json.dumps({'terms': [
            'filtration', ' WATER ', '$(touch /tmp/no)', 'Drink boiled water',
            '<script>alert(1)</script>', 'water\nfilter', 'x' * 100, 'emergency',
            'purification', 'purification', 'sediment', 'clarification', 'surplus']}) + '\n```'
        with model_server(completion) as (url, _):
            result = self.search('water filter', model_url=url)
        self.assertEqual(result['mode'], 'ai-assisted')
        self.assertIn('filtration', result['terms'])
        self.assertIn('purification', result['terms'])
        self.assertLessEqual(len(result['terms']), 6)
        for forbidden in ('PRIVATE', 'drink boiled water', '<script>', '$(', 'emergency', 'surplus'):
            self.assertNotIn(forbidden, json.dumps(result))
        self.assertTrue(all(len(term) <= 48 and '\n' not in term for term in result['terms']))
