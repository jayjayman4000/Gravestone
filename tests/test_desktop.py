"""Opt-in desktop bridge: no host commands or networking are executed."""
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from app import make_server

ROOT = Path(__file__).resolve().parents[1]


class DesktopAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = make_server(content_dir=ROOT / 'content', data_dir=Path(self.tmp.name) / 'data', port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = '127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()

    def request(self, path, body=b'{}', headers=None, method='POST'):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        conn.request(method, path, body, headers or {'Origin': 'http://' + self.host, 'Content-Type': 'application/json'})
        response = conn.getresponse()
        status, data = response.status, json.loads(response.read())
        conn.close()
        return status, data

    def test_desktop_is_unavailable_without_live_session(self):
        status, data = self.request('/api/desktop/network-online')
        self.assertEqual(status, 503)
        self.assertIn('error', data)

    def test_status_is_read_only_and_get_cannot_launch(self):
        with patch('app.desktop.request_action', return_value={'accepted': True, 'network_state': 'disconnected'}) as launch:
            self.assertEqual(self.request('/api/desktop/status', method='GET')[0], 200)
            launch.assert_called_once_with('status')
            self.assertEqual(self.request('/api/desktop/browser', method='GET')[0], 404)
            self.assertEqual(launch.call_count, 1)

    def test_ambiguous_headers_and_framing_never_launch(self):
        import socket
        cases = [
            ('Content-Length: 2\r\nContent-Length: 2', '', 400),
            ('Content-Length: 2\r\nTransfer-Encoding: chunked', '', 400),
            ('', '', 400),
            ('Content-Length: 2', 'Origin: http://' + self.host + '\r\n', 403),
            ('Content-Length: 2', 'Sec-Fetch-Site: same-origin\r\nSec-Fetch-Site: cross-site\r\n', 403),
            ('Content-Length: 2', 'Content-Type: text/plain\r\n', 415),
        ]
        with patch('app.desktop.request_action', return_value={'accepted': True}) as launch:
            for framing, extra, expected in cases:
                with self.subTest(framing=framing, extra=extra):
                    raw = ('POST /api/desktop/browser HTTP/1.1\r\nHost: ' + self.host +
                           '\r\nOrigin: http://' + self.host + '\r\nContent-Type: application/json\r\n' +
                           extra + (framing + '\r\n' if framing else '') + '\r\n{}').encode()
                    with socket.create_connection(('127.0.0.1', self.server.server_port), timeout=3) as sock:
                        sock.sendall(raw)
                        response = http.client.HTTPResponse(sock)
                        response.begin()
                        self.assertEqual(response.status, expected)
                        self.assertTrue(response.will_close)
                        response.read()
                        self.assertEqual(sock.recv(1), b'', 'Rejected request must close the transport')
            launch.assert_not_called()

    def test_download_directory_to_import_read_search_and_restart(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from urllib.request import urlopen
        from test_personal import pdf_bytes
        from app.desktop import DesktopSession
        pdf = pdf_bytes()
        class Publisher(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Disposition', 'attachment; filename="equipment.pdf"')
                self.send_header('Content-Length', str(len(pdf)))
                self.end_headers(); self.wfile.write(pdf)
            def log_message(self, format, *args): pass
        publisher = ThreadingHTTPServer(('127.0.0.1', 0), Publisher)
        thread = threading.Thread(target=publisher.serve_forever, daemon=True); thread.start()
        try:
            home = Path(self.tmp.name) / 'home'
            with patch('app.desktop.subprocess.Popen'), patch('app.desktop.subprocess.run'):
                session = DesktopSession(home)
                session.perform('browser')  # Profile and Downloads are real; native launch alone is mocked.
                target = home / 'Downloads/equipment.pdf'
                with urlopen('http://127.0.0.1:' + str(publisher.server_port) + '/equipment.pdf', timeout=3) as response:
                    target.write_bytes(response.read())
                session.perform('network-offline')  # Never invoke host sudo/network commands.
            status, imported = self.request('/api/personal/import', target.read_bytes(), {
                'Origin': 'http://' + self.host, 'Content-Type': 'application/pdf',
                'X-Personal-Rights': 'acknowledged', 'X-Document-Title': 'Downloaded test fixture',
            })
            self.assertEqual(status, 201, imported)
            self.server.shutdown(); self.server.server_close(); self.thread.join()
            self.server = make_server(content_dir=ROOT / 'content', data_dir=Path(self.tmp.name) / 'data', port=0)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
            self.host = '127.0.0.1:' + str(self.server.server_port)
            self.assertTrue(any(d['id'] == imported['id'] for d in self.request('/api/library', method='GET')[1]['documents']))
            hits = self.request('/api/command?q=Quasar', method='GET')[1]['results']
            self.assertTrue(any(hit['id'] == imported['id'] for hit in hits))
            conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
            conn.request('GET', '/' + imported['file'])
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), pdf)
            conn.close()
        finally:
            publisher.shutdown(); publisher.server_close(); thread.join()

    def test_only_empty_same_origin_fixed_actions_reach_bridge(self):
        with patch('app.desktop.request_action', return_value={'accepted': True}) as launch:
            for action in ('network-online', 'network-settings', 'network-offline', 'browser'):
                self.assertEqual(self.request('/api/desktop/' + action)[0], 200)
            self.assertEqual(launch.call_count, 4)
            for path, body, headers, expected in [
                ('browser', b'{"url":"https://example.org"}', None, 400),
                ('sh', b'{}', None, 404),
                ('browser', b'{}', {'Origin': 'https://evil.test', 'Content-Type': 'application/json'}, 403),
                ('browser', b'{}', {'Origin': 'http://' + self.host, 'Sec-Fetch-Site': 'cross-site', 'Content-Type': 'application/json'}, 403),
                ('browser', b'{}', {'Origin': 'http://' + self.host, 'Content-Type': 'text/plain'}, 415),
            ]:
                self.assertEqual(self.request('/api/desktop/' + path, body, headers)[0], expected)
            self.assertEqual(launch.call_count, 4)


class LiveNetworkRecipeTests(unittest.TestCase):
    def test_live_network_is_boot_gated_and_only_fixed_sudo_is_allowed(self):
        include = ROOT / 'live/config/includes.chroot'
        helper = include / 'usr/local/sbin/gravestone-network'
        self.assertTrue(helper.is_file(), 'missing opt-in network helper')
        script = helper.read_text()
        self.assertIn('online)', script)
        self.assertIn('offline)', script)
        self.assertIn('nmcli --wait 5 networking on', script)
        self.assertIn('nmcli --wait 5 networking off', script)
        self.assertIn('/run/gravestone-network-enabled', script)
        self.assertNotIn('eval ', script)
        policy = (include / 'etc/sudoers.d/gravestone-network').read_text()
        self.assertEqual(policy.strip(), 'user ALL=(root) NOPASSWD: /usr/local/sbin/gravestone-network online, /usr/local/sbin/gravestone-network offline')
        gate = (include / 'etc/systemd/system/NetworkManager.service.d/gravestone.conf').read_text()
        self.assertIn('ConditionPathExists=/run/gravestone-network-enabled', gate)
        self.assertIn('After=gravestone-network-default.service', gate)
        boot = (include / 'etc/systemd/system/gravestone-network-default.service').read_text()
        self.assertIn('Before=NetworkManager.service', boot)
        self.assertIn('RemainAfterExit=yes', boot)
        hook = (ROOT / 'live/config/hooks/live/0100-gravestone.hook.chroot').read_text()
        self.assertNotIn('mask networking.service NetworkManager.service', hook)
        self.assertIn('disable NetworkManager.service', hook)
        packages = (ROOT / 'live/config/package-lists/kiosk.list.chroot').read_text().splitlines()
        for package in ('network-manager', 'xterm', 'policykit-1'):
            self.assertIn(package, packages)
        session = (include / 'usr/local/bin/gravestone-session').read_text()
        self.assertIn('python3 -B -m app.desktop', session)
        self.assertIn('gravestone-kiosk', session)
        self.assertIn('--profile', session)


    def test_helper_control_flow_with_disposable_fake_commands_only(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            commands = base / 'bin'; commands.mkdir()
            log = base / 'calls'
            marker = base / 'enabled'
            for name in ('touch', 'rm'):
                (commands / name).symlink_to('/usr/bin/' + name)
            for name, script in {
                'id': '#!/bin/sh\nprintf "0\\n"\n',
                'systemctl': '#!/bin/sh\nprintf "systemctl %s\\n" "$*" >> "$CALL_LOG"\n',
                'nmcli': '#!/bin/sh\nprintf "nmcli %s\\n" "$*" >> "$CALL_LOG"\n',
            }.items():
                target = commands / name; target.write_text(script); target.chmod(0o700)
            source = (ROOT / 'live/config/includes.chroot/usr/local/sbin/gravestone-network').read_text()
            source = source.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin', 'PATH=' + str(commands))
            source = source.replace('/run/gravestone-network-enabled', str(marker))
            helper = base / 'helper'; helper.write_text(source)
            env = dict(os.environ, CALL_LOG=str(log))
            for action in ('online', 'offline'):
                result = subprocess.run(['/bin/sh', str(helper), action], env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(marker.exists(), action == 'online')
            self.assertEqual(log.read_text().splitlines(), [
                'systemctl start gravestone-network-default.service',
                'systemctl start NetworkManager.service',
                'nmcli --wait 5 networking on', 'nmcli --wait 5 radio wifi on',
                'systemctl is-active --quiet NetworkManager.service',
                'nmcli --wait 5 radio wifi off', 'nmcli --wait 5 networking off',
                'systemctl stop NetworkManager.service',
            ])
            before = log.read_bytes()
            self.assertEqual(subprocess.run(['/bin/sh', str(helper), 'sh'], env=env).returncode, 2)
            self.assertEqual(log.read_bytes(), before, 'Unknown action must execute no commands')


class DesktopSessionTests(unittest.TestCase):
    def test_session_launches_fixed_native_commands_and_separate_download_profile(self):
        from app import desktop
        with tempfile.TemporaryDirectory() as directory, patch('app.desktop.subprocess.run') as run, patch('app.desktop.subprocess.Popen') as popen:
            home = Path(directory)
            run.return_value.stdout = 'asleep\n'
            run.return_value.returncode = 0
            session = desktop.DesktopSession(home)
            self.assertEqual(session.perform('status')['network_state'], 'asleep')
            session.perform('network-online')
            run.assert_called_with(['/usr/bin/sudo', '-n', '/usr/local/sbin/gravestone-network', 'online'], check=True, timeout=25, capture_output=True, text=True)
            session.perform('network-offline')
            self.assertEqual(run.call_args.args[0][-1], 'offline')
            session.perform('network-settings')
            self.assertEqual(popen.call_args.args[0], ['/usr/bin/xterm', '-T', 'Gravestone Wi-Fi / wired setup — Quit to return', '-e', '/usr/bin/nmtui'])
            session.perform('browser')
            argv = popen.call_args.args[0]
            self.assertIn('--no-remote', argv)
            self.assertIn(str(home / '.mozilla/gravestone-downloads'), argv)
            self.assertEqual(argv[-1], 'about:blank')
            self.assertNotIn('--kiosk', argv)
            prefs = (home / '.mozilla/gravestone-downloads/user.js').read_text()
            self.assertIn(str(home / 'Downloads'), prefs)
            self.assertIn('browser.download.useDownloadDir', prefs)
            self.assertTrue((home / 'Downloads').is_dir())
            with self.assertRaises(ValueError):
                session.perform('browser;sh')

    def test_bridge_round_trip_over_real_private_unix_socket(self):
        from app import desktop
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'control.sock'
            class Session:
                def perform(self, action):
                    return {'accepted': True, 'action': action}
            stop = threading.Event()
            thread = threading.Thread(target=desktop.serve_session, args=(Session(), path, stop), daemon=True)
            thread.start()
            import time
            for _ in range(100):
                if path.exists(): break
                time.sleep(.01)
            try:
                with patch('app.desktop.SOCKET', path):
                    self.assertEqual(desktop.request_action('browser'), {'accepted': True, 'action': 'browser'})
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            finally:
                stop.set(); thread.join(3)
            self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
