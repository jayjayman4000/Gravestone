import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen


class SystemStatusTests(unittest.TestCase):
    def test_real_storage_and_unavailable_battery_are_honest(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('app.system_status'), 'Real system telemetry is missing')
        from app.system_status import system_status
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = system_status(root, power_root=root / 'absent')
            self.assertGreater(result['storage']['free_bytes'], 0)
            self.assertGreater(result['storage']['total_bytes'], result['storage']['free_bytes'])
            self.assertEqual(result['battery']['status'], 'unavailable')
            self.assertIsNone(result['battery']['percent'])
            battery = root / 'power/BAT0'
            battery.mkdir(parents=True)
            (battery / 'type').write_text('Battery\n')
            (battery / 'capacity').write_text('73\n')
            (battery / 'status').write_text('Discharging\n')
            result = system_status(root, power_root=root / 'power')
            self.assertEqual(result['battery']['percent'], 73)
            self.assertEqual(result['battery']['status'], 'Discharging')

    def test_api_system_reports_actual_data_volume(self):
        from app import make_server
        with tempfile.TemporaryDirectory() as directory:
            server = make_server(content_dir=Path(directory) / 'content', data_dir=Path(directory) / 'data', port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f'http://127.0.0.1:{server.server_port}/api/system', timeout=3) as response:
                    result = json.load(response)
                self.assertGreater(result['storage']['free_bytes'], 0)
                self.assertIn(result['battery']['available'], (True, False))
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
