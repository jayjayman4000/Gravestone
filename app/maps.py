"""Explicitly selected, bounded Census TIGER county reference packs (no routing)."""
import ctypes
import errno
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import threading
import time
from datetime import datetime, timezone
from urllib.request import build_opener, HTTPRedirectHandler, Request
from zipfile import ZipFile

from . import open_root, open_file, read_text
from ._vendor import shapefile

CATALOG = Path(__file__).resolve().parents[1] / 'content/maps/tiger-catalog.json'
MAX_ZIP = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_DATA = 96 * 1024 * 1024
RESERVE = 512 * 1024 * 1024
LAYERS = {'roads': 'ROADS', 'water': 'LINEARWATER'}
LIMITATION = 'County reference only; not computed routes, live passability, drinking-water safety, or elevation. TIGER/Line 2025; U.S. Census Bureau; no endorsement.'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Map download redirects are not permitted')


def source_url(region_id, layer):
    if not isinstance(region_id, str) or not re.fullmatch(r'\d{5}', region_id) or layer not in LAYERS:
        raise ValueError('Invalid county or layer')
    suffix = 'roads' if layer == 'roads' else 'linearwater'
    return f'https://www2.census.gov/geo/tiger/TIGER2025/{LAYERS[layer]}/tl_2025_{region_id}_{suffix}.zip'


def download(region_id, layer):
    # No caller-provided URLs; fixed HTTPS origin/path; redirects disabled.
    url = source_url(region_id, layer)
    started = time.monotonic()
    chunks = []
    size = 0
    with build_opener(NoRedirect()).open(Request(url, headers={'User-Agent': 'Gravestone-offline-preparation/1'}), timeout=25) as response:
        if response.status != 200 or response.url != url:
            raise ValueError('Unexpected Census response')
        if int(response.headers.get('Content-Length', '0')) > MAX_ZIP:
            raise ValueError('County ZIP exceeds 64 MiB limit')
        while True:
            if time.monotonic() - started > 120:
                raise ValueError('Download exceeded 120 seconds')
            chunk = response.read(128 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_ZIP:
                raise ValueError('County ZIP exceeds 64 MiB limit')
            chunks.append(chunk)
    return b''.join(chunks)


def convert(raw, region_id, layer):
    if not raw or len(raw) > MAX_ZIP:
        raise ValueError('ZIP must be between 1 byte and 64 MiB')
    suffix = 'roads' if layer == 'roads' else 'linearwater'
    stem = f'tl_2025_{region_id}_{suffix}'
    with ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        names = [m.filename for m in members]
        if len(members) > 20 or len(names) != len(set(names)) or sum(m.file_size for m in members) > MAX_EXPANDED:
            raise ValueError('ZIP exceeds member/expanded limits or contains duplicates')
        for member in members:
            name = member.filename
            mode = member.external_attr >> 16
            if (not name.startswith(stem + '.') or '/' in name or '\\' in name or '\x00' in name
                    or '..' in name or member.flag_bits & 1 or stat.S_ISLNK(mode)
                    or member.file_size > MAX_EXPANDED or member.compress_type not in (0, 8)):
                raise ValueError('Unsafe or unexpected ZIP member')
        for ext in ('.shp', '.shx', '.dbf', '.prj'):
            if stem + ext not in names:
                raise ValueError('ZIP is missing ' + ext)
        projection = archive.read(stem + '.prj').decode('ascii')
        if 'GCS_North_American_1983' not in projection or 'PROJCS' in projection:
            raise ValueError('Expected Census NAD83 geographic coordinates')
        streams = {ext: io.BytesIO(archive.read(stem + '.' + ext)) for ext in ('shp', 'shx', 'dbf')}
    features = []
    vertices = 0
    bbox = [180.0, 90.0, -180.0, -90.0]
    with shapefile.Reader(**streams, encoding='utf-8', encodingErrors='strict') as reader:
        if reader.shapeType != shapefile.POLYLINE or reader.numRecords > 200000:
            raise ValueError('Expected bounded polyline shapefile')
        for record in reader.iterShapeRecords():
            shape = record.shape
            if shape.shapeType == 0:
                continue
            vertices += len(shape.points)
            if vertices > 2000000:
                raise ValueError('County exceeds 2 million vertex limit')
            coordinates = []
            offsets = list(shape.parts) + [len(shape.points)]
            for start, end in zip(offsets, offsets[1:]):
                line = []
                for lon, lat in shape.points[start:end]:
                    if not math.isfinite(lon) or not math.isfinite(lat) or abs(lon) > 180 or abs(lat) > 90:
                        raise ValueError('Invalid geographic coordinate')
                    bbox = [min(bbox[0], lon), min(bbox[1], lat), max(bbox[2], lon), max(bbox[3], lat)]
                    line.append([lon, lat])
                if len(line) > 1:
                    coordinates.append(line)
            if coordinates:
                fields = record.record.as_dict()
                features.append({'type': 'Feature', 'properties': {'name': fields.get('FULLNAME', ''),
                                 'mtfcc': fields.get('MTFCC', '')},
                                 'geometry': {'type': 'MultiLineString', 'coordinates': coordinates}})
    if not features:
        raise ValueError('No line geometry in this county layer')
    data = {'type': 'FeatureCollection', 'bbox': bbox, 'features': features}
    encoded = json.dumps(data, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(encoded) > MAX_DATA:
        raise ValueError('Converted layer exceeds 96 MiB')
    return encoded, bbox, len(features)


def _publish_directory(directory, source, target):
    """Linux atomic, descriptor-relative rename that cannot replace a layer."""
    rename = getattr(ctypes.CDLL(None, use_errno=True), 'renameat2', None)
    if rename is None:
        raise OSError(errno.ENOSYS, 'Atomic no-replace map installation is unavailable')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(directory, os.fsencode(source), directory, os.fsencode(target), 1):  # RENAME_NOREPLACE
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), target)


def _clear_directory(directory):
    """Remove entries relative to an open directory, never following symlinks."""
    for name in os.listdir(directory):
        if stat.S_ISDIR(os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode):
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            try:
                _clear_directory(child)
            finally:
                os.close(child)
            os.rmdir(name, dir_fd=directory)
        else:
            os.unlink(name, dir_fd=directory)


class MapManager:
    def __init__(self, data_dir):
        self.root = Path(data_dir) / 'maps'
        self.lock = threading.Lock()
        self.jobs = {}

    def catalog(self):
        return json.loads(CATALOG.read_text(encoding='utf-8'))

    def region(self, ident):
        if not isinstance(ident, str) or not re.fullmatch(r'\d{5}', ident):
            raise ValueError('Select a catalog county')
        region = next((r for r in self.catalog()['regions'] if r['id'] == ident), None)
        if region is None:
            raise ValueError('County is not in the installed catalog')
        return region

    def pack_id(self, ident):
        if not isinstance(ident, str) or not re.fullmatch(r'\d{5}-(roads|water)', ident):
            raise ValueError('Invalid map pack ID')
        return ident

    def installed(self):
        if not self.root.exists():
            return []
        os.close(open_root(self.root))
        packs = []
        for path in sorted(self.root.iterdir()):
            if re.fullmatch(r'\d{5}-(roads|water)', path.name):
                try:
                    metadata = json.loads(read_text(self.root, path.name + '/metadata.json', 32768))
                    if metadata['id'] != path.name:
                        continue
                    packs.append(metadata)
                except (OSError, ValueError, KeyError):
                    continue
        return packs

    def data(self, ident, layer):
        ident = self.pack_id(ident)
        if layer not in LAYERS or not ident.endswith('-' + layer):
            raise ValueError('Layer does not match installed pack')
        metadata = json.loads(read_text(self.root, ident + '/metadata.json', 32768))
        with open_file(self.root, ident + '/data.geojson') as stream:
            raw = stream.read(MAX_DATA + 1)
        if len(raw) > MAX_DATA or hashlib.sha256(raw).hexdigest() != metadata['data_sha256']:
            raise ValueError('Installed map failed integrity check; remove and reinstall')
        return json.loads(raw)

    def install(self, region_id, layer, raw, imported=False):
        region = self.region(region_id)
        url = source_url(region_id, layer)
        ident = region_id + '-' + layer
        with self.lock:
            directory = open_root(self.root, create=True)
            temporary = None
            staging = None
            try:
                try:
                    os.stat(ident, dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError('Layer already installed; remove it explicitly before replacing')
                if shutil.disk_usage(directory).free < RESERVE + MAX_EXPANDED + MAX_DATA + len(raw):
                    raise OSError('Insufficient space; preserve 512 MiB free plus conversion headroom')
                encoded, bbox, count = convert(raw, region_id, layer)
                metadata = {'id': ident, 'region_id': region_id, 'name': region['name'], 'state': region['state'],
                        'year': 2025, 'layer': layer, 'publisher': 'U.S. Census Bureau',
                        'source_url': url, 'final_url': None if imported else url,
                        'imported': imported, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                        'sha256': hashlib.sha256(raw).hexdigest(), 'data_sha256': hashlib.sha256(encoded).hexdigest(),
                        'original_bytes': len(raw), 'data_bytes': len(encoded), 'features': count, 'bbox': bbox,
                        'rights': 'Not copyrighted. Acknowledge U.S. Census Bureau. TIGER/Line and Census TIGER are registered trademarks.',
                        'rights_evidence': 'content/maps/tiger-rights-original.html; original ZIP .shp.iso.xml',
                        'transformation': 'pyshp 2.3.1; NAD83 longitude/latitude polylines to GeoJSON without simplification; FULLNAME and MTFCC retained.',
                        'limitations': LIMITATION}
                while True:
                    candidate = '.install-' + secrets.token_hex(16)
                    try:
                        os.mkdir(candidate, mode=0o700, dir_fd=directory)
                    except FileExistsError:
                        continue
                    temporary = candidate
                    break
                staging = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                for name, body in [('original.zip', raw), ('data.geojson', encoded),
                                   ('metadata.json', json.dumps(metadata, ensure_ascii=False).encode('utf-8'))]:
                    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=staging)
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(body)
                        stream.flush()
                        os.fsync(stream.fileno())
                os.fsync(staging)
                # Fail closed if either the visible root or an ancestor changed.
                visible = open_root(self.root)
                try:
                    original, current = os.fstat(directory), os.fstat(visible)
                    if (original.st_dev, original.st_ino) != (current.st_dev, current.st_ino):
                        raise OSError('Maps root changed during installation')
                finally:
                    os.close(visible)
                _publish_directory(directory, temporary, ident)
                temporary = None
                os.fsync(directory)
                return metadata
            finally:
                try:
                    if temporary is not None and staging is not None:
                        _clear_directory(staging)
                        os.rmdir(temporary, dir_fd=directory)
                        os.fsync(directory)
                finally:
                    if staging is not None:
                        os.close(staging)
                    os.close(directory)

    def start(self, payload):
        import secrets
        if (not isinstance(payload, dict) or set(payload) != {'region_id', 'layers', 'online_preparation'}
                or payload['online_preparation'] is not True):
            raise ValueError('Explicit ONLINE PREPARATION confirmation required')
        region_id, layers = payload['region_id'], payload['layers']
        self.region(region_id)
        if (not isinstance(layers, list) or not layers or len(layers) > 2
                or any(not isinstance(layer, str) or layer not in LAYERS for layer in layers)
                or len(set(layers)) != len(layers)):
            raise ValueError('Choose roads and/or water')
        with self.lock:
            if any(job['state'] in ('queued', 'downloading', 'converting') for job in self.jobs.values()):
                raise ValueError('Another map operation is active')
            if len(self.jobs) >= 64:
                self.jobs.pop(next(iter(self.jobs)))
            ident = secrets.token_hex(12)
            job = {'id': ident, 'state': 'queued', 'region_id': region_id, 'layers': layers, 'installed': []}
            self.jobs[ident] = job
        def run():
            try:
                for layer in layers:
                    if any(pack['id'] == region_id + '-' + layer for pack in self.installed()):
                        raise ValueError(layer + ' already installed; remove it explicitly first')
                    # Check reserve before opening the network as well as before conversion.
                    if shutil.disk_usage(self.root.parent).free < RESERVE + MAX_EXPANDED + MAX_DATA + MAX_ZIP:
                        raise OSError('Insufficient map conversion headroom')
                    job.update(state='downloading', layer=layer)
                    raw = download(region_id, layer)
                    job.update(state='converting')
                    self.install(region_id, layer, raw)
                    job['installed'].append(region_id + '-' + layer)
                job.update(state='complete')
            except Exception as error:
                job.update(state='error', error=str(error)[:300])
        threading.Thread(target=run, daemon=True, name='map-preparation').start()
        return {'id': ident, 'state': 'queued'}

    def remove(self, ident):
        ident = self.pack_id(ident)
        with self.lock:
            directory = open_root(self.root)
            try:
                pack = os.open(ident, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                try:
                    _clear_directory(pack)
                    os.fsync(pack)
                finally:
                    os.close(pack)
                os.rmdir(ident, dir_fd=directory)
                os.fsync(directory)
            finally:
                os.close(directory)


def handle_get(handler):
    from urllib.parse import urlsplit, parse_qs
    path = urlsplit(handler.path).path
    manager = handler.app.maps
    query = parse_qs(urlsplit(handler.path).query)
    try:
        if path == '/api/maps/catalog':
            return handler.send_json(200, manager.catalog())
        if path == '/api/maps/installed':
            return handler.send_json(200, {'packs': manager.installed()})
        if path == '/api/maps/data':
            return handler.send_json(200, manager.data(query.get('id', [''])[0], query.get('layer', [''])[0]))
        if path.startswith('/api/maps/jobs/'):
            job = manager.jobs.get(path.rsplit('/', 1)[-1])
            return handler.send_json(200 if job else 404, dict(job) if job else {'error': 'Job not found; jobs are session-only'})
        return handler.send_json(404, {'error': 'Map endpoint not found'})
    except FileNotFoundError:
        return handler.send_json(404, {'error': 'Map layer not installed'})
    except (OSError, ValueError, KeyError) as error:
        return handler.send_json(400, {'error': str(error)[:300]})


def handle_post(handler):
    from urllib.parse import urlsplit, parse_qs
    path = urlsplit(handler.path).path
    importing = path == '/api/maps/import'
    expected_type = 'application/zip' if importing else 'application/json'
    if handler.headers.get_content_type() != expected_type:
        return handler.send_json(415, {'error': 'Expected ' + expected_type})
    if (handler.headers.get('Transfer-Encoding') or len(handler.headers.get_all('Content-Length', [])) != 1):
        return handler.send_json(400, {'error': 'One Content-Length required; no transfer encoding'})
    try:
        length = int(handler.headers['Content-Length'])
        if length <= 0 or length > (MAX_ZIP if importing else 8192):
            return handler.send_json(413, {'error': 'Map request exceeds size limit'})
        raw = handler.rfile.read(length)
        if len(raw) != length:
            raise ValueError('Incomplete request')
        manager = handler.app.maps
        if importing:
            query = parse_qs(urlsplit(handler.path).query)
            result = manager.install(query.get('region_id', [''])[0], query.get('layer', [''])[0], raw, imported=True)
            return handler.send_json(201, result)
        payload = json.loads(raw)
        if path == '/api/maps/download':
            return handler.send_json(202, manager.start(payload))
        if not isinstance(payload, dict) or set(payload) != {'id'}:
            raise ValueError('Expected map pack ID only')
        manager.remove(payload['id'])
        return handler.send_json(200, {'removed': payload['id']})
    except (ValueError, OSError, KeyError, RecursionError, UnicodeError) as error:
        return handler.send_json(400, {'error': str(error)[:300]})
    except Exception:
        return handler.send_json(400, {'error': 'Invalid or unsupported Census ZIP; nothing installed'})
