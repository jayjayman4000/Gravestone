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

    def test_sysfs_fixture_is_reread_for_charge_unplug_full_and_removal(self):
        """Temporary sysfs-shaped files, not a claim about physical hardware."""
        from app.system_status import system_status
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            power = root / 'power'
            device = power / 'BAT0'
            device.mkdir(parents=True)
            (device / 'type').write_text('Battery\n')
            for capacity, status in [(73, 'Charging'), (72, 'Discharging'),
                                     (100, 'Full'), (100, 'Not charging'), (0, 'Unknown')]:
                with self.subTest(capacity=capacity, status=status):
                    (device / 'capacity').write_text(f'{capacity}\n')
                    (device / 'status').write_text(f'{status}\n')
                    result = system_status(root, power_root=power)
                    self.assertTrue(result['battery']['available'])
                    self.assertEqual(result['battery']['percent'], capacity)
                    self.assertEqual(result['battery']['status'], status)
                    self.assertTrue(result['storage']['available'])
            (device / 'capacity').unlink()
            missing = system_status(root, power_root=power)
            self.assertFalse(missing['battery']['available'])
            self.assertIsNone(missing['battery']['percent'])
            (device / 'capacity').write_text('71\n')
            (device / 'status').write_text('Discharging\n')
            recovered = system_status(root, power_root=power)
            self.assertEqual(recovered['battery']['percent'], 71)
            self.assertEqual(recovered['battery']['status'], 'Discharging')

    def test_invalid_capacity_or_missing_data_volume_are_unavailable(self):
        from app.system_status import system_status
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = root / 'power/BAT0'
            device.mkdir(parents=True)
            (device / 'type').write_text('Battery\n')
            (device / 'status').write_text('Charging\n')
            for capacity in ['-1', '101', 'not a number']:
                with self.subTest(capacity=capacity):
                    (device / 'capacity').write_text(capacity)
                    result = system_status(root / 'missing', power_root=root / 'power')
                    self.assertFalse(result['battery']['available'])
                    self.assertIsNone(result['battery']['percent'])
                    self.assertFalse(result['storage']['available'])
                    self.assertIsNone(result['storage']['free_bytes'])

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
