"""Deterministic real socket/child fixtures, NOT VM persistence acceptance."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / 'scripts' / (name + '.py'))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SerialTail(unittest.TestCase):
    def fixture(self, h, root, marker, phase=1, exitcode=0, final_marker=True):
        first = 'fixture-token: boot one\nUTF-8: 雪\n<literal & text>\n'
        second = first + 'Updated during boot two\n'
        record = {'phase': phase, 'before': ['', first, second][phase - 1],
                  'after': first if phase == 1 else second,
                  'boot_id': f'{phase:08d}-1111-4111-8111-111111111111',
                  'cmdline': ' '.join(getattr(h, 'REQUIRED_ARGS', ()))}
        prefix = (marker + '=' + json.dumps(record) + '\n').encode()
        # More than one recv: final marker remains buffered AFTER child exit.
        tail = b'[137.939560] reboot: Power down\r\n' if final_marker else b'truncated shutdown\r\n'
        payload = prefix.ljust(65536, b'.') + tail
        fixture = root / f'fixture-{phase}.bin'
        fixture.write_bytes(payload)
        code = ('import socket,sys,pathlib; s=socket.socket(socket.AF_UNIX); '
                's.bind(sys.argv[1]); s.listen(1); c,_=s.accept(); '
                'c.sendall(pathlib.Path(sys.argv[2]).read_bytes()); c.close(); s.close(); '
                'sys.exit(int(sys.argv[3]))')
        return [sys.executable, '-c', code, str(root / 'serial.sock'), str(fixture), str(exitcode)], payload

    def ordered_socket(self, real_socket, spawned, clock=None):
        """Force exit before first recv returns, with real bytes still queued."""
        conn = real_socket(socket.AF_UNIX)

        class OrderedSocket:
            first = True

            def recv(self, size):
                if self.first:
                    self.first = False
                    spawned[-1].wait(timeout=5)
                data = conn.recv(size)
                if not data and clock is not None:
                    # A peer that never sends EOF must not extend the boot budget.
                    clock[0] += 100
                    raise socket.timeout()
                return data

            def __getattr__(self, name):
                return getattr(conn, name)

        return OrderedSocket()

    def run_direct_fixture(self, exitcode=0, final_marker=True, failure=False, withhold_eof=False):
        h = load('test-persistence')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            iso = root / 'release.iso'
            iso.write_bytes(b'fixture ISO, not bootable')
            evidence = root / 'evidence'
            spawned, payloads = [], []
            clock = [0]
            if withhold_eof:
                setattr(h, 'time', SimpleNamespace(monotonic=lambda: clock[0], sleep=time.sleep))
            real_popen, real_socket = subprocess.Popen, socket.socket

            def mapped_path(value):
                return {'/input/release.iso': iso, '/evidence': evidence,
                        '/.dockerenv': iso}.get(str(value), Path(value))

            def command(*args):
                cmd, payload = self.fixture(h, evidence, 'PERSISTENCE_RESULT', len(payloads) + 1,
                                            exitcode=exitcode, final_marker=final_marker)
                payloads.append(payload)
                return cmd

            def start(*args, **kwargs):
                proc = real_popen(*args, **kwargs)
                spawned.append(proc)
                return proc

            with patch.object(h, 'Path', side_effect=mapped_path), \
                    patch.object(h, 'expected_iso_digest', return_value=hashlib.sha256(iso.read_bytes()).hexdigest()), \
                    patch.object(h, 'vm_command', side_effect=command), \
                    patch.object(h.subprocess, 'run') as tools, \
                    patch.object(h.subprocess, 'Popen', side_effect=start), \
                    patch.object(h.socket, 'socket', side_effect=lambda *a: self.ordered_socket(
                        real_socket, spawned, clock if withhold_eof else None)):
                if failure:
                    with self.assertRaisesRegex(AssertionError, 'clean kernel poweroff missing'):
                        h.run()
                else:
                    h.run()
            result = json.loads((evidence / 'result.json').read_text())
            self.assertEqual(result['passed'], not failure)
            self.assertEqual(len(result['boots']), 0 if failure else 3)
            self.assertEqual([p.returncode for p in spawned], [exitcode] * (1 if failure else 3))
            self.assertEqual(sum(call.args[0][0] == 'e2fsck' for call in tools.call_args_list),
                             0 if failure else 3)
            for call in tools.call_args_list:
                if call.args[0][0] == 'e2fsck':
                    self.assertEqual(call.args[0][1], '-fn')
                    self.assertTrue(call.kwargs['check'])
            for phase, payload in enumerate(payloads, 1):
                self.assertEqual((evidence / f'boot-{phase}-serial.log').read_bytes(), payload)
            if failure:
                diagnostic = result['failed_boot']
                self.assertEqual(diagnostic['phase'], 1)
                self.assertEqual(diagnostic['qemu_exit'], exitcode)
                self.assertEqual(diagnostic['serial_bytes'], len(payloads[0]))
                self.assertEqual(diagnostic['serial_tail'], payloads[0][-2048:].decode())
                self.assertTrue(diagnostic['serial_eof'])
            if withhold_eof:
                self.assertEqual(clock[0], 900, 'three original 300-second budgets; no added drain budget')

    def test_direct_harness_drains_final_marker_after_child_exit(self):
        self.run_direct_fixture()

    def test_missing_poweroff_marker_fails_with_actual_exit_and_tail(self):
        self.run_direct_fixture(final_marker=False, failure=True)

    def test_nonzero_exit_still_fails_with_poweroff_marker(self):
        self.run_direct_fixture(exitcode=7, failure=True)

    def test_post_exit_drain_keeps_original_deadline_without_eof(self):
        self.run_direct_fixture(withhold_eof=True)

    def test_rufus_existing_drain_retains_buffered_final_marker(self):
        h = load('test-rufus-persistence')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args, payload = self.fixture(h, root, 'RUFUS_PERSISTENCE_RESULT')
            spawned = []
            real_popen, real_socket = subprocess.Popen, socket.socket

            def start(*args, **kwargs):
                proc = real_popen(*args, **kwargs)
                spawned.append(proc)
                return proc

            with patch.object(h.subprocess, 'Popen', side_effect=start), \
                    patch.object(h.socket, 'socket', side_effect=lambda *a: self.ordered_socket(real_socket, spawned)), \
                    patch.object(h, 'validate_mounts'):
                record = h.boot_once(args, root, 1, 'fixture-token', timeout=5)
            self.assertTrue(record['clean_poweroff'])
            self.assertEqual((root / 'boot-1-serial.log').read_bytes(), payload)


if __name__ == '__main__':
    unittest.main()
