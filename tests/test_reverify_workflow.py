"""Contract tests for rechecking immutable 0.4.2 bytes, never rebuilding them."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/verify-0.4.2.yml'
IMAGE_SOURCE = 'a3ff211f9670a1cff0f966e103e834460519424f'
IMAGE_RUN = '41258126216'
IMAGE_SHA = '707d0a271af4f0a418c0ef2016459b0b2cae33e15850cba6d46d5a91e36ab34b'


class ReverifyWorkflowTests(unittest.TestCase):
    def workflow(self):
        self.assertTrue(WORKFLOW.is_file(), 'missing one-off immutable-ISO verification workflow')
        return WORKFLOW.read_text()

    def step(self, name, workflow=None):
        workflow = self.workflow() if workflow is None else workflow
        marker = '      - name: ' + name + '\n'
        self.assertIn(marker, workflow)
        return workflow.split(marker, 1)[1].split('      - ', 1)[0]

    def run_block(self, name):
        step = self.step(name)
        match = re.search(r'        run: \|\n((?:          .*\n|\n)+)', step)
        self.assertIsNotNone(match, 'expected literal multiline run block')
        assert match is not None
        return textwrap.dedent(match.group(1))

    def test_source_guard_rejects_every_image_payload_change_but_allows_harness_changes(self):
        guard = self.run_block('Reject changes to image payload')
        self.assertIn('git diff --quiet "$IMAGE_SOURCE_COMMIT" HEAD -- app/ ai/ content/ live/', guard)
        self.assertLess(self.workflow().index('name: Reject changes to image payload'),
                        self.workflow().index('name: Download pinned image artifact'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.STDOUT,
                                               text=True).strip()
            git('init', '-q')
            git('config', 'user.email', 'fixture@example.invalid')
            git('config', 'user.name', 'Workflow test fixture')
            for folder in ('app', 'ai', 'content', 'live', 'scripts'):
                (root / folder).mkdir()
                (root / folder / 'fixture').write_text('original\n')
            git('add', '.')
            git('commit', '-qm', 'image fixture')
            pin = git('rev-parse', 'HEAD')
            env = dict(os.environ, IMAGE_SOURCE_COMMIT=pin)
            def check():
                return subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', guard],
                                      cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(check().returncode, 0)
            (root / 'scripts/fixture').write_text('new harness\n')
            git('commit', '-qam', 'harness only')
            self.assertEqual(check().returncode, 0, 'harness-only fixes must not require a rebuild')
            harness = git('rev-parse', 'HEAD')
            for folder in ('app', 'ai', 'content', 'live'):
                with self.subTest(folder=folder):
                    (root / folder / 'fixture').write_text('changed payload\n')
                    git('commit', '-qam', 'payload drift')
                    self.assertNotEqual(check().returncode, 0)
                    git('reset', '--hard', harness)
            env['IMAGE_SOURCE_COMMIT'] = '0' * 40
            self.assertNotEqual(check().returncode, 0, 'missing image commit must fail closed')

    def test_download_exact_run_and_fail_closed_on_iso_or_checksum_drift(self):
        download = self.step('Download pinned image artifact')
        for token in ('GH_TOKEN: ${{ github.token }}', 'gh run download "$IMAGE_RUN_ID"',
                      '--repo "$GITHUB_REPOSITORY"', '--name "$IMAGE_ARTIFACT" --dir dist'):
            self.assertIn(token, download)
        self.assertNotIn('set -x', download)
        block = self.run_block('Check pinned ISO and checksum')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'dist').mkdir()
            (root / 'logs').mkdir()
            iso = root / 'dist/gravestone-0.4.2-amd64.iso'
            checksum = iso.with_suffix('.iso.sha256')
            original = b'non-bootable checksum unit-test fixture\n'
            pin = hashlib.sha256(original).hexdigest()
            env = dict(os.environ, IMAGE_ISO_SHA256=pin)
            good_checksum = f'{pin}  {iso.name}\n'
            cases = (
                ('valid', original, good_checksum, True),
                ('changed ISO', b'drift', good_checksum, False),
                ('changed ISO and matching sidecar', b'drift',
                 f'{hashlib.sha256(b"drift").hexdigest()}  {iso.name}\n', False),
                ('missing ISO', None, good_checksum, False),
                ('missing sidecar', original, None, False),
                ('extra checksum entry', original, good_checksum + good_checksum, False),
                ('wrong filename', original, f'{pin}  other.iso\n', False),
            )
            for name, content, sidecar, expected in cases:
                with self.subTest(case=name):
                    iso.unlink(missing_ok=True)
                    checksum.unlink(missing_ok=True)
                    if content is not None:
                        iso.write_bytes(content)
                    if sidecar is not None:
                        checksum.write_text(sidecar)
                    result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', block],
                                            cwd=root, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode == 0, expected, result.stderr)
                    if expected:
                        self.assertEqual((root / 'logs' / checksum.name).read_text(), good_checksum)

    def test_provenance_records_separate_image_and_harness_commits(self):
        block = self.run_block('Prepare output and record provenance')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=test@example.invalid',
                            'commit', '--allow-empty', '-qm', 'harness fixture'], cwd=root, check=True)
            harness = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
            env = dict(os.environ, IMAGE_SOURCE_COMMIT=IMAGE_SOURCE, IMAGE_RUN_ID=IMAGE_RUN,
                       IMAGE_ISO_SHA256=IMAGE_SHA, IMAGE_ARTIFACT='gravestone-0.4.2-amd64',
                       GITHUB_SERVER_URL='https://github.com', GITHUB_REPOSITORY='fixture/repo',
                       GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='2')
            result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', block],
                                    cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((root / 'logs/verification-provenance.json').read_text())
            self.assertEqual(data['image_source_commit'], IMAGE_SOURCE)
            self.assertEqual(data['verification_harness_commit'], harness)
            self.assertEqual(data['image_run_id'], IMAGE_RUN)
            self.assertEqual(data['image_sha256'], IMAGE_SHA)
            self.assertEqual(data['image_artifact'], 'gravestone-0.4.2-amd64')
            self.assertEqual(data['image_run_url'], f'https://github.com/fixture/repo/actions/runs/{IMAGE_RUN}')
            self.assertEqual(data['verification_run_url'], 'https://github.com/fixture/repo/actions/runs/123')
            self.assertEqual(data['verification_run_attempt'], '2')
            self.assertFalse(data['image_rebuilt'])

    def test_all_existing_boot_and_persistence_gates_are_reused_unchanged(self):
        workflow = self.workflow()
        original = (ROOT / '.github/workflows/build-live.yml').read_text()
        gate_names = (
            'Boot extracted kernel and whole BIOS and UEFI ISO',
            'Verify notebook across two clean reboots',
            'Verify extracted UEFI and same-USB root persistence',
        )
        for name in gate_names:
            with self.subTest(gate=name):
                self.assertEqual(self.step(name).rstrip(), self.step(name, original).rstrip(),
                                 'reuse the reviewed gate including limits and cleanup verbatim')
        test_step = self.step('Test source and recipe')
        self.assertIn('python3 -m unittest discover -s tests -v', test_step)
        deps = self.step('Install VM test dependencies')
        self.assertIn('sudo apt-get update', deps)
        self.assertIn('qemu-system-x86 ovmf xorriso', deps)
        self.assertNotIn('continue-on-error', workflow)
        names = ('Reject changes to image payload', 'Test source and recipe',
                 'Download pinned image artifact', 'Check pinned ISO and checksum',
                 'Install VM test dependencies', *gate_names)
        positions = [workflow.index('name: ' + name + '\n') for name in names]
        self.assertEqual(positions, sorted(positions))

    def test_only_small_logs_and_provenance_are_uploaded_even_on_failure(self):
        workflow = self.workflow()
        self.assertEqual(workflow.count('uses: actions/upload-artifact@v4'), 1)
        upload = self.step('Upload verification evidence even on failure')
        for token in ('if: always()', 'path: logs/', 'retention-days: 14',
                      'name: gravestone-0.4.2-verification-logs'):
            self.assertIn(token, upload)
        self.assertNotIn('dist/', upload)
        self.assertIn('if: always()', self.step('Record final disk use'))

    def test_every_run_block_has_valid_bash_syntax(self):
        workflow = self.workflow()
        blocks = re.findall(r'^        run: \|\n((?:          .*\n|\n)+)', workflow, re.MULTILINE)
        self.assertTrue(blocks)
        self.assertEqual(len(blocks), len(re.findall(r'^        run:', workflow, re.MULTILINE)),
                         'every run block must receive a syntax check')
        for index, block in enumerate(blocks):
            with self.subTest(block=index):
                result = subprocess.run(['bash', '-n'], input=textwrap.dedent(block),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_manual_read_only_workflow_pins_image_not_harness(self):
        workflow = self.workflow()
        self.assertRegex(workflow, r'(?m)^on:\n  workflow_dispatch:\s*\npermissions:')
        self.assertNotIn('inputs:', workflow)
        self.assertRegex(workflow, r'permissions:\n  contents: read\n  actions: read\n')
        for key, value in (('IMAGE_SOURCE_COMMIT', IMAGE_SOURCE), ('IMAGE_RUN_ID', IMAGE_RUN),
                           ('IMAGE_ISO_SHA256', IMAGE_SHA),
                           ('IMAGE_ARTIFACT', 'gravestone-0.4.2-amd64')):
            self.assertRegex(workflow, rf'(?m)^  {key}: [\'\"]?{re.escape(value)}[\'\"]?$')
        self.assertIn('uses: actions/checkout@v4', workflow)
        self.assertIn('fetch-depth: 0', workflow)
        self.assertNotIn('ref:', workflow, 'checkout the dispatched harness, not old image source')
        self.assertIn('runs-on: ubuntu-24.04', workflow)
        self.assertIn('timeout-minutes: 90', workflow)
        for forbidden in ('prepare-ai.sh', 'prepare-live.sh', 'scripts/build-live.sh',
                          'lb build', '--privileged', 'gh release', 'contents: write'):
            self.assertNotIn(forbidden, workflow)


if __name__ == '__main__':
    unittest.main()
