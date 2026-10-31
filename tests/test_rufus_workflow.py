"""The image job must exercise, not merely ship, the Rufus-like harness."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RufusWorkflowTests(unittest.TestCase):
    def test_workflow_runs_same_usb_acceptance_and_preserves_failure_evidence(self):
        workflow = (ROOT / '.github/workflows/build-live.yml').read_text()
        self.assertIn('name: Verify extracted UEFI and same-USB root persistence', workflow)
        section = workflow.split('name: Verify extracted UEFI and same-USB root persistence', 1)[1].split('      - name:', 1)[0]
        for text in ('set -euo pipefail', 'trap cleanup EXIT', '--memory 2500m',
                     '--cpus 1', '--cap-drop ALL', '--security-opt no-new-privileges',
                     'GRAVESTONE_TEST_ISO_SHA256="$pin"', 'target=/input/release.iso,readonly',
                     '--network none', 'scripts/rufus-test.Dockerfile',
                     'python3 /src/scripts/test-rufus-persistence.py',
                     'result.json', 'extract.log', 'fixture.log',
                     'command.json,serial.log,qemu.log,fsck.log',
                     'docker rm -f "$container"'):
            self.assertIn(text, section)
        dependencies = (ROOT / 'scripts/rufus-test.Dockerfile').read_text()
        for package in ('qemu-system-x86', 'ovmf', 'fdisk', 'mtools', 'dosfstools', 'e2fsprogs', 'python3', 'xorriso'):
            self.assertIn(package, dependencies)
        self.assertNotIn('--privileged', section)
        self.assertNotIn('usb.raw', section, 'never upload scratch USB or notebook storage')


if __name__ == '__main__':
    unittest.main()
