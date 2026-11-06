"""Deterministic cooldown tests; no inference or real sleeping."""
import importlib.util
import contextlib
import io
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/wait-for-host-load.py'


class HostLoadCooldownTests(unittest.TestCase):
    def load_helper(self):
        self.assertTrue(SCRIPT.is_file(), 'missing measured host-load cooldown')
        spec = importlib.util.spec_from_file_location('host_load_cooldown', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_waits_through_recorded_failures_and_exact_threshold(self):
        helper = self.load_helper()
        readings = iter([2.05029296875, 2.028, 2.0, 1.999])
        now = [0.0]
        sleeps = []
        logs = []

        def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        result = helper.wait_for_host_load(
            read_load=lambda: next(readings), clock=lambda: now[0],
            sleep=sleep, log=logs.append)
        self.assertEqual(result, 1.999)
        self.assertEqual(sleeps, [5, 5, 5])
        for value in ('2.050293', '2.028000', '2.000000', '1.999000'):
            self.assertTrue(any(value in line for line in logs), logs)

    def test_invalid_load_readings_fail_closed_without_sleeping(self):
        helper = self.load_helper()
        for value in (float('nan'), float('inf'), -1.0):
            with self.subTest(load=value):
                with self.assertRaisesRegex(ValueError, 'invalid.*load1='):
                    helper.wait_for_host_load(
                        read_load=lambda: value, clock=lambda: 0,
                        sleep=lambda _: self.fail('invalid measurement must fail immediately'),
                        log=lambda _: None)

    def test_sustained_load_fails_closed_after_five_minutes(self):
        helper = self.load_helper()
        now = [0.0]
        logs = []

        def sleep(seconds):
            now[0] += seconds
            if now[0] > 300:
                self.fail('cooldown exceeded its five-minute budget')

        with self.assertRaisesRegex(TimeoutError, '300.*load1=2.050293'):
            helper.wait_for_host_load(
                read_load=lambda: 2.05029296875, clock=lambda: now[0],
                sleep=sleep, log=logs.append)
        self.assertEqual(now[0], 300)
        self.assertIn('elapsed=300.0s', logs[-1])

    def test_cli_logs_real_api_measurement_before_success(self):
        output = io.StringIO()
        with patch('os.getloadavg', return_value=(1.5, 9, 9)) as reading:
            with contextlib.redirect_stdout(output):
                runpy.run_path(str(SCRIPT), run_name='__main__')
        reading.assert_called_once_with()
        self.assertIn('load1=1.500000', output.getvalue())

    def test_cli_measurement_failure_returns_nonzero(self):
        error = io.StringIO()
        with patch('os.getloadavg', side_effect=OSError('load unavailable')):
            with contextlib.redirect_stderr(error):
                with self.assertRaises(SystemExit) as raised:
                    runpy.run_path(str(SCRIPT), run_name='__main__')
        self.assertEqual(raised.exception.code, 1)
        self.assertIn('load unavailable', error.getvalue())

    def test_idle_host_returns_without_sleep(self):
        helper = self.load_helper()
        self.assertEqual(helper.wait_for_host_load(
            read_load=lambda: 0.25, clock=lambda: 0,
            sleep=lambda _: self.fail('idle host must not sleep'), log=lambda _: None), 0.25)

    def test_sleep_is_clipped_to_remaining_deadline(self):
        helper = self.load_helper()
        times = iter([0, 298, 300])
        sleeps = []
        with self.assertRaises(TimeoutError):
            helper.wait_for_host_load(
                read_load=lambda: 2, clock=lambda: next(times),
                sleep=sleeps.append, log=lambda _: None)
        self.assertEqual(sleeps, [2])

    def test_low_reading_after_oversleep_cannot_pass_deadline(self):
        helper = self.load_helper()
        times = iter([0, 0, 301])
        loads = iter([2.05, 0.5])
        with self.assertRaises(TimeoutError):
            helper.wait_for_host_load(
                read_load=lambda: next(loads), clock=lambda: next(times),
                sleep=lambda _: None, log=lambda _: None)

    def test_cli_timeout_returns_nonzero_and_logs_last_measurement(self):
        output, error = io.StringIO(), io.StringIO()
        with patch('os.getloadavg', return_value=(2.05, 0, 0)):
            with patch('time.monotonic', side_effect=[0, 300]):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        runpy.run_path(str(SCRIPT), run_name='__main__')
        self.assertEqual(raised.exception.code, 1)
        self.assertIn('load1=2.050000', output.getvalue())
        self.assertIn('timed out after 300s', error.getvalue())

    def test_actual_shell_gate_stops_before_overview_on_cooldown_failure(self):
        build = (ROOT / 'scripts/build-live.sh').read_text()
        start = build.index('python3 -u "$repo/scripts/wait-for-host-load.py"')
        block = build[start:build.index('\ncp --', start)]
        # Command-dispatch fixture only: no real inference, build, or sleeping.
        for status in (0, 1):
            with self.subTest(cooldown_status=status):
                fixture = '''set -euo pipefail
repo=/fixture app_root=/fixture out=/fixture
python3() {
    if [[ "$*" == *wait-for-host-load.py* ]]; then
        printf 'cooldown\\n'
        return STATUS
    fi
    printf 'overview\\n'
}
'''.replace('STATUS', str(status))
                result = subprocess.run(['bash', '-c', fixture + block],
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(result.stdout.splitlines(),
                                 ['cooldown', 'overview'] if status == 0 else ['cooldown'])


if __name__ == '__main__':
    unittest.main()
