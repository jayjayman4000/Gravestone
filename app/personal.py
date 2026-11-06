"""Private owner-acquired PDFs. No URL fetching; originals never enter content/."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
from datetime import datetime, timezone

from . import open_root, open_file, read_text
from .maps import _publish_directory, _clear_directory

MAX_PDF = 32 * 1024 * 1024
MAX_TEXT = 16 * 1024 * 1024
MAX_PAGES = 1000
PARSER_WALL_TIMEOUT = 40


def extract(raw):
    """Parse untrusted PDF in a disposable CPU/memory/time-bounded process."""
    if not raw.startswith(b'%PDF-') or not raw.rstrip().endswith(b'%%EOF'):
        raise ValueError('Expected a complete PDF, not a web page or partial download')
    try:
        result = subprocess.run([sys.executable, '-m', 'app.personal_parser'], input=raw,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=PARSER_WALL_TIMEOUT,
                                cwd=Path(__file__).resolve().parent.parent)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f'PDF parsing exceeded {PARSER_WALL_TIMEOUT} seconds') from exc
    if result.returncode == 3:
        raise ValueError('PDF parser unavailable; install python3-pypdf2 (or pypdf) before importing')
    if result.returncode or len(result.stdout) > MAX_TEXT + 32768:
        raise ValueError('PDF is invalid, encrypted, or exceeds parsing limits')
    data = json.loads(result.stdout)
    return data['pages'], data['text'], data['parser']


class PersonalLibrary:
    def __init__(self, data_dir):
        self.root = Path(data_dir) / 'personal'
        self.lock = threading.Lock()

    def documents(self):
        try:
            directory = open_root(self.root)
        except FileNotFoundError:
            return []
        try:
            names = sorted(os.listdir(directory))
        finally:
            os.close(directory)
        docs = []
        for name in names:
            if re.fullmatch(r'[a-f0-9]{64}', name):
                try:
                    doc = json.loads(read_text(self.root, name + '/metadata.json', 32768))
                    if (isinstance(doc, dict) and doc.get('id') == 'personal-' + name
                            and doc.get('file') == 'personal/' + name + '/original.pdf'
                            and doc.get('text_file') == 'personal/' + name + '/search.txt'
                            and doc.get('personal') is True and doc.get('sha256') == name
                            and isinstance(doc.get('title'), str)
                            and type(doc.get('pages')) is int and 1 <= doc['pages'] <= MAX_PAGES):
                        docs.append(doc)
                except (OSError, ValueError, KeyError):
                    continue
        return docs

    def install(self, raw, title, source_id='other'):
        if not raw or len(raw) > MAX_PDF:
            raise ValueError('PDF must be 1 byte to 32 MiB')
        if not isinstance(title, str) or not title.strip() or len(title) > 200 or any(ord(c) < 32 for c in title):
            raise ValueError('Title must be 1–200 printable characters')
        # Keep the legacy header bounded without accepting URLs or inventing provenance.
        # Existing private metadata remains readable; new imports are generic.
        if source_id != 'other':
            raise ValueError('Expected a generic local personal PDF')
        with self.lock:
            directory = open_root(self.root, create=True)
            temporary = staging = None
            try:
                pages, text, parser = extract(raw)
                digest = hashlib.sha256(raw).hexdigest()
                doc = {'id': 'personal-' + digest, 'title': 'Personal · ' + title.strip(),
                       'personal': True, 'publisher': 'Personal import · publisher not verified',
                       'file': 'personal/' + digest + '/original.pdf',
                       'text_file': 'personal/' + digest + '/search.txt', 'pages': pages,
                       'sha256': digest, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                       'original_bytes': len(raw), 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                       'source_id': source_id, 'url': '', 'rights': 'Owner acknowledged authorized personal storage/use and applicable publisher terms. No redistribution permission inferred.',
                       'extraction_status': 'Unverified machine extraction (' + parser + '); image-only pages are not searchable. Compare original pages.'}
                candidate = '.import-' + secrets.token_hex(16)
                os.mkdir(candidate, 0o700, dir_fd=directory)
                temporary = candidate
                staging = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                for name, body in [('original.pdf', raw), ('search.txt', text.encode()),
                                   ('metadata.json', json.dumps(doc, ensure_ascii=False).encode())]:
                    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=staging)
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(body); stream.flush(); os.fsync(stream.fileno())
                os.fsync(staging)
                visible = open_root(self.root)
                try:
                    before, after = os.fstat(directory), os.fstat(visible)
                    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                        raise OSError('Personal storage changed during import')
                finally:
                    os.close(visible)
                _publish_directory(directory, temporary, digest)
                temporary = None
                os.fsync(directory)
                return doc
            finally:
                try:
                    if temporary is not None:
                        if staging is not None:
                            _clear_directory(staging)
                        os.rmdir(temporary, dir_fd=directory)
                finally:
                    if staging is not None:
                        os.close(staging)
                    os.close(directory)


def handle_import(handler):
    handler.close_connection = True
    host = handler.headers.get('Host', '')
    if (not handler.valid_host() or handler.headers.get('Origin') != 'http://' + host
            or handler.headers.get('Sec-Fetch-Site', 'same-origin') not in ('same-origin', 'none')):
        return handler.send_json(403, {'error': 'Same-origin request required'})
    if handler.headers.get_content_type() != 'application/pdf':
        return handler.send_json(415, {'error': 'Expected application/pdf bytes only'})
    if handler.headers.get('X-Personal-Rights') != 'acknowledged':
        return handler.send_json(400, {'error': 'Personal storage/use and publisher terms acknowledgment required'})
    if handler.headers.get('Transfer-Encoding') or len(handler.headers.get_all('Content-Length', [])) != 1:
        return handler.send_json(400, {'error': 'One Content-Length required'})
    try:
        length = int(handler.headers['Content-Length'])
        if length <= 0 or length > MAX_PDF:
            return handler.send_json(413, {'error': 'PDF must be 1 byte to 32 MiB'})
        from urllib.parse import unquote
        title = unquote(handler.headers.get('X-Document-Title', 'Imported PDF'), errors='strict')
        raw = handler.rfile.read(length)
        if len(raw) != length:
            raise ValueError('Incomplete upload')
        doc = handler.app.personal.install(raw, title, handler.headers.get('X-Source-Id', 'other'))
    except (ValueError, UnicodeError):
        return handler.send_json(400, {'error': 'Import rejected: invalid PDF/title, parsing limits, or unavailable PDF parser'})
    except FileExistsError:
        return handler.send_json(409, {'error': 'This PDF is already imported; no file replaced'})
    except OSError:
        return handler.send_json(503, {'error': 'Import not confirmed; check private storage and library before retrying'})
    return handler.send_json(201, doc)


def serve_personal(handler):
    from urllib.parse import urlsplit
    path = urlsplit(handler.path).path
    if not re.fullmatch(r'/personal/[a-f0-9]{64}/(original\.pdf|search\.txt)', path):
        return handler.send_json(404, {'error': 'Not found'})
    return handler.serve_file(handler.app.data_dir, path[1:])
