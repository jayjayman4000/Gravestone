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
def model_server(completion='{"terms":["filtration"]}', *, delay=0.0, status=200, location=None, raw=None):
    """A real HTTP fixture, explicitly not actual model inference."""
    requests = []
    stop = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            requests.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            if stop.wait(delay):
                return
            body = raw if raw is not None else json.dumps({'choices': [{'message': {'content': completion}}]}).encode()
            try:
                self.send_response(status)
                if location:
                    self.send_header('Location', location)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = False
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01))
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', requests
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if thread.is_alive():
            raise AssertionError('HTTP fixture did not stop')


@contextmanager
def dripping_model_server(stage, *, connection_close=False):
    """Loopback HTTP timing fixture, NOT actual model inference.

    Each 10 ms drip is below the client's 120 ms inactivity budget, but the
    complete response takes over 700 ms. Stop/join all fixture threads even
    when an assertion fails or the client shuts down mid-header/body.
    """
    stop = threading.Event()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            body = json.dumps({'choices': [{'message': {'content': '{"terms":["filtration"]}'}}]}).encode()
            try:
                self.wfile.write(b'HTTP/1.1 200 OK\r\n')
                if stage == 'headers':
                    for _ in range(80):
                        self.wfile.write(b'X-Fixture: drip\r\n')
                        self.wfile.flush()
                        if stop.wait(0.01):
                            return
                self.wfile.write(b'Content-Length: ' + str(len(body)).encode() + b'\r\n')
                if connection_close:
                    self.wfile.write(b'Connection: close\r\n')
                self.wfile.write(b'\r\n')
                chunks = [body[i:i + 1] for i in range(len(body))] if stage == 'body' else [body]
                for chunk in chunks:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    if stage == 'body' and stop.wait(0.01):
                        return
            except (BrokenPipeError, ConnectionResetError):
                pass  # Expected when the deadline interrupts the client socket.

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = False  # server_close must join every owned handler.
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01))
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', requests
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if thread.is_alive():
            raise AssertionError('HTTP timing fixture did not stop')


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

    def test_model_roundtrip_without_new_accepted_terms_is_keyword_only(self):
        self.document('Water fixture.')
        for terms in ([], ['water', 'safe', 'drink boiled water', 42]):
            with self.subTest(terms=terms), model_server(json.dumps({'terms': terms})) as (url, requests):
                result = self.search('water', model_url=url)
            self.assertEqual(result['model_status'], 'available')
            self.assertEqual(result['mode'], 'keyword-only')
            self.assertEqual(result['expansion_terms'], [])
            self.assertIn('no accepted new keywords', result['message'])
            self.assertEqual(len(requests), 1)

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

    def test_total_deadline_interrupts_dripped_headers_and_body(self):
        source = 'Water fixture. Untouched original page.'
        self.document(source)
        for stage, connection_close in (('headers', False), ('body', False), ('body', True)):
            with self.subTest(stage=stage, connection_close=connection_close):
                with dripping_model_server(stage, connection_close=connection_close) as (url, requests):
                    start = time.monotonic()
                    result = self.search('water', model_url=url, timeout=0.12)
                    elapsed = time.monotonic() - start
                self.assertEqual(result['model_status'], 'timeout', f'elapsed={elapsed:.3f}s')
                self.assertLess(elapsed, 0.6, 'deadline must interrupt read, not just reject a late response')
                self.assertEqual(result['mode'], 'keyword-only')
                self.assertEqual(result['terms'], ['water'])
                self.assertEqual(result['expansion_terms'], [])
                self.assertEqual(len(requests), 1)
                self.assertEqual(result['results'][0]['excerpt'], source)
                self.assertNotIn('answer', result)
                self.assertNotIn('choices', result)
                self.assertNotIn('filtration', json.dumps(result))

    def test_deadline_resources_close_on_success_and_failure(self):
        # Instrument real sockets/timers without replacing their I/O behavior.
        from app import retrieval
        original_connection = retrieval.http.client.HTTPConnection
        original_timer = threading.Timer
        sockets, timers = [], []

        class TrackingConnection(original_connection):
            def connect(self):
                super().connect()
                sockets.append(self.sock)

        def track_timer(*args, **kwargs):
            timer = original_timer(*args, **kwargs)
            timers.append(timer)
            return timer

        self.document('Water fixture.')
        cases = [({}, 'available'), ({'status': 503}, 'unavailable'),
                 ({'raw': b'{broken'}, 'invalid-response'),
                 ({'raw': b'x' * 32769}, 'invalid-response'),
                 ({'delay': 0.2}, 'timeout')]
        with patch('app.retrieval.http.client.HTTPConnection', TrackingConnection), \
                patch('app.retrieval.threading.Timer', track_timer):
            for options, status in cases:
                with self.subTest(status=status, options=str(options)[:40]):
                    with model_server(**options) as (url, _):
                        result = self.search('water', model_url=url, timeout=0.12)
                        self.assertEqual(result['model_status'], status)
                        self.assertTrue(all(not timer.is_alive() for timer in timers))
                        self.assertTrue(all(sock.fileno() == -1 for sock in sockets))
            with dripping_model_server('body', connection_close=True) as (url, _):
                result = self.search('water', model_url=url, timeout=0.12)
                self.assertEqual(result['model_status'], 'timeout')
                self.assertTrue(all(not timer.is_alive() for timer in timers))
                self.assertTrue(all(sock.fileno() == -1 for sock in sockets))
        self.assertEqual(len(timers), len(cases) + 1)
        self.assertEqual(len(sockets), len(cases) + 1)

    def test_concurrent_deadlines_do_not_interrupt_another_search(self):
        from concurrent.futures import ThreadPoolExecutor
        self.document('Water fixture.')
        baseline_threads = set(threading.enumerate())
        with dripping_model_server('headers') as (slow_url, _), \
                model_server(delay=0.25) as (normal_url, _), ThreadPoolExecutor(max_workers=2) as pool:
            slow = pool.submit(self.search, 'water', model_url=slow_url, timeout=0.12)
            normal = pool.submit(self.search, 'water', model_url=normal_url, timeout=1)
            self.assertEqual(slow.result(timeout=2)['model_status'], 'timeout')
            self.assertEqual(normal.result(timeout=2)['model_status'], 'available')
        self.assertEqual(set(threading.enumerate()) - baseline_threads, set())

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
        self.assertEqual(len(result['results']), 1)
        self.assertEqual([hit['page'] for hit in result['related_results']], [1])
        self.assertEqual(result['related_results'][0]['missing_terms'], ['filter'])
        for hit in result['results'] + result['related_results']:
            self.assertNotEqual(hit['page'], 3)
            self.assertIn(hit['excerpt'], pages[hit['page'] - 1])
            self.assertLessEqual(len(hit['excerpt']), 600)
        self.assertIn('Partial', result['message'])

    def test_incomplete_query_coverage_is_related_only_not_a_primary_result(self):
        # Test-only text, not an invented installed repair reference. The same
        # rule must work for arbitrary domains, not a publisher/word blacklist.
        self.document('Fixture insurance repair wording.\f'
                      'Vehicle fixture. ' + 'layout ' * 150 + 'Repair fixture.')
        for query in ('engine repair', 'vehicle repair', 'quantum repair'):
            with self.subTest(query=query):
                result = self.search(query)
                self.assertEqual(result['results'], [])
                self.assertTrue(result['related_results'])
                self.assertEqual(result['coverage']['status'], 'no-local-coverage')
                self.assertEqual(result['coverage']['required_terms'], query.split())
                self.assertIn('Library gap', result['message'])
                self.assertIn('not proof', result['message'])

    def test_preview_cut_cannot_create_query_word_from_a_longer_word(self):
        source = 'xengine' + ' ' * 94 + 'repair'
        self.document(source)
        result = self.search('engine repair')
        self.assertEqual(result['results'], [])
        hit = result['related_results'][0]
        self.assertEqual(hit['local_matched_terms'], ['repair'])
        self.assertEqual(hit['missing_terms'], ['engine'])
        self.assertNotRegex(hit['excerpt'], r'(?<!\w)engine(?!\w)')
        self.assertIn(hit['excerpt'], source)

    def test_preview_end_cannot_create_query_word_from_a_longer_word(self):
        source = 'repair' + ' ' * 588 + 'engineered'
        self.document(source)
        result = self.search('engine repair')
        self.assertEqual(result['results'], [])
        hit = result['related_results'][0]
        self.assertEqual(hit['local_matched_terms'], ['repair'])
        self.assertEqual(hit['missing_terms'], ['engine'])
        self.assertNotRegex(hit['excerpt'], r'(?<!\w)engine(?!\w)')
        self.assertIn(hit['excerpt'], source)

    def test_long_query_can_miss_one_word_without_hiding_the_qualifier(self):
        self.document('Prepare infant formula using tap water. Test-only fixture.')
        result = self.search('prepare infant formula tap water unsafe')
        self.assertTrue(result['results'])
        self.assertEqual(result['results'][0]['missing_terms'], ['unsafe'])
        self.assertEqual(result['coverage']['status'], 'partial-query-match')
        self.assertIn('Missing query words', result['message'])
        self.assertIn('not proof', result['message'])
        self.assertNotIn('Library gap', result['message'])

    def test_local_coverage_threshold_is_domain_independent_and_bounded(self):
        self.document('Alpha beta gamma delta. Test-only fixture.')
        cases = [
            ('alpha', True),
            ('alpha missing', False),
            ('alpha beta missing', False),
            ('alpha beta gamma missing', True),
            ('alpha beta missing absent', False),
            ('alpha beta gamma delta missing', True),
            ('alpha beta gamma missing absent', False),
        ]
        for query, primary in cases:
            with self.subTest(query=query):
                result = self.search(query)
                self.assertEqual(bool(result['results']), primary)
                for hit in result['results']:
                    self.assertLessEqual(len(hit['missing_terms']), 1)
                    if len(result['coverage']['required_terms']) <= 3:
                        self.assertEqual(hit['missing_terms'], [])
                for hit in result['related_results']:
                    self.assertLess(len(hit['local_matched_terms']),
                                    result['coverage']['minimum_local_terms'])

    def test_search_scaffolding_is_not_a_required_source_word(self):
        source = 'Safe drinking water fixture.'
        self.document(source)
        result = self.search('Find safe drinking water guidance')
        self.assertTrue(result['results'])
        self.assertEqual(result['coverage']['required_terms'], ['safe', 'drinking', 'water'])
        self.assertEqual(result['coverage']['status'], 'local-query-match')
        self.assertEqual(result['results'][0]['excerpt'], source)

    def test_hit_coverage_is_measured_in_preview_not_elsewhere_on_page(self):
        self.document('Vehicle fixture. ' + 'layout ' * 150 + 'Repair fixture.')
        result = self.search('vehicle repair')
        hit = result['related_results'][0]
        self.assertEqual(hit['matched_terms'], ['vehicle', 'repair'])
        self.assertEqual(hit['local_matched_terms'], ['repair'])
        self.assertEqual(hit['missing_terms'], ['vehicle'])
        self.assertNotIn('installed', result['coverage'])
        self.assertNotIn('not-installed', json.dumps(result))

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
                    self.assertEqual(result['related_results'], [])
                    self.assertEqual(result['coverage'], {'status': 'invalid-query', 'required_terms': []})
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
        self.assertEqual(result['results'], [])
        hit = result['related_results'][0]
        self.assertIn('Water near filter', hit['excerpt'])
        self.assertIn(hit['excerpt'], source)
        self.assertEqual(hit['missing_terms'], ['maintenance'])
        self.assertEqual(result['coverage']['status'], 'no-local-coverage')

    def test_local_original_coverage_outweighs_scattered_whole_page_matches(self):
        self.document('Safe home. ' + 'layout ' * 150 + 'Drinking water supplies.\f'
                      'Water for drinking must be safe. Source passage.')
        result = self.search('safe drinking water')
        self.assertEqual(result['results'][0]['page'], 2)
        self.assertIn('Water for drinking must be safe.', result['results'][0]['excerpt'])

    def test_proximity_uses_later_occurrences_and_keeps_whole_cluster_in_preview(self):
        source = ('Water topic. ' + 'layout ' * 120 + 'Drinking topic. '
                  + 'layout ' * 120 + 'Safe topic. ' + 'layout ' * 120
                  + 'Water for drinking must be safe. Exact later cluster.')
        self.document(source)
        result = self.search('safe drinking water')
        hit = result['results'][0]
        self.assertIn('Water for drinking must be safe.', hit['excerpt'])
        self.assertIn(hit['excerpt'], source)
        self.assertLessEqual(len(hit['excerpt']), 600)

    def test_phrase_layout_whitespace_does_not_demote_equivalent_source(self):
        self.document('Safe Minimum Internal  \nTemperature Chart\nSource table.\f'
                      'See Safe Minimum Internal Temperature Chart in another section.')
        result = self.search('safe minimum internal temperature chart')
        self.assertEqual(result['results'][0]['page'], 1)
        self.assertEqual(result['results'][0]['score'], result['results'][1]['score'])
        self.assertIn('Internal  \nTemperature', result['results'][0]['excerpt'])

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
