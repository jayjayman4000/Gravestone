"""Immutable-ISO networking diagnostic only; fixture execution is not VM acceptance."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest
from test_reverify_workflow import ReverifyWorkflowTests as GuardFixtures

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/diagnose-networking.yml'
IMAGE_SOURCE = 'f483c265a417511a38c0eb4cc01b79f37d932ab5'
IMAGE_RUN = '42164540994'
IMAGE_SHA = '6b0c38671887cd54a8fbc7ac486e52bc628c35172e23de83a643b691bb7bf2ce'


class NetworkingDiagnosticWorkflowTests(unittest.TestCase):
    # Execute the exact new guard/checksum shell blocks in real disposable Git
    # and byte fixtures, including self-consistent replacement rejection.
    step = GuardFixtures.step
    run_block = GuardFixtures.run_block
    test_source_guard_rejects_every_image_payload_change_but_allows_harness_changes = (
        GuardFixtures.test_source_guard_rejects_every_image_payload_change_but_allows_harness_changes)
    test_download_exact_run_and_fail_closed_on_iso_or_checksum_drift = (
        GuardFixtures.test_download_exact_run_and_fail_closed_on_iso_or_checksum_drift)
    test_every_run_block_has_valid_bash_syntax = GuardFixtures.test_every_run_block_has_valid_bash_syntax

    def workflow(self):
        self.assertTrue(WORKFLOW.is_file(), 'missing immutable-ISO networking diagnostic workflow')
        return WORKFLOW.read_text()

    def test_manual_pins_full_history_and_diagnostic_only_gate(self):
        workflow = self.workflow()
        self.assertRegex(workflow, r'(?m)^on:\n  workflow_dispatch:\s*\npermissions:')
        self.assertNotIn('inputs:', workflow)
        for key, value in (('IMAGE_SOURCE_COMMIT', IMAGE_SOURCE), ('IMAGE_RUN_ID', IMAGE_RUN),
                           ('IMAGE_ISO_SHA256', IMAGE_SHA),
                           ('IMAGE_ARTIFACT', 'gravestone-0.4.2-amd64')):
            self.assertRegex(workflow, rf'(?m)^  {key}: [\'\"]?{value}[\'\"]?$')
        self.assertIn('contents: read\n  actions: read', workflow)
        self.assertIn('fetch-depth: 0', workflow)
        self.assertNotIn('ref:', workflow)
        original = (ROOT / '.github/workflows/build-live.yml').read_text()
        name = 'Verify explicit networking opt-in and offline reading'
        self.assertEqual(self.step(name).rstrip(), self.step(name, original).rstrip(),
                         'reuse original networking limits, cleanup, and assertions verbatim')
        for forbidden in ('test-persistence.py', 'test-rufus-persistence.py', 'smoke-iso.sh',
                          'prepare-live.sh', 'prepare-ai.sh', 'scripts/build-live.sh',
                          '--privileged', 'continue-on-error', 'gh release', 'contents: write'):
            self.assertNotIn(forbidden, workflow)
        names = ('Reject changes to image payload', 'Install source-test PDF parser',
                 'Test source and recipe', 'Download pinned image artifact',
                 'Check pinned ISO and checksum', name)
        positions = [workflow.index('name: ' + name + '\n') for name in names]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('networking diagnostic only', workflow.lower())
        self.assertIn('not full image acceptance', workflow.lower())

    def test_runner_parser_source_tests_and_small_logs_always(self):
        deps = self.run_block('Install source-test PDF parser')
        self.assertIn('sudo apt-get update', deps)
        self.assertIn('python3-pypdf2', deps)
        self.assertIn("/usr/bin/python3 -c 'import PyPDF2", deps)
        tests = self.run_block('Test source and recipe')
        self.assertIn('/usr/bin/python3 -m unittest discover -s tests -v', tests)
        self.assertIn('set -euo pipefail', tests)
        self.assertIn('tee logs/source-tests.log', tests)
        workflow = self.workflow()
        self.assertEqual(workflow.count('uses: actions/upload-artifact@v4'), 1)
        upload = self.step('Upload networking diagnostic evidence even on failure')
        for token in ('if: always()', 'path: logs/', 'retention-days: 14'):
            self.assertIn(token, upload)
        self.assertNotIn('dist/', upload)
        self.assertIn('if: always()', self.step('Record final disk use'))

    def test_provenance_keeps_failed_image_and_current_harness_distinct(self):
        block = self.run_block('Prepare output and record provenance')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True, timeout=5)
            subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=test@example.invalid',
                            'commit', '--allow-empty', '-qm', 'harness fixture'],
                           cwd=root, check=True, timeout=5)
            harness = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True, timeout=5).strip()
            env = dict(os.environ, IMAGE_SOURCE_COMMIT=IMAGE_SOURCE, IMAGE_RUN_ID=IMAGE_RUN,
                       IMAGE_ISO_SHA256=IMAGE_SHA, IMAGE_ARTIFACT='gravestone-0.4.2-amd64',
                       GITHUB_SERVER_URL='https://github.com', GITHUB_REPOSITORY='fixture/repo',
                       GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='2')
            result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', block], cwd=root,
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((root / 'logs/verification-provenance.json').read_text())
            self.assertEqual(data['image_source_commit'], IMAGE_SOURCE)
            self.assertEqual(data['image_run_id'], IMAGE_RUN)
            self.assertEqual(data['image_sha256'], IMAGE_SHA)
            self.assertEqual(data['verification_harness_commit'], harness)
            self.assertFalse(data['image_rebuilt'])
            self.assertEqual(data['scope'], 'networking diagnostic only; not full image acceptance')


# Do not collect the imported fixture TestCase a second time.
del GuardFixtures

if __name__ == '__main__':
    unittest.main()
