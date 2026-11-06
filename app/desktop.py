"""Fixed local desktop actions, served by the live X session, never a shell API."""
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import threading

ACTIONS = ('status', 'network-online', 'network-settings', 'network-offline', 'browser')
SOCKET = Path('/home/user/.local/share/gravestone-desktop/control.sock')


def request_action(action):
    if action not in ACTIONS:
        raise ValueError('Unknown desktop action')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(30)
        client.connect(str(SOCKET))
        client.sendall(action.encode('ascii') + b'\n')
        with client.makefile('rb') as stream:
            raw = stream.readline(4097)
        if len(raw) > 4096:
            raise ValueError('Invalid desktop response')
        result = json.loads(raw)
        if not isinstance(result, dict) or not result.get('accepted'):
            raise ValueError('Desktop action failed; check the native window')
        return result


class DesktopSession:
    """Runs outside the backend sandbox with the real X/DBus session environment."""
    def __init__(self, home):
        self.home = Path(home)
        self.windows = {}

    def perform(self, action):
        if action not in ACTIONS:
            raise ValueError('Unknown desktop action')
        if action == 'status':
            result = subprocess.run(['/usr/bin/nmcli', '-t', '-f', 'STATE', 'general'],
                                    capture_output=True, text=True, timeout=3)
            state = result.stdout.strip() if result.returncode == 0 else 'unavailable / offline'
            return {'accepted': True, 'network_state': state}
        if action in ('network-online', 'network-offline'):
            subprocess.run(['/usr/bin/sudo', '-n', '/usr/local/sbin/gravestone-network',
                            'online' if action == 'network-online' else 'offline'],
                           check=True, timeout=25, capture_output=True, text=True)
            return {'accepted': True}
        existing = self.windows.get(action)
        if existing is not None and existing.poll() is None:
            return {'accepted': True, 'already_open': True}
        if action == 'network-settings':
            command = ['/usr/bin/xterm', '-T', 'Gravestone Wi-Fi / wired setup — Quit to return',
                       '-e', '/usr/bin/nmtui']
        else:
            from . import open_root
            profile = self.home / '.mozilla/gravestone-downloads'
            downloads = self.home / 'Downloads'
            os.close(open_root(downloads, create=True))
            directory = open_root(profile, create=True)
            try:
                fd = os.open('user.js', os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
                prefs = {'browser.download.folderList': 2,
                         'browser.download.dir': str(downloads),
                         'browser.download.useDownloadDir': True,
                         'browser.startup.homepage': 'about:blank'}
                with os.fdopen(fd, 'w') as stream:
                    for key, value in prefs.items():
                        stream.write('user_pref(' + json.dumps(key) + ', ' + json.dumps(value) + ');\n')
            finally:
                os.close(directory)
            command = ['/usr/bin/firefox-esr', '--no-remote', '--profile', str(profile),
                       '--new-window', 'about:blank']
        self.windows[action] = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {'accepted': True}


def serve_session(session, path=SOCKET, stop=None):
    """Private same-UID socket; serial requests and bounded messages, no shell/URL input."""
    from . import open_root
    import fcntl
    stop = stop or threading.Event()
    directory = open_root(path.parent, create=True)
    lock = os.open('session.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            os.unlink(path.name, dir_fd=directory)
        except FileNotFoundError:
            pass
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(path))
            os.chmod(path, 0o600)
            server.listen(4)
            server.settimeout(.25)
            try:
                while not stop.is_set():
                    try:
                        conn, _ = server.accept()
                    except socket.timeout:
                        continue
                    with conn:
                        conn.settimeout(2)
                        try:
                            _, uid, _ = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                            if uid != os.getuid():
                                continue
                            with conn.makefile('rb') as stream:
                                raw = stream.readline(65)
                            action = raw.decode('ascii').removesuffix('\n')
                            if not raw.endswith(b'\n') or action not in ACTIONS:
                                raise ValueError('Unknown action')
                            result = session.perform(action)
                        except (OSError, ValueError, subprocess.SubprocessError):
                            result = {'accepted': False, 'error': 'Desktop action unavailable'}
                        try:
                            conn.sendall(json.dumps(result).encode('utf-8') + b'\n')
                        except OSError:
                            pass
            finally:
                os.unlink(path.name, dir_fd=directory)
    finally:
        os.close(lock)
        os.close(directory)


def handle_post(handler):
    # Always close, including rejection paths with unread bytes.
    handler.close_connection = True
    host = handler.headers.get('Host', '')
    if (not handler.valid_host() or len(handler.headers.get_all('Origin', [])) != 1
            or handler.headers.get('Origin') != 'http://' + host
            or len(handler.headers.get_all('Sec-Fetch-Site', [])) > 1
            or handler.headers.get('Sec-Fetch-Site', 'same-origin') not in ('same-origin', 'none')):
        return handler.send_json(403, {'error': 'Same-origin request required'})
    action = handler.path.removeprefix('/api/desktop/')
    if action not in ACTIONS or action == 'status':
        return handler.send_json(404, {'error': 'Unknown desktop action'})
    if (len(handler.headers.get_all('Content-Type', [])) != 1
            or handler.headers.get_content_type() != 'application/json'):
        return handler.send_json(415, {'error': 'Expected application/json'})
    lengths = handler.headers.get_all('Content-Length', [])
    if handler.headers.get_all('Transfer-Encoding') or len(lengths) != 1:
        return handler.send_json(400, {'error': 'Invalid request framing'})
    if lengths[0] != '2':
        return handler.send_json(400, {'error': 'Expected empty JSON object only'})
    if handler.rfile.read(2) != b'{}':
        return handler.send_json(400, {'error': 'Expected empty JSON object only'})
    try:
        result = request_action(action)
    except (OSError, ValueError):
        return handler.send_json(503, {'error': 'Live desktop unavailable or action failed. Use the live image desktop; local imports still work.'})
    handler.send_json(200, result)


if __name__ == '__main__':
    serve_session(DesktopSession(Path.home()))
