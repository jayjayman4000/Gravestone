"""Overview tests use explicitly synthetic transport fixtures, not model inference."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class OverviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'originals').mkdir()
        (self.root / 'search').mkdir()
        (self.root / 'originals/source.pdf').write_bytes(b'%PDF-1.7\nTEST FIXTURE ONLY')
        self.pages = ['First fixture page.', '', 'Relevant fixture topic. Warning: fixture condition applies.']
        (self.root / 'search/source.txt').write_text('\f'.join(self.pages))
        self.doc = {'id': 'fixture', 'file': 'originals/source.pdf', 'title': 'Fixture',
                    'text_file': 'search/source.txt', 'pages': 3}
        self.save_manifest()

    def save_manifest(self):
        (self.root / 'manifest.json').write_text(json.dumps({'documents': [self.doc], 'map': {}}))

    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('app.overview'), 'Optional overview backend must exist')
        from app import overview
        return overview

    def test_evidence_id_selects_server_owned_exact_original_quote_and_page(self):
        overview = self.module()
        self.pages[2] = 'Relevant fixture topic.\n Warning:  fixture condition applies.  '
        (self.root / 'search/source.txt').write_text('\f'.join(self.pages))
        completion = json.dumps({'bullets': [{'text': 'Fixture topic with a condition.', 'evidence_id': 'E1'}]})
        with patch.object(overview, '_complete', return_value=(completion, 'available')):
            result = overview.generate_overview(self.root, 'fixture', query='topic')
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['bullets'], [{'text': 'Fixture topic with a condition.',
                                             'evidence_id': 'E1', 'page': 3, 'quote': self.pages[2]}])

    def test_opt_in_overview_has_separate_bounded_budget_for_baseline_cpu(self):
        overview = self.module()
        with patch.object(overview, '_complete', return_value=('', 'timeout')) as model:
            result = overview.generate_overview(self.root, 'fixture')
        self.assertGreaterEqual(model.call_args.args[2], 90)
        self.assertLessEqual(model.call_args.args[2], 120)
        self.assertEqual(result['status'], 'timeout')
        self.assertEqual(result['bullets'], [])

    def test_transport_does_not_silently_reduce_overview_budget_to_search_budget(self):
        import http.client
        import socket
        overview = self.module()
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1', 0))
            url = f'http://127.0.0.1:{reserved.getsockname()[1]}'
            with patch.object(overview.http.client, 'HTTPConnection', wraps=http.client.HTTPConnection) as connection:
                overview._complete({}, url, 120)
            self.assertEqual(connection.call_args.kwargs['timeout'], 120)

    def test_model_request_requires_complete_evidence_fields_in_json_schema(self):
        overview = self.module()
        with patch.object(overview, '_complete', return_value=('', 'timeout')) as model:
            overview.generate_overview(self.root, 'fixture', query='topic')
        response_format = model.call_args.args[0]['response_format']
        self.assertEqual(response_format['type'], 'json_schema')
        schema = response_format['json_schema']['schema']
        bullet = schema['properties']['bullets']['items']
        self.assertEqual(set(bullet['required']), {'text', 'evidence_id'})
        self.assertEqual(bullet['properties']['evidence_id']['enum'], ['E1'])
        self.assertEqual(set(bullet['properties']), {'text', 'evidence_id'})
        self.assertFalse(bullet['additionalProperties'])

    def test_small_model_overview_bounds_generation_to_one_brief_cited_point(self):
        overview = self.module()
        with patch.object(overview, '_complete', return_value=('', 'timeout')) as model:
            overview.generate_overview(self.root, 'fixture')
        payload = model.call_args.args[0]
        self.assertLessEqual(payload['max_tokens'], 96)
        schema = payload['response_format']['json_schema']['schema']
        self.assertEqual(schema['properties']['bullets']['maxItems'], 1)

    def test_malformed_manifest_text_path_types_fail_closed_without_inference(self):
        overview = self.module()
        for path in (3, None, True, [], {}, ['search/source.txt']):
            with self.subTest(text_file=path):
                self.doc['text_file'] = path
                self.save_manifest()
                with patch.object(overview, '_complete') as model:
                    result = overview.generate_overview(self.root, 'fixture')
                model.assert_not_called()
                self.assertEqual(result['status'], 'unavailable')
                self.assertEqual(result['bullets'], [])
                self.assertEqual(result['selected_pages'], [])

    def test_malformed_original_path_types_fail_closed_without_inference(self):
        overview = self.module()
        for path in (3, None, True, [], {}, ['originals/source.pdf']):
            with self.subTest(file=path):
                self.doc['file'] = path
                self.save_manifest()
                with patch.object(overview, '_complete') as model:
                    result = overview.generate_overview(self.root, 'fixture')
                model.assert_not_called()
                self.assertEqual(result['status'], 'unavailable')
                self.assertEqual(result['bullets'], [])

    def test_duplicate_json_fields_cannot_hide_altered_evidence(self):
        overview = self.module()
        for completion in (
                '{"bullets":[{"text":"Fixture topic.","evidence_id":"E999","evidence_id":"E1"}]}',
                '{"bullets":[],"bullets":[{"text":"Fixture topic.","evidence_id":"E1"}]}'):
            with self.subTest(completion=completion):
                with patch.object(overview, '_complete', return_value=(completion, 'available')):
                    result = overview.generate_overview(self.root, 'fixture', query='topic')
                self.assertEqual(result['status'], 'invalid-response')
                self.assertEqual(result['bullets'], [])

    def test_candidate_rank_never_invents_query_matches_at_prefix_cut(self):
        overview = self.module()
        # A real whole-word match admits the parent, but a second occurrence
        # cut from 'topicword' must not count toward candidate preference.
        prefix = 'Fixture topic. '
        text = prefix + ('x ' * overview.PAGE_CHARS)[:overview.PAGE_CHARS - len(prefix) - 5] + 'topicword'
        self.pages = [text, '', '']
        (self.root / 'search/source.txt').write_text('\f'.join(self.pages))
        with patch.object(overview, '_complete', return_value=('', 'timeout')) as model:
            overview.generate_overview(self.root, 'fixture', query='topic')
        fragments = json.loads(model.call_args.args[0]['messages'][1]['content'])['physical_page_fragments']
        # With only one real hit, the first four parts win; the final cut is
        # context, not a manufactured high-ranking evidence candidate.
        self.assertNotIn('evidence_id', fragments[0]['parts'][-1])

    def test_absent_source_reports_unavailable_without_calling_model(self):
        overview = self.module()
        with patch.object(overview, '_complete') as model:
            result = overview.generate_overview(self.root, 'missing')
        model.assert_not_called()
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['bullets'], [])

    def test_response_validation_enforces_the_same_small_output_limits_as_schema(self):
        overview = self.module()
        self.pages[2] = 'Relevant fixture topic. ' + 'x' * 300
        (self.root / 'search/source.txt').write_text('\f'.join(self.pages))
        valid = {'text': 'Fixture topic.', 'evidence_id': 'E1'}
        for bullets in ([valid, valid], [{**valid, 'text': 'x' * 161}],
                        [{**valid, 'quote': self.pages[2][:241]}]):
            with self.subTest(bullets=bullets):
                with patch.object(overview, '_complete', return_value=(json.dumps({'bullets': bullets}), 'available')):
                    result = overview.generate_overview(self.root, 'fixture', query='topic')
                self.assertEqual(result['status'], 'invalid-response')
                self.assertEqual(result['bullets'], [])

    def test_raw_output_bounds_cannot_be_bypassed_with_padding(self):
        overview = self.module()
        valid = {'text': 'Fixture topic.', 'evidence_id': 'E1'}
        for bullet in ({**valid, 'text': ' ' * 161 + 'x'},
                       {**valid, 'text': ' ' * 160},
                       {**valid, 'evidence_id': ' E1'},
                       {**valid, 'evidence_id': 'E1 '},
                       {**valid, 'evidence_id': 'e1'},
                       {**valid, 'evidence_id': True},
                       {**valid, 'evidence_id': []},
                       {**valid, 'evidence_id': 'E999'},
                       {**valid, 'quote': self.pages[2]},
                       {**valid, 'page': 3}):
            with self.subTest(bullet=bullet):
                with patch.object(overview, '_complete', return_value=(json.dumps({'bullets': [bullet]}), 'available')):
                    result = overview.generate_overview(self.root, 'fixture', query='topic')
                self.assertEqual(result['status'], 'invalid-response')
                self.assertEqual(result['bullets'], [])
        bullet = {**valid, 'text': ' ' * 159 + 'x'}
        with patch.object(overview, '_complete', return_value=(json.dumps({'bullets': [bullet]}), 'available')):
            result = overview.generate_overview(self.root, 'fixture', query='topic')
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['bullets'][0]['text'], bullet['text'])
        self.assertEqual(result['bullets'][0]['quote'], self.pages[2])

    def test_raw_bound_fix_preserves_minimum_nonpadding_quote_evidence(self):
        overview = self.module()
        self.pages = [' ' * 12 + 'x', '', '']
        (self.root / 'search/source.txt').write_text('\f'.join(self.pages))
        with patch.object(overview, '_complete') as model:
            result = overview.generate_overview(self.root, 'fixture')
        model.assert_not_called()
        self.assertEqual(result['status'], 'coverage-gap')
        self.assertEqual(result['bullets'], [])

    def test_candidates_are_small_deterministic_exact_parts_with_full_parent_context(self):
        overview = self.module()
        self.pages[2] = ('Unrelated context and conditions. ' * 25 +
                         'Relevant fixture topic. Warning: fixture condition applies.  ')
        (self.root / 'search/source.txt').write_text('\f'.join(self.pages))
        payloads = []
        for _ in range(2):
            with patch.object(overview, '_complete', return_value=('', 'timeout')) as model:
                overview.generate_overview(self.root, 'fixture', query='topic')
            payloads.append(model.call_args.args[0])
        self.assertEqual(payloads[0], payloads[1])
        fragments = json.loads(payloads[0]['messages'][1]['content'])['physical_page_fragments']
        self.assertEqual(len(fragments), 1)
        parts = fragments[0]['parts']
        self.assertEqual(''.join(part['text'] for part in parts), self.pages[2])
        candidates = [part for part in parts if 'evidence_id' in part]
        self.assertLessEqual(len(candidates), 4)
        self.assertTrue(any('topic' in part['text'] for part in candidates))
        for part in candidates:
            self.assertIn(part['text'], self.pages[2])
            self.assertGreaterEqual(len(part['text'].strip()), 12)
            self.assertLessEqual(len(part['text']), 240)
        ids = [part['evidence_id'] for part in candidates]
        schema = payloads[0]['response_format']['json_schema']['schema']
        self.assertEqual(schema['properties']['bullets']['items']['properties']['evidence_id']['enum'], ids)

    def test_nonexact_or_out_of_scope_evidence_never_becomes_available(self):
        # Existing fail-closed contract: model quote rewriting must not be
        # "repaired" into an apparently exact publisher quotation.
        overview = self.module()
        valid = {'text': 'Fixture topic.', 'page': 3, 'quote': self.pages[2]}
        variants = [[], [{**valid, 'page': 1}], [{**valid, 'page': True}],
                    [{**valid, 'quote': self.pages[2].replace('Warning:', 'Caution:')}],
                    [{**valid, 'extra': 'untrusted'}], [{**valid, 'quote': ''}]]
        for bullets in variants:
            with self.subTest(bullets=bullets):
                with patch.object(overview, '_complete', return_value=(json.dumps({'bullets': bullets}), 'available')):
                    result = overview.generate_overview(self.root, 'fixture', query='topic')
                self.assertEqual(result['status'], 'invalid-response')
                self.assertEqual(result['bullets'], [])
        for status in ('timeout', 'unavailable', 'invalid-response', 'invalid-url'):
            with self.subTest(status=status):
                with patch.object(overview, '_complete', return_value=('', status)):
                    result = overview.generate_overview(self.root, 'fixture')
                self.assertEqual(result['status'], status)
                self.assertEqual(result['bullets'], [])
                self.assertIn('no generated fallback', result['message'])

    def test_each_fragment_requires_every_meaningful_original_query_word(self):
        overview = self.module()
        cases = [
            ('diesel engine repair', ['Repair of a roof.', 'Diesel fuel storage.', 'Engine facts.']),
            ('How do I repair a diesel engine?', ['How do you prepare?', 'Repair of a roof.', 'Diesel engine facts.']),
            ('diesel engine repair procedure', ['Diesel engine repair only.', '', 'Repair procedure only.']),
        ]
        for query, pages in cases:
            with self.subTest(query=query):
                (self.root / 'search/source.txt').write_text('\f'.join(pages))
                with patch.object(overview, '_complete', return_value=('', 'timeout')) as model:
                    result = overview.generate_overview(self.root, 'fixture', query=query)
                model.assert_not_called()
                self.assertEqual(result['status'], 'coverage-gap')
                self.assertEqual(result['selected_pages'], [])
                self.assertEqual(result['bullets'], [])
                self.assertIn('coverage', result['message'].lower())
                self.assertIn('original', result['message'].lower())

    def test_eligible_bounded_third_fragment_is_considered_before_two_page_limit(self):
        overview = self.module()
        self.pages = ['Unrelated prefix. ' * 120 + 'Diesel engine repair.',
                      ' ' * overview.PAGE_CHARS + 'Diesel engine repair.',
                      'Diesel engine repair. Warning: synthetic fixture only.']
        (self.root / 'search/source.txt').write_text('\f'.join(self.pages))
        for query in ('diesel engine repair', 'How do I repair a diesel engine?'):
            with self.subTest(query=query):
                with patch.object(overview, '_complete', return_value=('', 'timeout')) as model:
                    result = overview.generate_overview(self.root, 'fixture', query=query, page=1)
                self.assertEqual(result['selected_pages'], [3])
                self.assertEqual(result['status'], 'timeout')
                fragments = json.loads(model.call_args.args[0]['messages'][1]['content'])['physical_page_fragments']
                self.assertEqual(fragments, [{'page': 3, 'parts': [{'text': self.pages[2], 'evidence_id': 'E1'}]}])
                self.assertEqual(model.call_args.args[0]['response_format']['json_schema']['schema']
                                 ['properties']['bullets']['items']['properties']['evidence_id']['enum'], ['E1'])

    def test_fragment_cutoff_cannot_manufacture_a_whole_query_word(self):
        overview = self.module()
        prefix = 'Diesel repair. '
        source = prefix + ' ' * (overview.PAGE_CHARS - len(prefix) - len('engine')) + 'enginehouse'
        self.pages = [source, '', 'No relevant fixture content.']
        (self.root / 'search/source.txt').write_text('\f'.join(self.pages))
        with patch.object(overview, '_complete', return_value=('', 'timeout')) as model:
            result = overview.generate_overview(self.root, 'fixture', query='diesel engine repair')
        model.assert_not_called()
        self.assertEqual(result['status'], 'coverage-gap')
        self.assertEqual(result['selected_pages'], [])

    def test_nonempty_query_without_meaningful_words_never_calls_model(self):
        overview = self.module()
        with patch.object(overview, '_complete', return_value=('', 'timeout')) as model:
            result = overview.generate_overview(self.root, 'fixture', query='How do I?')
        model.assert_not_called()
        self.assertEqual(result['status'], 'coverage-gap')
        self.assertEqual(result['bullets'], [])
        self.assertEqual(result['selected_pages'], [])

    def test_irrelevant_query_or_mismatched_page_index_never_calls_model(self):
        overview = self.module()
        with patch.object(overview, '_complete') as model:
            result = overview.generate_overview(self.root, 'fixture', query='unsupported-engine-repair')
        model.assert_not_called()
        self.assertEqual(result['status'], 'coverage-gap')
        self.assertEqual(result['selected_pages'], [])
        self.doc['pages'] = 4
        self.save_manifest()
        with patch.object(overview, '_complete') as model:
            result = overview.generate_overview(self.root, 'fixture')
        model.assert_not_called()
        self.assertEqual(result['status'], 'unavailable')

    def test_concurrent_overview_requests_fail_busy_without_queueing_inference(self):
        import threading
        overview = self.module()
        entered, release = threading.Event(), threading.Event()
        output = []
        def complete(*args):
            entered.set()
            release.wait(2)
            return '', 'timeout'
        with patch.object(overview, '_complete', side_effect=complete) as model:
            worker = threading.Thread(target=lambda: output.append(overview.generate_overview(self.root, 'fixture')))
            worker.start()
            self.assertTrue(entered.wait(1))
            try:
                second = overview.generate_overview(self.root, 'fixture')
                self.assertEqual(second['status'], 'busy')
                self.assertEqual(model.call_count, 1)
            finally:
                release.set()
                worker.join()

    def test_http_overview_is_disabled_unless_explicitly_enabled_before_reading_body(self):
        import io
        import os
        from email.message import Message
        from types import SimpleNamespace
        from unittest.mock import Mock
        overview = self.module()
        body = json.dumps({'id': 'fixture', 'query': 'topic', 'page': 1}).encode()
        for value in (None, '', '0', 'true', 'yes', '01', ' 1', '1 '):
            with self.subTest(environment=value), patch.dict(os.environ):
                os.environ.pop('GRAVESTONE_EXPERIMENTAL_OVERVIEW', None)
                if value is not None:
                    os.environ['GRAVESTONE_EXPERIMENTAL_OVERVIEW'] = value
                headers = Message()
                for name, value in {'Host': '127.0.0.1:8766', 'Origin': 'http://127.0.0.1:8766',
                                    'Content-Type': 'application/json', 'Content-Length': str(len(body))}.items():
                    headers[name] = value
                handler = SimpleNamespace(headers=headers, valid_host=lambda: True,
                                          rfile=Mock(wraps=io.BytesIO(body)), send_json=Mock(),
                                          app=SimpleNamespace(content_dir=self.root))
                with patch.object(overview, 'generate_overview', return_value={'status': 'available'}) as generate:
                    overview.handle_post(handler)
                status, result = handler.send_json.call_args.args
                self.assertEqual(status, 200)
                self.assertEqual(result['status'], 'disabled')
                self.assertEqual(result['bullets'], [])
                self.assertEqual(result['selected_pages'], [])
                self.assertEqual(result['warning'], overview.WARNING)
                self.assertIn('unready experimental overview', result['message'].lower())
                self.assertIn('withheld pending substantive quality validation', result['message'])
                self.assertIn('original PDF', result['message'])
                self.assertIn('search', result['message'])
                handler.rfile.read.assert_not_called()
                generate.assert_not_called()

    def test_disabled_http_overview_preserves_original_pdf_and_keyword_search(self):
        import http.client
        import os
        import threading
        from urllib.request import urlopen
        from app import make_server
        overview = self.module()
        with tempfile.TemporaryDirectory() as notes:
            server = make_server(content_dir=self.root, data_dir=notes, port=0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with patch.dict(os.environ), patch.object(overview, '_complete') as model:
                    os.environ.pop('GRAVESTONE_EXPERIMENTAL_OVERVIEW', None)
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
                    try:
                        # Deliberately send no declared body: disabled must not wait for it.
                        connection.putrequest('POST', '/api/overview')
                        connection.putheader('Origin', base)
                        connection.putheader('Content-Type', 'application/json')
                        connection.putheader('Content-Length', '100')
                        connection.endheaders()
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(json.loads(response.read())['status'], 'disabled')
                    finally:
                        connection.close()
                    with urlopen(base + '/content/originals/source.pdf', timeout=2) as response:
                        self.assertEqual(response.headers.get_content_type(), 'application/pdf')
                        self.assertEqual(response.read(), (self.root / 'originals/source.pdf').read_bytes())
                    with urlopen(base + '/api/search?q=topic', timeout=2) as response:
                        results = json.load(response)['results']
                    self.assertEqual(len(results), 1)
                    self.assertEqual(results[0]['id'], 'fixture')
                    self.assertEqual(results[0]['page'], 3)
                    self.assertEqual(results[0]['excerpt'], self.pages[2])
                    model.assert_not_called()
            finally:
                server.shutdown()
                server.server_close()
                worker.join()

    def test_real_loopback_protocol_fixture_and_same_origin_api(self):
        # Actual HTTP, synthetic completion; explicitly NOT inference evidence.
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from urllib.request import Request, urlopen
        from app import make_server
        captured = []
        quote = self.pages[2]

        class Fixture(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                captured.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                completion = json.dumps({'bullets': [{'text': 'Synthetic fixture overview.', 'evidence_id': 'E1'}]})
                raw = json.dumps({'choices': [{'message': {'content': completion}}]}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        model = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        app = make_server(content_dir=self.root, data_dir=self.root.parent / (self.root.name + '-notes'), port=0)
        threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (model, app)]
        for thread in threads:
            thread.start()
        try:
            base = f'http://127.0.0.1:{app.server_port}'
            with patch.dict('os.environ', {'GRAVESTONE_MODEL_URL': f'http://127.0.0.1:{model.server_port}',
                                           'GRAVESTONE_EXPERIMENTAL_OVERVIEW': '1'}):
                request = Request(base + '/api/overview', data=json.dumps({'id': 'fixture', 'query': 'topic', 'page': 1}).encode(),
                                  headers={'Content-Type': 'application/json', 'Origin': base})
                with urlopen(request, timeout=3) as response:
                    result = json.load(response)
            self.assertEqual(result['status'], 'available')
            self.assertEqual(result['bullets'][0]['quote'], quote)
            self.assertEqual(captured[0][0], '/v1/chat/completions')
            self.assertLessEqual(captured[0][1]['max_tokens'], 512)
            self.assertNotIn('notes', captured[0][1]['messages'][1]['content'])
        finally:
            for server in (model, app):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join()
            import shutil
            shutil.rmtree(app.data_dir)

    def test_api_rejects_cross_origin_and_malformed_requests_before_inference(self):
        import http.client
        import threading
        from app import make_server
        overview = self.module()
        with tempfile.TemporaryDirectory() as notes:
            server = make_server(content_dir=self.root, data_dir=notes, port=0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{server.server_port}'
            body = json.dumps({'id': 'fixture', 'query': 'topic', 'page': 1}).encode()
            cases = [
                ({'Origin': 'http://example.invalid'}, body, 403),
                ({'Origin': ''}, body, 403),
                ({'Host': 'example.invalid'}, body, 403),
                ({'Sec-Fetch-Site': 'cross-site'}, body, 403),
                ({'Sec-Fetch-Site': 'same-site'}, body, 403),
                ({'Content-Type': 'text/plain'}, body, 415),
                ({}, b'{}', 400),
                ({}, b'{broken', 400),
                ({}, json.dumps({'id': 'fixture', 'query': 'topic', 'page': True}).encode(), 400),
                ({}, json.dumps({'id': 'fixture', 'query': 'topic', 'page': 0}).encode(), 400),
                ({}, json.dumps({'id': 'fixture', 'query': 'x' * 201, 'page': 1}).encode(), 400),
                ({}, body[:-1] + b',"model_url":"http://example.invalid"}', 400),
                ({}, b' ' * 4097, 400),
                ({'Transfer-Encoding': 'chunked'}, body, 400),
            ]
            try:
                with patch.object(overview, '_complete') as model:
                    for enabled in ('0', '1'):
                        with patch.dict('os.environ', {'GRAVESTONE_EXPERIMENTAL_OVERVIEW': enabled}):
                            for overrides, raw, expected in cases:
                                with self.subTest(enabled=enabled, overrides=overrides, size=len(raw)):
                                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
                                    try:
                                        headers = {'Content-Type': 'application/json', 'Origin': base, **overrides}
                                        connection.request('POST', '/api/overview', raw, headers)
                                        response = connection.getresponse()
                                        # Disabled skips body validation, never origin/content-type checks.
                                        disabled = enabled == '0' and expected == 400
                                        self.assertEqual(response.status, 200 if disabled else expected)
                                        result = json.loads(response.read())
                                        if disabled:
                                            self.assertEqual(result['status'], 'disabled')
                                    finally:
                                        connection.close()
                    model.assert_not_called()
            finally:
                server.shutdown()
                server.server_close()
                worker.join()

    def test_manifest_paths_cannot_escape_to_other_source_or_private_data(self):
        overview = self.module()
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external)
            (outside / 'private.txt').write_text('PRIVATE SENTINEL fixture topic.')
            (outside / 'private.pdf').write_bytes(b'%PDF-1.7\nPRIVATE SENTINEL')
            (self.root / 'search/link.txt').symlink_to(outside / 'private.txt')
            (self.root / 'originals/link.pdf').symlink_to(outside / 'private.pdf')
            for field, path in (
                    ('text_file', 'search/../../private.txt'),
                    ('text_file', str(outside / 'private.txt')),
                    ('text_file', 'search/link.txt'),
                    ('text_file', 'search/../search/source.txt'),
                    ('file', 'originals/../../private.pdf'),
                    ('file', 'originals/link.pdf')):
                with self.subTest(field=field, path=path):
                    original = self.doc[field]
                    self.doc[field] = path
                    self.save_manifest()
                    try:
                        with patch.object(overview, '_complete') as model:
                            result = overview.generate_overview(self.root, 'fixture', query='topic')
                        model.assert_not_called()
                        self.assertEqual(result['status'], 'unavailable')
                        self.assertEqual(result['bullets'], [])
                        self.assertNotIn('PRIVATE SENTINEL', json.dumps(result))
                    finally:
                        self.doc[field] = original
                        self.save_manifest()

    def test_source_scoped_quote_backed_overview_is_explicitly_unverified(self):
        overview = self.module()
        completion = json.dumps({'bullets': [{'text': 'Fixture topic with a condition.',
                                              'evidence_id': 'E1'}]})
        with patch.object(overview, '_complete', return_value=(completion, 'available')) as model:
            result = overview.generate_overview(self.root, 'fixture', query='topic', page=1)
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['file'], self.doc['file'])
        self.assertIn(3, result['selected_pages'])
        self.assertEqual(result['bullets'][0]['quote'], self.pages[2])
        self.assertIn('AI-generated', result['warning'])
        self.assertIn('unverified', result['warning'])
        self.assertIn('not the complete PDF', result['scope'])
        self.assertIn('at most 2 physical PDF pages', result['scope'])
        self.assertIn('first 1800 characters', result['scope'])
        self.assertIn('Warning: fixture condition applies.', model.call_args.args[0]['messages'][1]['content'])
        self.assertEqual((self.root / 'originals/source.pdf').read_bytes(), b'%PDF-1.7\nTEST FIXTURE ONLY')
