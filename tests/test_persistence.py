"""Safety gates for disposable VM persistence acceptance (no physical disks)."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/test-persistence.py'


class PersistenceSafety(unittest.TestCase):
    def test_expected_iso_pin_is_explicit_and_validated(self):
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('persistence', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(hasattr(module, 'expected_iso_digest'), 'validated release pin missing')
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(module.expected_iso_digest(),
                             '63be2439540ce02b5821791ea93e4cda5669f2b8adcd7a7d3d96fe921accc001')
        with patch.dict('os.environ', {'GRAVESTONE_TEST_ISO_SHA256': 'a' * 64}):
            self.assertEqual(module.expected_iso_digest(), 'a' * 64)
        for invalid in ('', 'ABC', '../disk', 'a' * 63, 'a' * 64 + '\n'):
            with patch.dict('os.environ', {'GRAVESTONE_TEST_ISO_SHA256': invalid}):
                with self.assertRaises(ValueError):
                    module.expected_iso_digest()

    def test_build_runs_offline_bounded_reboot_acceptance(self):
        workflow = (SCRIPT.parents[1] / '.github/workflows/build-live.yml').read_text()
        self.assertIn('Verify notebook across two clean reboots', workflow)
        step = workflow.split('Verify notebook across two clean reboots', 1)[1].split('      - name:', 1)[0]
        for text in ('--memory 2500m', '--cpus 1', '--shm-size 256m',
                     'docker network disconnect bridge', 'GRAVESTONE_TEST_ISO_SHA256',
                     'scripts/test-persistence.py', 'docker cp', 'docker rm -f'):
            self.assertIn(text, step)
        self.assertNotIn('--privileged', step)
        self.assertNotIn('--device ', step)
        self.assertNotIn('source=/dev/', step)

    def test_only_fresh_regular_scratch_file_can_be_created(self):
        self.assertTrue(SCRIPT.exists(), 'persistence harness is missing')
        spec = importlib.util.spec_from_file_location('persistence', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            disk = module.create_scratch(root)
            self.assertTrue(disk.is_file())
            self.assertEqual(disk.stat().st_size, 256 * 1024 * 1024)
            with self.assertRaises(FileExistsError):
                module.create_scratch(root)
            with self.assertRaises(ValueError):
                module.create_scratch(Path('/dev'))
            link = root / 'link'
            link.symlink_to('/dev')
            with self.assertRaises(ValueError):
                module.create_scratch(link)

    def test_three_pass_protocol_is_exact_and_uses_real_api(self):
        spec = importlib.util.spec_from_file_location('persistence', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(hasattr(module, 'guest_program'), 'guest protocol missing')
        for phase in (1, 2, 3):
            source = module.guest_program(phase, 'unique-token')
            compile(source, '<guest>', 'exec')
            self.assertIn('/api/notes', source)
            self.assertIn('/proc/sys/kernel/random/boot_id', source)
            self.assertIn('assert before == expected', source)
        self.assertTrue(hasattr(module, 'run'), 'acceptance runner missing')

    def test_vm_has_only_readonly_iso_and_removable_scratch_no_nic(self):
        spec = importlib.util.spec_from_file_location('persistence', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(hasattr(module, 'vm_command'), 'VM safety command builder missing')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            iso = root / 'release.iso'
            iso.write_bytes(b'test ISO')
            disk = module.create_scratch(root)
            cmd = module.vm_command(iso, disk, root)
            self.assertEqual(cmd[cmd.index('-nic') + 1], 'none')
            self.assertEqual(cmd[cmd.index('-smp') + 1], '1')
            self.assertIn('readonly=on', ' '.join(cmd))
            self.assertIn('removable=true', ' '.join(cmd))
            self.assertNotIn('mount', cmd)
            with self.assertRaises(ValueError):
                module.vm_command(Path('/dev/null'), disk, root)
            link = root / 'alias.iso'
            link.symlink_to(iso)
            with self.assertRaises(ValueError):
                module.vm_command(link, disk, root)


if __name__ == '__main__':
    unittest.main()
