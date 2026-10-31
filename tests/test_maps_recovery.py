"""Offline restart checks use disposable data, port 0, and actual HTTP subprocesses.

Opt in to official Arlington downloads with GRAVESTONE_REAL_MAP_RECOVERY=1.
No test reads a user's notebook. Evidence/originals stay outside the checkout.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from app import maps
from app.backup import export_backup, restore_backup

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = Path('/home/jayjayman4000/gravestone-test-evidence/map-backup-recovery')

# A separate interpreter is killed/recreated, not just a new Python object.
SERVER = r'''
import json, os, socket, sys, urllib.request
from pathlib import Path
from app import make_server, maps

def forbidden(*args, **kwargs):
    raise AssertionError('Online map/network call forbidden in offline phase')

server = make_server(content_dir=Path(sys.argv[1]), data_dir=Path(sys.argv[2]), port=0)
for layer, filename in json.loads(sys.argv[3]).items():
    server.maps.install('51013', layer, Path(filename).read_bytes(), imported=False)
maps.download = forbidden
maps.build_opener = forbidden
urllib.request.urlopen = forbidden
urllib.request.OpenerDirector.open = forbidden
connect = socket.socket.connect
connect_ex = socket.socket.connect_ex
def offline_connect(sock, address):
    if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1'):
        return forbidden(address)
    return connect(sock, address)
def offline_connect_ex(sock, address):
    if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1'):
        return forbidden(address)
    return connect_ex(sock, address)
socket.socket.connect = offline_connect
socket.socket.connect_ex = offline_connect_ex
# Prove all guards really raise without touching a network.
for probe in (lambda: maps.download('51013', 'roads'),
              lambda: urllib.request.urlopen('https://www2.census.gov/'),
              lambda: socket.socket().connect(('192.0.2.1', 443))):
    try:
        probe()
    except AssertionError:
        pass
    else:
        raise AssertionError('Offline guard was ineffective')
print(json.dumps({'port': server.server_port, 'pid': os.getpid(),
                  'network_guards_selftested': True}), flush=True)
server.serve_forever()
'''


@contextmanager
def server_process(data, originals=None):
    process = subprocess.Popen([sys.executable, '-c', SERVER, str(REPO / 'content'), str(data),
                                json.dumps(originals or {})], cwd=REPO,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready = selectors.DefaultSelector()
        try:
            ready.register(process.stdout, selectors.EVENT_READ)
            if not ready.select(timeout=60):
                raise AssertionError('Scratch server failed readiness deadline')
            line = process.stdout.readline()
        finally:
            ready.close()
        if not line:
            raise AssertionError('Scratch server exited: ' + process.stderr.read())
        yield json.loads(line)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        process.stdout.close()
        process.stderr.close()


def request(port, path, payload=None):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=15)
    try:
        body = None if payload is None else json.dumps(payload).encode()
        headers = {'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json'}
        connection.request('GET' if payload is None else 'POST', path, body, headers)
        response = connection.getresponse()
        raw = response.read(40 * 1024 * 1024)
        if response.status != 200:
            raise AssertionError(f'HTTP {response.status}: {raw[:500]!r}')
        return json.loads(raw)
    finally:
        connection.close()


def hashes(data):
    return {p.relative_to(data).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(data.rglob('*')) if p.is_file()}


def fixture():
    from app._vendor import shapefile
    streams = [io.BytesIO() for _ in range(3)]
    writer = shapefile.Writer(shp=streams[0], shx=streams[1], dbf=streams[2], shapeType=3)
    writer.field('FULLNAME', 'C', 80)
    writer.field('MTFCC', 'C', 5)
    writer.line([[[-77.1, 38.8], [-77.09, 38.81]]])
    writer.record('Fixture only', 'S1100')
    writer.close()
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as archive:
        for ext, stream in zip(('shp', 'shx', 'dbf'), streams):
            archive.writestr(f'tl_2025_51013_roads.{ext}', stream.getvalue())
        archive.writestr('tl_2025_51013_roads.prj', 'GEOGCS["GCS_North_American_1983"]')
    return raw.getvalue()


class MapsRecoveryTests(unittest.TestCase):
    def verify_http(self, data, state, expected_layers):
        self.assertTrue(state['network_guards_selftested'])
        installed = request(state['port'], '/api/maps/installed')['packs']
        self.assertEqual(sorted(p['layer'] for p in installed), sorted(expected_layers))
        results = {}
        for meta in installed:
            pack = data / 'maps' / meta['id']
            self.assertEqual(meta, json.loads((pack / 'metadata.json').read_bytes()))
            geometry = request(state['port'], f"/api/maps/data?id={meta['id']}&layer={meta['layer']}")
            self.assertEqual(geometry, json.loads((pack / 'data.geojson').read_bytes()))
            self.assertEqual(geometry['type'], 'FeatureCollection')
            self.assertEqual(len(geometry['features']), meta['features'])
            self.assertGreater(meta['features'], 0)
            self.assertEqual(hashlib.sha256((pack / 'original.zip').read_bytes()).hexdigest(), meta['sha256'])
            self.assertEqual(hashlib.sha256((pack / 'data.geojson').read_bytes()).hexdigest(), meta['data_sha256'])
            results[meta['id']] = {'metadata': meta, 'http_geometry_exact': True,
                                   'feature_count': len(geometry['features'])}
        return results

    def test_fixture_process_restart_backup_restore_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'data'
            raw = root / 'original.zip'
            raw.write_bytes(fixture())
            with server_process(source, {'roads': str(raw)}) as first:
                request(first['port'], '/api/notes', {'text': 'Disposable notebook — exact\n'})
                self.verify_http(source, first, ['roads'])
            before = hashes(source)
            with server_process(source) as second:
                self.verify_http(source, second, ['roads'])
                self.assertEqual(request(second['port'], '/api/notes')['text'], 'Disposable notebook — exact\n')
            export_backup(source, root / 'backup.tar')
            fresh = root / 'recovered'
            restore_backup(root / 'backup.tar', fresh)
            self.assertEqual(hashes(fresh), before)
            with server_process(fresh) as third:
                self.verify_http(fresh, third, ['roads'])
            self.assertEqual(len({first['pid'], second['pid'], third['pid']}), 3)

    @unittest.skipUnless(os.environ.get('GRAVESTONE_REAL_MAP_RECOVERY') == '1',
                         'Opt-in official Census download; normal tests stay network-free')
    def test_real_arlington_roads_water_process_restart_and_recovery(self):
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        run = Path(tempfile.mkdtemp(prefix='official-arlington-', dir=EVIDENCE))
        originals = run / 'publisher-originals'
        originals.mkdir()
        provenance, original_paths, total = [], {}, 0
        for layer in ('roads', 'water'):
            # Preparation is the only online phase. Keep the full batch below 50 MiB.
            with patch.object(maps, 'MAX_ZIP', 50 * 1024 * 1024 - total):
                raw = maps.download('51013', layer)
            total += len(raw)
            self.assertLessEqual(total, 50 * 1024 * 1024)
            path = originals / f'51013-{layer}.zip'
            path.write_bytes(raw)
            original_paths[layer] = str(path)
            provenance.append({'url': maps.source_url('51013', layer), 'bytes': len(raw),
                               'sha256': hashlib.sha256(raw).hexdigest(), 'file': str(path),
                               'retrieved_at': datetime.now(timezone.utc).isoformat()})
        (run / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
        source = run / 'scratch-data'
        text = 'SCRATCH ONLY: human notebook persistence check.\nNo actual personal notes.\n'
        phases = []
        with server_process(source, original_paths) as first:
            request(first['port'], '/api/notes', {'text': text})
            phases.append({'phase': 'initial-install', **first,
                           'packs': self.verify_http(source, first, ['roads', 'water'])})
        before = hashes(source)
        with server_process(source) as second:
            self.assertEqual(request(second['port'], '/api/notes')['text'], text)
            phases.append({'phase': 'offline-process-restart', **second,
                           'packs': self.verify_http(source, second, ['roads', 'water'])})
        archive = run / 'scratch-backup.tar'
        manifest = export_backup(source, archive)
        restored = run / 'new-restored-data'
        restore_backup(archive, restored)
        self.assertEqual(hashes(restored), before)
        with server_process(restored) as third:
            self.assertEqual(request(third['port'], '/api/notes')['text'], text)
            phases.append({'phase': 'offline-restored-process', **third,
                           'packs': self.verify_http(restored, third, ['roads', 'water'])})
        self.assertEqual(len({first['pid'], second['pid'], third['pid']}), 3)
        self.assertEqual(hashes(source), before)
        result = {'passed': True, 'completed_at': datetime.now(timezone.utc).isoformat(),
                  'scratch_only': True, 'originals': provenance, 'phases': phases,
                  'files_before': before, 'files_restored': hashes(restored), 'manifest': manifest,
                  'archive': {'path': str(archive), 'bytes': archive.stat().st_size,
                              'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()},
                  'network_isolation': 'Python raising download/urllib and non-loopback socket guards, self-tested in each child; NOT a network namespace',
                  'physical_reboot_tested': False,
                  'limitations': maps.LIMITATION}
        (run / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        (EVIDENCE / 'latest-result.json').write_text(json.dumps(result, indent=2) + '\n')
        print('Official map recovery evidence: ' + str(run / 'result.json'))


if __name__ == '__main__':
    unittest.main()
