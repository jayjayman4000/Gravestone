"""EFI bootstrap regression contracts; firmware behavior is test-efi-fat.py."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EfiBootstrapTests(unittest.TestCase):
    def test_builder_checks_patched_helper_before_expensive_ai(self):
        build = (ROOT / 'scripts/build-live.sh').read_text()
        patch = build.index('python3 "$repo/scripts/patch-live-build-efi.py"') if 'patch-live-build-efi.py' in build else -1
        gate = build.index('python3 "$repo/scripts/test-efi-fat.py"') if 'test-efi-fat.py' in build else -1
        self.assertGreaterEqual(patch, 0, 'builder must patch the exact reviewed EFI helper')
        self.assertGreater(gate, patch, 'firmware gate must test the patched helper')
        self.assertLess(gate, build.index('"$repo/scripts/prepare-ai.sh"'))
        workflow = (ROOT / '.github/workflows/build-live.yml').read_text()
        dependencies = workflow.split('/src/scripts/build-live.sh')[0]
        for package in ('qemu-system-x86', 'ovmf', 'fdisk'):
            self.assertIn(package, dependencies)

    def test_built_iso_loader_has_its_own_firmware_gate(self):
        build = (ROOT / 'scripts/build-live.sh').read_text()
        self.assertIn('--iso "$out/$name"', build)
        self.assertLess(build.index('lb build'), build.index('--iso "$out/$name"'))

    def test_timeout_or_failed_exit_is_not_boot_success(self):
        spec = importlib.util.spec_from_file_location('efi_gate', ROOT / 'scripts/test-efi-fat.py')
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        verdict = getattr(module, 'successful_boot', None)
        self.assertTrue(callable(verdict), 'firmware gate needs an explicit fail-closed verdict')
        assert callable(verdict)
        marker = b'GRAVESTONE_EFI_FAT_OK root=hd0,gpt1 platform=efi'
        self.assertTrue(verdict(marker, 0, False))
        self.assertFalse(verdict(marker, None, True))
        self.assertFalse(verdict(marker, 1, False))
        self.assertFalse(verdict(marker + b'error: no such device', 0, False))
        self.assertFalse(verdict(b'', 0, False))

    def test_gate_audits_embedded_partition_modules_and_runtime_variables(self):
        gate = (ROOT / 'scripts/test-efi-fat.py').read_text()
        self.assertIn("embedded_modules=", gate)
        self.assertIn("'.modname'", gate)
        self.assertIn("'part_gpt', 'part_msdos'", gate)
        self.assertIn("'$grub_platform'", gate)
        self.assertIn("'$lockdown'", gate)

    def test_unreviewed_helper_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as temporary:
            helper = Path(temporary) / 'efi-image'
            original = b'#!/bin/sh\necho unreviewed\n'
            helper.write_bytes(original)
            result = subprocess.run(['python3', str(ROOT / 'scripts/patch-live-build-efi.py'), str(helper)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Unreviewed', result.stderr)
            self.assertEqual(helper.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
