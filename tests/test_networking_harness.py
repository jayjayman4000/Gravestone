"""QA-only harness checks; these do not claim a real VM boot or browser proof."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_harness():
    path = ROOT / 'scripts/test-networking.py'
    if not path.exists():
        raise AssertionError('network acceptance harness is missing')
    spec = importlib.util.spec_from_file_location('networking_harness', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NetworkingHarnessTests(unittest.TestCase):
    def test_qemu_uses_original_readonly_iso_and_e1000_without_smoke(self):
        h = load_harness()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            iso = root / 'original.iso'; iso.touch()
            command = h.vm_command(iso, root)
            self.assertIn('user,id=acceptance,ipv6=off', command)
            self.assertIn('e1000,netdev=acceptance,mac=52:54:00:12:34:56', command)
            self.assertIn(f'file={iso},format=raw,media=cdrom,readonly=on', command)
            self.assertIn(str(root / 'vmlinuz'), command)
            self.assertIn('systemd.debug_shell=ttyS0', ' '.join(command))
            self.assertNotIn('gravestone.smoke=1', ' '.join(command))
            self.assertNotIn('hostfwd', ' '.join(command))
            self.assertNotIn('-enable-kvm', command)
            for bad in [root / 'absent', root / 'comma,iso']:
                bad.touch()
                if bad.name == 'absent':
                    bad.unlink()
                with self.assertRaises(ValueError):
                    h.vm_command(bad, root)
            link = root / 'link'; link.symlink_to(iso)
            with self.assertRaises(ValueError):
                h.vm_command(link, root)

    def test_guest_offline_and_online_assertions_fail_closed(self):
        h = load_harness()
        namespace: dict[str, Any] = {'__name__': 'guest_unit_test'}
        source = h.guest_program('a' * 64)
        exec(compile(source, '<network-guest>', 'exec'), namespace)
        offline = {'addresses': [{'ifname': 'eth0', 'addr_info': [
            {'family': 'inet6', 'scope': 'link', 'local': 'fe80::1'}]}],
            'routes4': [], 'routes6': []}
        namespace['assert_offline'](offline)
        import copy
        for key in ('routes4', 'routes6', 'addresses'):
            bad = copy.deepcopy(offline)
            if key == 'addresses':
                bad[key][0]['addr_info'].append({'family': 'inet', 'scope': 'global', 'local': '10.0.2.15'})
            else:
                bad[key] = [{'dst': 'default', 'gateway': '10.0.2.2'}]
            with self.subTest(key=key), self.assertRaises(AssertionError):
                namespace['assert_offline'](bad)
        online = {'addresses': [{'ifname': 'eth0', 'addr_info': [
            {'family': 'inet', 'scope': 'global', 'local': '10.0.2.15'}]}],
            'routes4': [{'dst': 'default', 'gateway': '10.0.2.2', 'dev': 'eth0'}], 'routes6': []}
        self.assertEqual(namespace['online_interface'](online), 'eth0')
        self.assertIsNone(namespace['online_interface'](offline))
        self.assertIn('/usr/local/sbin/gravestone-network', source)
        self.assertNotIn("'nmcli', 'connection', 'up'", source)
        self.assertNotIn('systemctl start', source)
        self.assertIn('/api/personal/import', source)
        self.assertIn('/api/search?q=Quasar', source)
        self.assertIn('timeout=', source)

    def test_fixture_serves_only_pdf_and_records_every_hit(self):
        import urllib.request
        import urllib.error
        h = load_harness()
        with h.fixture_server(port=0) as server:
            url = f'http://127.0.0.1:{server.server_port}'
            with urllib.request.urlopen(url + '/fixture.pdf', timeout=2) as response:
                self.assertEqual(response.headers['Content-Type'], 'application/pdf')
                self.assertEqual(response.read(), h.pdf_bytes())
            self.assertEqual(server.hits, ['/fixture.pdf'])
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(url + '/baseline.pdf', timeout=2)
            self.assertEqual(server.hits, ['/fixture.pdf', '/baseline.pdf'])
        self.assertTrue(h.pdf_bytes().startswith(b'%PDF-1.4'))
        self.assertIn(b'Quasar', h.pdf_bytes())

    def test_iso_pin_is_required_and_strict(self):
        from unittest.mock import patch
        h = load_harness()
        for value in ('', 'A' * 64, 'a' * 63, 'a' * 65, 'a' * 64 + '\n'):
            with patch.dict('os.environ', {'GRAVESTONE_TEST_ISO_SHA256': value}):
                with self.assertRaises(ValueError):
                    h.expected_iso_digest()
        with patch.dict('os.environ', {'GRAVESTONE_TEST_ISO_SHA256': '1' * 64}):
            self.assertEqual(h.expected_iso_digest(), '1' * 64)

    def test_serial_upload_is_bounded_and_roundtrips_source(self):
        import base64
        import re
        h = load_harness()
        source = h.guest_program('b' * 64)
        lines = h.shell_upload(source)
        self.assertTrue(all(len(line) < 1000 for line in lines))
        chunks = [re.search(r"printf %s '([A-Za-z0-9+/=]+)'", line).group(1)
                  for line in lines[1:-1]]
        self.assertEqual(base64.b64decode(''.join(chunks)).decode(), source)
        self.assertIn('systemctl poweroff', lines[-1])

    def test_serial_drains_after_child_exit_and_enforces_deadline(self):
        import json
        import socket
        import subprocess
        import sys
        import time
        h = load_harness()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 's'
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(str(path)); listener.listen(1)
            child = subprocess.Popen([sys.executable, '-c',
                "import socket,sys; s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); "
                "s.sendall(b'NETWORK_RESULT={\"ok\":true}\\nPower down\\n'); s.close()", str(path)])
            conn, _ = listener.accept()
            try:
                self.assertEqual(child.wait(timeout=3), 0)
                text = h.collect_serial(child, conn, time.monotonic() + 2, '', root / 'serial.log')
                self.assertIn('Power down', text)
                self.assertEqual(json.loads(text.splitlines()[0].split('=', 1)[1]), {'ok': True})
            finally:
                conn.close(); listener.close()
            left, right = socket.socketpair()
            try:
                start = time.monotonic()
                with self.assertRaises(TimeoutError):
                    h.collect_serial(child, left, start + .1, '', root / 'timeout.log')
                self.assertLess(time.monotonic() - start, 1)
            finally:
                left.close(); right.close()

    def test_result_requires_one_marker_exact_hits_hash_and_clean_exit(self):
        import json
        h = load_harness()
        record = {'download_sha256': 'c' * 64, 'local_read_after_offline': True,
                  'search_after_offline': True, 'graphical_browser_proved': False}
        text = 'NETWORK_RESULT=' + json.dumps(record) + '\nPower down\n'
        self.assertEqual(h.validate_result(text, 0, ['/fixture.pdf'], 'c' * 64), record)
        for changed_text, code, hits, digest in [
            ('Power down', 0, ['/fixture.pdf'], 'c' * 64),
            (text + text, 0, ['/fixture.pdf'], 'c' * 64),
            (text, 1, ['/fixture.pdf'], 'c' * 64),
            (text.replace('Power down', ''), 0, ['/fixture.pdf'], 'c' * 64),
            (text, 0, ['/baseline.pdf', '/fixture.pdf'], 'c' * 64),
            (text, 0, ['/fixture.pdf', '/after-offline.pdf'], 'c' * 64),
            (text, 0, [], 'c' * 64), (text, 0, ['/fixture.pdf'], 'd' * 64),
            (text.replace('true', 'false'), 0, ['/fixture.pdf'], 'c' * 64)]:
            with self.subTest(text=changed_text, code=code, hits=hits, digest=digest):
                with self.assertRaises((ValueError, RuntimeError)):
                    h.validate_result(changed_text, code, hits, digest)

    def test_workflow_executes_network_none_gate_and_retains_small_evidence(self):
        import subprocess
        workflow = (ROOT / '.github/workflows/build-live.yml').read_text()
        marker = '      - name: Verify explicit networking opt-in and offline reading\n'
        self.assertIn(marker, workflow)
        block = workflow.split(marker, 1)[1].split('      - name:', 1)[0]
        for required in ('--network none', '--cap-drop ALL', '--security-opt no-new-privileges',
                         '--memory 2500m', '--memory-swap 2500m', '--cpus 1',
                         'target=/input/release.iso,readonly', 'target=/src,readonly',
                         'GRAVESTONE_TEST_ISO_SHA256=', 'scripts/test-networking.py',
                         'scripts/rufus-test.Dockerfile', 'trap cleanup EXIT',
                         'result.json command.json serial.log qemu.log extract.log'):
            self.assertIn(required, block)
        self.assertNotIn('--privileged', block)
        self.assertNotIn('docker cp "$container:/evidence"', block)
        script = block.split('        run: |\n', 1)[1]
        script = '\n'.join(line[10:] for line in script.splitlines())
        subprocess.run(['bash', '-n'], input=script, text=True, check=True, timeout=5)

    def test_network_fixture_pdf_imports_and_reads_in_actual_api(self):
        import hashlib
        import json
        import threading
        import urllib.request
        from app import make_server
        h = load_harness()
        with h.fixture_server(port=0) as fixture:
            with urllib.request.urlopen(f'http://127.0.0.1:{fixture.server_port}/fixture.pdf', timeout=2) as response:
                raw = response.read()
        # No fixture listener remains while the local original/search are read.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = root / 'content'; content.mkdir()
            (content / 'manifest.json').write_text(json.dumps({'documents': [], 'map': {}}))
            server = make_server(content_dir=content, data_dir=root / 'data', port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                request = urllib.request.Request(base + '/api/personal/import', raw,
                    headers={'Origin': base, 'Content-Type': 'application/pdf',
                             'X-Personal-Rights': 'acknowledged', 'X-Document-Title': 'Networking QA'}, method='POST')
                with urllib.request.urlopen(request, timeout=10) as response:
                    self.assertEqual(response.status, 201)
                    doc = json.load(response)
                self.assertEqual(doc['sha256'], hashlib.sha256(raw).hexdigest())
                with urllib.request.urlopen(base + '/' + doc['file'], timeout=2) as response:
                    self.assertEqual(response.read(), raw)
                with urllib.request.urlopen(base + '/api/search?q=Quasar', timeout=2) as response:
                    self.assertEqual(json.load(response)['results'][0]['id'], doc['id'])
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=3)

    def test_guest_transitions_and_shell_commands_have_bounded_deadlines(self):
        import ast
        import subprocess
        import time
        h = load_harness()
        namespace: dict[str, Any] = {'__name__': 'guest_unit_test'}
        source = h.guest_program('e' * 64)
        exec(compile(source, '<network-guest>', 'exec'), namespace)
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            namespace['bounded_wait'](lambda: False, seconds=.01)
        self.assertLess(time.monotonic() - start, 1)
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'subprocess'):
                self.assertIn('timeout', [kw.arg for kw in node.keywords])
        source_tree = ast.parse((ROOT / 'scripts/test-networking.py').read_text())
        for node in ast.walk(source_tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'subprocess'
                    and node.func.attr == 'run'):
                self.assertIn('timeout', [kw.arg for kw in node.keywords])
        preparation = (ROOT / 'scripts/prepare-live.sh').read_text()
        self.assertIn("--exclude='scripts'", preparation)
        self.assertIn("--exclude='tests'", preparation)
        self.assertIn("--exclude='.github'", preparation)

    def test_import_client_allows_60_seconds_without_changing_get_timeout(self):
        import io
        import json
        from unittest.mock import patch
        h = load_harness()
        ns: dict[str, Any] = {'__name__': 'guest_test'}
        exec(h.guest_program('a' * 64), ns)
        class Response(io.BytesIO):
            status = 201
        response = Response(json.dumps({'id': 'fixture'}).encode())
        request = object()
        with patch.object(ns['HTTP'], 'open', return_value=response) as opened:
            self.assertEqual(ns['import_document'](request, h.pdf_bytes()), {'id': 'fixture'})
        opened.assert_called_once_with(request, timeout=60)
        response = Response(b'fixture')
        response.status = 200
        with patch.object(ns['HTTP'], 'open', return_value=response) as opened:
            self.assertEqual(ns['get']('http://fixture.invalid/fixture.pdf'), b'fixture')
        opened.assert_called_once_with('http://fixture.invalid/fixture.pdf', timeout=8)

    def test_http400_emits_bounded_diagnostic_and_reraises_same_error(self):
        import contextlib
        import io
        import json
        import subprocess
        import urllib.error
        import urllib.request
        from unittest.mock import patch
        h = load_harness()
        ns: dict[str, Any] = {'__name__': 'guest_test'}
        exec(h.guest_program('a' * 64), ns)
        from email.message import Message
        error = urllib.error.HTTPError(ns['BASE'], 400, 'Bad Request', Message(),
                                       io.BytesIO(b'import failed ' + b'x' * 20000))
        calls = []
        def run(args, **kwargs):
            calls.append((args, kwargs))
            if 'app.personal_parser' in args:
                return subprocess.CompletedProcess(args, 1, b'worker output', b'e' * 20000)
            return subprocess.CompletedProcess(args, 0, b'module version or service status\n' * 1000, b'')
        output = io.StringIO()
        with patch.object(ns['HTTP'], 'open', side_effect=error), \
                patch.object(ns['subprocess'], 'run', side_effect=run), \
                contextlib.redirect_stdout(output):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                ns['import_document'](object(), h.pdf_bytes())
        self.assertIs(caught.exception, error)
        record = json.loads(output.getvalue().split('IMPORT_DIAGNOSTIC=', 1)[1])
        self.assertEqual(record['http_status'], 400)
        self.assertLessEqual(len(record['http_body']), 4096)
        self.assertEqual(record['worker']['returncode'], 1)
        self.assertEqual(record['worker']['status'], 'exited')
        self.assertGreaterEqual(record['worker']['elapsed_seconds'], 0)
        self.assertLessEqual(len(record['worker']['stderr']), 4096)
        self.assertIn('parser_module', record)
        self.assertIn('systemctl', record)
        self.assertIn('journal', record)
        self.assertLess(len(output.getvalue()), 40000)
        worker_args, worker_kw = next(c for c in calls if 'app.personal_parser' in c[0])
        self.assertEqual(worker_args, ['/usr/sbin/runuser', '-u', 'user', '--',
                                     '/usr/bin/python3', '-m', 'app.personal_parser'])
        self.assertEqual(worker_kw['cwd'], '/opt/gravestone')
        self.assertEqual(worker_kw['input'], h.pdf_bytes())
        self.assertEqual(worker_kw['timeout'], 40)
        self.assertIs(worker_kw['stdout'], subprocess.PIPE)
        self.assertIs(worker_kw['stderr'], subprocess.PIPE)
        for args, kw in calls:
            self.assertGreater(kw['timeout'], 0)
            self.assertLessEqual(kw['timeout'], 40)
            self.assertNotIn('shell', kw)
        self.assertEqual(sum('app.personal_parser' in a for a, _ in calls), 1)

    def test_actual_http400_and_diagnostic_timeout_do_not_become_success(self):
        import contextlib
        import http.server
        import io
        import json
        import subprocess
        import threading
        import urllib.error
        import urllib.request
        from unittest.mock import patch
        h = load_harness()
        ns: dict[str, Any] = {'__name__': 'guest_test'}
        source = h.guest_program('a' * 64)
        exec(source, ns)
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(400)
                self.send_header('Content-Length', '14')
                self.end_headers()
                self.wfile.write(b'parser refused')
            def log_message(self, *args):
                pass
        server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        output = io.StringIO()
        def timeout(args, **kw):
            raise subprocess.TimeoutExpired(args, kw['timeout'], output=b'o' * 20000,
                                             stderr=b'e' * 20000)
        try:
            req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/import',
                                         h.pdf_bytes(), method='POST')
            with patch.object(ns['subprocess'], 'run', side_effect=timeout), \
                    contextlib.redirect_stdout(output):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    ns['import_document'](req, h.pdf_bytes())
            self.assertEqual(caught.exception.code, 400)
            record = json.loads(output.getvalue().split('IMPORT_DIAGNOSTIC=', 1)[1])
            self.assertEqual(record['http_body'], 'parser refused')
            self.assertEqual(record['worker']['status'], 'timeout')
            self.assertIsNone(record['worker']['returncode'])
            self.assertLessEqual(len(record['worker']['stdout']), 4096)
            self.assertLess(len(output.getvalue()), 50000)
            self.assertNotIn('NETWORK_RESULT=', output.getvalue())
            self.assertIn('document = import_document(request, raw)', source)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)

    def test_isolation_checks_fail_closed(self):
        h = load_harness()
        good = 'CapEff:\t0000000000000000\nNoNewPrivs:\t1\n'
        h.check_isolation(['lo'], good)
        for names, status in [(['lo', 'eth0'], good), ([], good),
                              (['lo'], good.replace('0000000000000000', '0000000000000001')),
                              (['lo'], good.replace('NoNewPrivs:\t1', 'NoNewPrivs:\t0')),
                              (['lo'], '')]:
            with self.subTest(names=names, status=status), self.assertRaises(RuntimeError):
                h.check_isolation(names, status)


if __name__ == '__main__':
    unittest.main()
