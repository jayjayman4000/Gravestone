"""Gravestone: a dependency-free, loopback-only offline dashboard."""
import json
import os
import stat
import mimetypes
import shutil
import secrets
import threading
from pathlib import Path
from typing import cast
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

PREVIEW_WARNING = 'Machine-extracted search preview — not verified; open the original document and read full context.'


def open_root(path, create=False):
    """Walk from / with openat: never follow a symlink, including ancestors."""
    parts = Path(os.path.abspath(path)).parts
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[1:]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def open_file(root, relative):
    if not isinstance(relative, str) or not relative or relative.startswith('/') or '\\' in relative or '\x00' in relative:
        raise ValueError('Invalid file path')
    parts = relative.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('Invalid file path')
    fd = open_root(root)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            os.close(file_fd)
            raise OSError('Not a regular file')
        return os.fdopen(file_fd, 'rb')
    finally:
        os.close(fd)


def read_text(root, relative, limit):
    with open_file(root, relative) as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('File exceeds read limit')
    return raw.decode('utf-8')


def read_manifest(root):
    data = json.loads(read_text(root, 'manifest.json', 2 * 1024 * 1024))
    if (not isinstance(data, dict) or not isinstance(data.get('documents'), list)
            or not isinstance(data.get('map'), dict)):
        raise ValueError('Invalid manifest')
    for document in data['documents']:
        if not isinstance(document, dict) or any(not isinstance(document.get(key), str) for key in ('id', 'title', 'file')):
            raise ValueError('Invalid document')
    return data


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, address, content_dir, data_dir):
        self.content_dir = content_dir
        self.data_dir = data_dir
        self.note_lock = threading.Lock()
        from .maps import MapManager
        self.maps = MapManager(data_dir)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    @property
    def app(self):
        return cast(DashboardServer, self.server)

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'SAMEORIGIN' if getattr(self, 'reader_pdf', False) else 'DENY')
        policy = "default-src 'self'; script-src 'self'; worker-src 'self'; font-src 'self' blob: data:; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if urlsplit(self.path).path.startswith('/content/'):
            policy = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        if getattr(self, 'reader_pdf', False):
            policy = "default-src 'none'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"
        self.send_header('Content-Security-Policy', policy)
        super().end_headers()

    def valid_host(self):
        return (len(self.headers.get_all('Host', [])) == 1 and self.headers.get('Host') in
                {f'127.0.0.1:{self.app.server_port}', f'localhost:{self.app.server_port}'})

    def log_message(self, format, *args):
        pass

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def serve_file(self, root, relative):
        if not relative:
            return self.send_json(404, {'error': 'Not found'})
        try:
            stream = open_file(root, relative)
        except ValueError:
            return self.send_json(400, {'error': 'Invalid path'})
        except OSError:
            return self.send_json(404, {'error': 'File unavailable'})
        with stream:
            media_type = mimetypes.guess_type(relative)[0] or 'application/octet-stream'
            # Only actual local PDF bytes get the framing exception, never HTML.
            is_pdf = media_type == 'application/pdf' and stream.read(5) == b'%PDF-'
            stream.seek(0)
            if media_type == 'application/pdf' and not is_pdf:
                media_type = 'application/octet-stream'
            self.reader_pdf = root == self.app.content_dir and is_pdf
            self.send_response(200)
            self.send_header('Content-Type', media_type)
            self.send_header('Content-Length', str(os.fstat(stream.fileno()).st_size))
            self.end_headers()
            if self.command != 'HEAD':
                shutil.copyfileobj(stream, self.wfile)

    def do_HEAD(self):
        # Reader preflight checks status and MIME without downloading the original.
        if not self.valid_host():
            return self.send_json(403, {'error': 'Loopback Host required'})
        path = urlsplit(self.path).path
        if path.startswith('/content/'):
            return self.serve_file(self.app.content_dir, unquote(path[len('/content/'):]))
        self.send_json(404, {'error': 'Not found'})

    def do_GET(self):
        if not self.valid_host():
            return self.send_json(403, {'error': 'Loopback Host required'})
        path = urlsplit(self.path).path
        if path == '/api/system':
            from .system_status import system_status
            return self.send_json(200, system_status(self.app.data_dir))
        if path.startswith('/api/maps/'):
            from .maps import handle_get
            return handle_get(self)
        if self.path == '/api/status':
            self.send_json(200, {
                'status': 'prototype',
                'persistence_note': 'Persistence is not verified. Notes survive only if the configured data directory is on persistent storage.',
            })
        elif self.path == '/':
            self.serve_file(Path(__file__).parent / 'static', 'index.html')
        elif urlsplit(self.path).path.startswith('/static/'):
            self.serve_file(Path(__file__).parent / 'static', unquote(urlsplit(self.path).path[len('/static/'):]))
        elif urlsplit(self.path).path.startswith('/content/'):
            self.serve_file(self.app.content_dir, unquote(urlsplit(self.path).path[len('/content/'):]))
        elif self.path == '/api/notes':
            try:
                with open_file(self.app.data_dir, 'notes.txt') as stream:
                    raw = stream.read(256 * 1024 + 1)
                if len(raw) > 256 * 1024:
                    raise ValueError('Notes too large')
                text = raw.decode('utf-8')
            except FileNotFoundError:
                try:
                    os.close(open_root(self.app.data_dir))
                except OSError:
                    return self.send_json(503, {'error': 'Notebook storage unavailable'})
                text = ''
            except (OSError, ValueError):
                return self.send_json(503, {'error': 'Notebook storage unavailable'})
            self.send_json(200, {'text': text})
        elif self.path == '/api/library':
            try:
                manifest = read_manifest(self.app.content_dir)
            except (OSError, ValueError):
                return self.send_json(503, {'error': 'Library manifest unavailable or invalid'})
            self.send_json(200, manifest)
        elif urlsplit(self.path).path == '/api/command':
            query = parse_qs(urlsplit(self.path).query).get('q', [''])[0].strip()
            if not query or len(query) > 200:
                return self.send_json(400, {'error': 'Enter a question of 1–200 characters'})
            try:
                # Lazy import avoids a circular dependency on safe content readers.
                from .retrieval import command_search
                result = command_search(self.app.content_dir, query,
                                        model_url=os.environ.get('GRAVESTONE_MODEL_URL', 'http://127.0.0.1:8767'))
            except (OSError, ValueError, ImportError):
                return self.send_json(503, {'error': 'Command search unavailable; check the installed library'})
            self.send_json(200, result)
        elif urlsplit(self.path).path == '/api/search':
            query = parse_qs(urlsplit(self.path).query).get('q', [''])[0].strip()
            if len(query) > 200:
                return self.send_json(400, {'error': 'Search query exceeds 200 characters'})
            try:
                manifest = read_manifest(self.app.content_dir)
            except (OSError, ValueError):
                return self.send_json(503, {'error': 'Library manifest unavailable or invalid'})
            results = []
            if query:
                import re
                for document in manifest['documents']:
                    if not document.get('text_file'):
                        continue
                    try:
                        text = read_text(self.app.content_dir, document['text_file'], 16 * 1024 * 1024)
                    except (OSError, ValueError):
                        continue
                    for page, source in enumerate(text.split('\f'), 1):
                        for match in re.finditer(re.escape(query), source, re.IGNORECASE):
                            results.append({'id': document['id'], 'title': document['title'],
                                            'publisher': document.get('publisher', ''),
                                            'file': document['file'], 'page': page,
                                            'excerpt': source[max(0, match.start()-100):match.end()+160]})
                            if len(results) >= 50:
                                break
                        if len(results) >= 50:
                            break
                    if len(results) >= 50:
                        break
            self.send_json(200, {'results': results, 'warning': PREVIEW_WARNING})
        else:
            self.send_json(404, {'error': 'Not found'})


    def do_POST(self):
        if urlsplit(self.path).path in ('/api/maps/download', '/api/maps/import', '/api/maps/remove'):
            host = self.headers.get('Host', '')
            if (not self.valid_host() or self.headers.get('Origin') != 'http://' + host
                    or self.headers.get('Sec-Fetch-Site', 'same-origin') not in ('same-origin', 'none')):
                return self.send_json(403, {'error': 'Same-origin request required'})
            from .maps import handle_post
            return handle_post(self)
        if self.path != '/api/notes':
            return self.send_json(404, {'error': 'Not found'})
        host = self.headers.get('Host', '')
        if (not self.valid_host()
                or self.headers.get('Origin') != 'http://' + host
                or self.headers.get('Sec-Fetch-Site', 'same-origin') not in ('same-origin', 'none')):
            return self.send_json(403, {'error': 'Same-origin request required'})
        if self.headers.get_content_type() != 'application/json':
            return self.send_json(415, {'error': 'Expected application/json'})
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) > 1:
            return self.send_json(400, {'error': 'Invalid request framing'})
        if self.headers.get('Content-Length') is None:
            return self.send_json(411, {'error': 'Content-Length required'})
        try:
            length = int(self.headers['Content-Length'])
            if length < 0:
                raise ValueError()
        except ValueError:
            return self.send_json(400, {'error': 'Invalid Content-Length'})
        if length > 256 * 1024 * 6 + 1024:
            return self.send_json(413, {'error': 'Request too large'})
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError()
            data = json.loads(raw.decode('utf-8'))
            if not isinstance(data, dict) or set(data) != {'text'} or not isinstance(data['text'], str):
                raise ValueError()
            text = data['text']
            size = len(text.encode('utf-8'))
        except (ValueError, UnicodeError, RecursionError):
            return self.send_json(400, {'error': 'Expected JSON object with text string only'})
        if size > 256 * 1024:
            return self.send_json(413, {'error': 'Notes exceed 256 KiB UTF-8 limit'})
        try:
            with self.app.note_lock:
                directory = open_root(self.app.data_dir)
                name = '.notes-' + secrets.token_hex(16)
                try:
                    try:
                        info = os.stat('notes.txt', dir_fd=directory, follow_symlinks=False)
                        if not stat.S_ISREG(info.st_mode):
                            raise OSError('Unsafe notebook target')
                    except FileNotFoundError:
                        pass
                    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(text.encode('utf-8'))
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(name, 'notes.txt', src_dir_fd=directory, dst_dir_fd=directory)
                    os.fsync(directory)
                finally:
                    try:
                        os.unlink(name, dir_fd=directory)
                    except FileNotFoundError:
                        pass
                    os.close(directory)
        except OSError:
            return self.send_json(503, {'error': 'Notebook save failed; check storage'})
        self.send_json(200, {'text': text})


def make_server(*, content_dir, data_dir, host='127.0.0.1', port=8766):
    if host not in ('127.0.0.1', 'localhost'):
        raise ValueError('Only 127.0.0.1 / localhost binding is permitted')
    host = '127.0.0.1'
    data_dir = Path(os.path.abspath(data_dir))
    content_dir = Path(os.path.abspath(content_dir))
    repo = Path(__file__).resolve().parent.parent
    if data_dir.is_relative_to(repo) or data_dir.is_relative_to(content_dir):
        raise ValueError('Data directory must be outside the repository and content tree')
    os.close(open_root(data_dir, create=True))
    return DashboardServer((host, port), content_dir, data_dir)
