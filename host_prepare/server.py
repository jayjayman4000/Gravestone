"""Single-request-at-a-time loopback wizard; uploads live in memory only."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import secrets
import socket

MAX_REQUEST = 92 * 1024 * 1024  # 64 MiB base64 plus bounded inventory/JSON
STATIC = Path(__file__).parent


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass  # Never log inventory, document names, or session token.

    def reply(self, status, body=b'', content_type='text/plain; charset=utf-8', filename=None):
        self.close_connection = True
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get_all('Host', []) == ['127.0.0.1:' + str(self.server.server_port)]

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403)
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/wizard.js': ('wizard.js', 'text/javascript; charset=utf-8'),
                 '/wizard.css': ('wizard.css', 'text/css; charset=utf-8')}
        if self.path not in files:
            return self.reply(404)
        name, mime = files[self.path]
        body = (STATIC / name).read_bytes()
        if name == 'index.html':
            body = body.replace(b'PREPARATION_TOKEN', self.server.token.encode())
        return self.reply(200, body, mime)

    def do_POST(self):
        from . import build_pack
        if (not self.valid_host() or self.headers.get('Origin') != 'http://127.0.0.1:' + str(self.server.server_port)
                or self.headers.get('X-Preparation-Token') != self.server.token
                or self.headers.get('Sec-Fetch-Site', 'same-origin') not in ('same-origin', 'none')):
            return self.reply(403)
        if self.path != '/pack':
            return self.reply(404)
        if self.headers.get('Content-Type') != 'application/json':
            return self.reply(415)
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            return self.reply(400)
        try:
            length = int(self.headers['Content-Length'])
            if not 0 < length <= MAX_REQUEST:
                return self.reply(413)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('Incomplete request')
            payload = json.loads(raw)
            packed = build_pack(payload)
        except (ValueError, UnicodeError, RecursionError, socket.timeout):
            return self.reply(400, b'Pack rejected. Check fields, PDF bytes, limits and permission acknowledgment.')
        return self.reply(200, packed, 'application/zip', 'gravestone-private-' + secrets.token_hex(12) + '.zip')


def make_server(port=0):
    server = HTTPServer(('127.0.0.1', port), Handler)
    server.token = secrets.token_hex(32)
    return server
