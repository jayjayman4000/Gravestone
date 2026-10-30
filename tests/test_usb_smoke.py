"""Exercise the shell smoke runner's QEMU argument assembly, without a VM."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class USBImageSmokeTests(unittest.TestCase):
    def test_raw_usb_boot_has_no_optical_media_attached(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            tools = base / 'bin'
            tools.mkdir()
            calls = base / 'calls.jsonl'
            qemu = tools / 'qemu-system-x86_64'
            qemu.write_text('#!' + sys.executable + '\n' + '''import json, os, sys, time
with open(os.environ['QEMU_CALLS'], 'a') as f:
    f.write(json.dumps(sys.argv[1:]) + '\\n')
if '-kernel' in sys.argv:
    print('GRAVESTONE_BOOT_OK', flush=True)
else:
    print('GRAVESTONE_SERVICE_READY', flush=True)
    time.sleep(3)
''')
            qemu.chmod(0o755)
            xorriso = tools / 'xorriso'
            xorriso.write_text('#!/bin/sh\nexit 0\n')
            xorriso.chmod(0o755)
            for name in ('OVMF_VARS_4M.fd', 'OVMF_CODE_4M.fd', 'test.iso'):
                (base / name).write_bytes(b'fixture')
            env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'],
                       OVMF_DIR=str(base), QEMU_CALLS=str(calls))
            result = subprocess.run(['bash', str(ROOT / 'scripts/smoke-iso.sh'),
                                     str(base / 'test.iso'), str(base / 'logs')],
                                    env=env, capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            invocations = [json.loads(line) for line in calls.read_text().splitlines()]
            usb = [args for args in invocations if any('usb-storage,' in arg for arg in args)]
            self.assertEqual(len(usb), 1, 'Need a distinct raw USB firmware boot, not only CD-ROM boots')
            self.assertNotIn('-cdrom', usb[0], 'A fallback CD could hide a USB boot failure')
            self.assertTrue(any('removable=on' in arg for arg in usb[0]))
            self.assertTrue(any('readonly=on' in arg and 'test.iso' in arg for arg in usb[0]))
            self.assertEqual(len(invocations), 4)
            self.assertIn('UEFI-USB', result.stdout)

if __name__ == '__main__':
    unittest.main()
