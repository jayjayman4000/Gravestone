"""Non-inference loopback fixtures exercising production overview transport."""
import threading
import time
import unittest
from unittest.mock import patch
from typing import Any

from app import overview
from test_retrieval import dripping_model_server, model_server


class OverviewTransportTests(unittest.TestCase):
    def test_dripped_headers_or_detached_body_obey_one_total_deadline(self):
        for stage, close in (('headers', False), ('body', False), ('body', True)):
            with self.subTest(stage=stage, close=close):
                before = {t.ident for t in threading.enumerate() if isinstance(t, threading.Timer)}
                with dripping_model_server(stage, connection_close=close) as (url, requests):
                    started = time.monotonic()
                    completion, status = overview._complete({'messages': []}, url, 0.12)
                    elapsed = time.monotonic() - started
                self.assertEqual(status, 'timeout')
                self.assertEqual(completion, '')
                self.assertLess(elapsed, 0.6, 'must interrupt reads, not just reject after receipt')
                self.assertEqual(len(requests), 1)
                self.assertEqual({t.ident for t in threading.enumerate() if isinstance(t, threading.Timer)}, before)

    def test_transport_rejects_redirects_invalid_json_or_oversized_response(self):
        cases: list[tuple[dict[str, Any], str]] = [
            ({'status': 503}, 'unavailable'),
            ({'status': 302, 'location': 'http://example.invalid/stolen'}, 'unavailable'),
            ({'raw': b'{broken'}, 'invalid-response'),
            ({'raw': b'x' * 32769}, 'invalid-response')]
        for options, status in cases:
            with self.subTest(options=str(options)[:100]):
                with model_server(**options) as (url, requests):
                    completion, actual = overview._complete({}, url, 1)
                self.assertEqual(actual, status)
                self.assertEqual(completion, '')
                self.assertEqual(len(requests), 1)

    def test_nonloopback_or_credential_urls_never_open_connection(self):
        for url in ('https://127.0.0.1:9', 'http://example.invalid',
                    'http://127.0.0.1:9/path', 'http://name:secret@127.0.0.1:9',
                    'http://127.0.0.1:9?query', 'http://192.0.2.1:9'):
            with self.subTest(url=url), patch.object(overview.http.client, 'HTTPConnection') as connection:
                self.assertEqual(overview._complete({}, url, 0.1), ('', 'invalid-url'))
                connection.assert_not_called()
