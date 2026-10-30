"""Map fixtures are geometry only, never survival guidance."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


class CatalogTests(unittest.TestCase):
    def test_catalog_is_offline_national_county_selection_with_official_provenance(self):
        self.assertIsNotNone(importlib.util.find_spec('app.maps'), 'Map packs are not implemented')
        from app.maps import MapManager
        with tempfile.TemporaryDirectory() as directory:
            manager = MapManager(Path(directory))
            catalog = manager.catalog()
            self.assertEqual(catalog['year'], 2025)
            self.assertGreater(len(catalog['regions']), 3000)
            self.assertGreater(len({r['state'] for r in catalog['regions']}), 50)
            self.assertTrue(any(r['id'] == '11001' for r in catalog['regions']))
            self.assertTrue(catalog['source_url'].startswith('https://www2.census.gov/'))
            self.assertEqual(manager.installed(), [])
            self.assertEqual(list(Path(directory).iterdir()), [])


class PackTests(unittest.TestCase):
    def archive(self, region='11001', layer='roads'):
        import io
        import zipfile
        from app._vendor import shapefile
        shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
        writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=3)
        writer.field('FULLNAME', 'C', 80)
        writer.field('MTFCC', 'C', 5)
        writer.line([[[-77.04, 38.9], [-77.03, 38.91]]])
        writer.record('Fixture Road', 'S1100')
        writer.close()
        raw = io.BytesIO()
        suffix = 'roads' if layer == 'roads' else 'linearwater'
        with zipfile.ZipFile(raw, 'w') as archive:
            for extension, stream in [('shp', shp), ('shx', shx), ('dbf', dbf)]:
                archive.writestr(f'tl_2025_{region}_{suffix}.{extension}', stream.getvalue())
            archive.writestr(f'tl_2025_{region}_{suffix}.prj', 'GEOGCS["GCS_North_American_1983"]')
        return raw.getvalue()

    def test_import_installs_original_and_real_named_line_geometry_atomically(self):
        import hashlib
        from app.maps import MapManager
        with tempfile.TemporaryDirectory() as directory:
            manager = MapManager(Path(directory))
            original = self.archive()
            pack = manager.install('11001', 'roads', original, imported=True)
            self.assertEqual(pack['sha256'], hashlib.sha256(original).hexdigest())
            self.assertEqual(pack['features'], 1)
            self.assertEqual(len(manager.installed()), 1)
            data = manager.data('11001-roads', 'roads')
            self.assertEqual(data['features'][0]['properties']['name'], 'Fixture Road')
            self.assertEqual(data['features'][0]['geometry']['coordinates'][0][0], [-77.04, 38.9])
            with self.assertRaises(ValueError):
                manager.install('11001', 'roads', original, imported=True)
            self.assertEqual(len(manager.installed()), 1)
            self.assertEqual((manager.root / '11001-roads' / 'original.zip').read_bytes(), original)
            manager.remove('11001-roads')
            self.assertEqual(manager.installed(), [])

    def test_install_confines_writes_when_root_or_ancestor_is_replaced_during_conversion(self):
        from unittest.mock import patch
        from app.maps import MapManager, convert
        for replace_ancestor in (False, True):
            with self.subTest(replace_ancestor=replace_ancestor), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                data = base / 'data'
                manager = MapManager(data)
                outside = base / 'outside'
                outside.mkdir()
                if replace_ancestor:
                    (outside / 'maps').mkdir()
                moved = base / 'validated'

                def swap(raw, region, layer):
                    result = convert(raw, region, layer)
                    target = data if replace_ancestor else manager.root
                    target.rename(moved)
                    target.symlink_to(outside, target_is_directory=True)
                    return result

                error = None
                with patch('app.maps.convert', side_effect=swap):
                    try:
                        manager.install('11001', 'roads', self.archive(), imported=True)
                    except (OSError, ValueError) as caught:
                        error = caught
                outside_maps = outside / 'maps' if replace_ancestor else outside
                self.assertEqual(list(outside_maps.iterdir()), [], 'Install wrote outside validated maps root')
                self.assertIsNotNone(error, 'Changed visible root must fail before publication')
                validated_maps = moved / 'maps' if replace_ancestor else moved
                self.assertEqual(list(validated_maps.iterdir()), [], 'Failed install left staging or a published pack')

    def test_install_does_not_replace_layer_created_during_conversion(self):
        from unittest.mock import patch
        from app.maps import MapManager, convert
        with tempfile.TemporaryDirectory() as directory:
            manager = MapManager(Path(directory))
            existing = manager.root / '11001-roads'
            original_inode = None

            def create_existing(raw, region, layer):
                nonlocal original_inode
                result = convert(raw, region, layer)
                existing.mkdir()
                original_inode = existing.stat().st_ino
                return result

            error = None
            with patch('app.maps.convert', side_effect=create_existing):
                try:
                    manager.install('11001', 'roads', self.archive(), imported=True)
                except (OSError, ValueError) as caught:
                    error = caught
            self.assertIsNotNone(error, 'Publication silently replaced an existing layer')
            self.assertEqual(existing.stat().st_ino, original_inode)
            self.assertEqual(list(existing.iterdir()), [])
            self.assertEqual(list(manager.root.iterdir()), [existing])

    def test_remove_confines_deletion_when_root_or_ancestor_is_replaced_after_validation(self):
        from unittest.mock import patch
        from app import open_root
        from app.maps import MapManager
        for replace_ancestor in (False, True):
            with self.subTest(replace_ancestor=replace_ancestor), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                data = base / 'data'
                manager = MapManager(data)
                manager.install('11001', 'roads', self.archive(), imported=True)
                outside = base / 'outside'
                outside_maps = outside / 'maps' if replace_ancestor else outside
                outside_pack = outside_maps / '11001-roads'
                outside_pack.mkdir(parents=True)
                marker = outside_pack / 'keep'
                marker.write_bytes(b'external content')
                moved = base / 'validated'
                swapped = False

                def swap(path, create=False):
                    nonlocal swapped
                    descriptor = open_root(path, create=create)
                    if not swapped:
                        swapped = True
                        target = data if replace_ancestor else manager.root
                        target.rename(moved)
                        target.symlink_to(outside, target_is_directory=True)
                    return descriptor

                with patch('app.maps.open_root', side_effect=swap):
                    manager.remove('11001-roads')
                self.assertTrue(marker.exists(), 'Removal deleted outside validated maps root')
                self.assertEqual(marker.read_bytes(), b'external content')
                validated_maps = moved / 'maps' if replace_ancestor else moved
                self.assertEqual(list(validated_maps.iterdir()), [])

    def test_rejects_unsafe_archives_unknown_regions_and_layers(self):
        import io
        import zipfile
        from app.maps import MapManager, convert, source_url
        with tempfile.TemporaryDirectory() as directory:
            manager = MapManager(Path(directory))
            for region, layer in [('99999', 'roads'), ('../11', 'roads'), ('11001', 'https://evil')]:
                with self.assertRaises(ValueError):
                    manager.install(region, layer, self.archive(), imported=True)
            for name in ['../escape', '/tmp/escape', 'tl_2025_11001_roads.shp/evil', 'tl_2025_11001_roads..shp']:
                raw = io.BytesIO()
                with zipfile.ZipFile(raw, 'w') as archive:
                    archive.writestr(name, 'bad')
                with self.assertRaises(ValueError):
                    convert(raw.getvalue(), '11001', 'roads')
            self.assertEqual(manager.installed(), [])
            with self.assertRaises(ValueError):
                source_url('11001/../../secret', 'roads')


class MapHTTPTests(unittest.TestCase):
    def test_routes_are_offline_by_default_and_mutations_require_same_origin_and_preparation(self):
        import threading
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from unittest.mock import patch
        from app import make_server
        with tempfile.TemporaryDirectory() as directory:
            server = make_server(content_dir=Path(directory) / 'content', data_dir=Path(directory) / 'data', port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            def call(path, body=None, origin=None):
                headers = {'Content-Type': 'application/json'}
                if origin:
                    headers['Origin'] = origin
                try:
                    response = urlopen(Request(base + path, data=body, headers=headers), timeout=3)
                except HTTPError as error:
                    response = error
                with response:
                    return response.status, json.load(response)
            try:
                with patch('app.maps.download', side_effect=AssertionError('Unexpected network')):
                    self.assertEqual(call('/api/maps/catalog')[0], 200)
                    self.assertEqual(call('/api/maps/installed'), (200, {'packs': []}))
                    body = json.dumps({'region_id': '11001', 'layers': ['roads']}).encode()
                    self.assertEqual(call('/api/maps/download', body)[0], 403)
                    self.assertEqual(call('/api/maps/download', body, base)[0], 400)
                    body = json.dumps({'region_id': '99999', 'layers': ['roads'], 'online_preparation': True}).encode()
                    self.assertEqual(call('/api/maps/download', body, base)[0], 400)
                import time
                body = json.dumps({'region_id': '11001', 'layers': ['roads'], 'online_preparation': True}).encode()
                with patch('app.maps.download', return_value=PackTests().archive()):
                    code, result = call('/api/maps/download', body, base)
                    self.assertEqual(code, 202)
                    for _ in range(100):
                        _, job = call('/api/maps/jobs/' + result['id'])
                        if job['state'] in ('complete', 'error'):
                            break
                        time.sleep(.01)
                    self.assertEqual(job['state'], 'complete', job)
                    self.assertEqual(len(call('/api/maps/installed')[1]['packs']), 1)
                    code, data = call('/api/maps/data?id=11001-roads&layer=roads')
                    self.assertEqual(code, 200)
                    self.assertEqual(data['features'][0]['properties']['name'], 'Fixture Road')
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class RendererTests(unittest.TestCase):
    def test_local_pack_bounds_can_zoom_to_streets_without_changing_overview_math(self):
        import shutil
        import subprocess
        if not shutil.which('node'):
            self.skipTest('Node unavailable')
        path = Path(__file__).resolve().parents[1] / 'app/static/map.js'
        result = subprocess.run(['node', '-e', '''
const assert = require('node:assert/strict');
const {fitBounds, projectPoint, changeView} = require(process.argv[1]);
assert.equal(typeof fitBounds, 'function', 'Street packs need a local-scale view');
assert(Number.isFinite(fitBounds([-77.1,38.8,-76.9,39],0,0).zoom), 'Hidden map must not poison the view');
const view = fitBounds([-77.1,38.8,-76.9,39], 800, 600);
assert(view.zoom > 100);
assert.deepEqual(projectPoint(-77,38.9,view,800,600),[400,300]);
assert(changeView(view,0,0,100).zoom > 1000);
assert.equal(changeView({lon:0,lat:0,zoom:1},0,0,100).zoom,16);
''', str(path)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
