"""Contracts for the constructed Rufus-like fixture, never a physical writer."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/test-rufus-persistence.py'


def load():
    if not SCRIPT.is_file():
        raise AssertionError('same-USB persistence harness is missing')
    spec = importlib.util.spec_from_file_location('rufus_persistence', SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Safety(unittest.TestCase):
    def test_explicit_pin_and_fresh_canonical_regular_storage(self):
        h = load()
        for value in (None, '', 'A' * 64, 'a' * 63, 'a' * 64 + '\n', '../disk'):
            with patch.dict(os.environ, {}, clear=True):
                if value is not None:
                    os.environ['GRAVESTONE_TEST_ISO_SHA256'] = value
                with self.assertRaises(ValueError):
                    h.expected_iso_digest()
        with patch.dict(os.environ, {'GRAVESTONE_TEST_ISO_SHA256': 'a' * 64}):
            self.assertEqual(h.expected_iso_digest(), 'a' * 64)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'usb.raw'
            h.fresh_file(target, 4 * 1024**3)
            self.assertEqual(target.stat().st_size, 4 * 1024**3)
            self.assertLess(target.stat().st_blocks * 512, 1024**2)
            with self.assertRaises(FileExistsError):
                h.fresh_file(target, 1)
            alias = root / 'alias'
            alias.symlink_to(root, target_is_directory=True)
            for path in (alias / 'new', Path('/dev/new'), root / '../bad'):
                with self.assertRaises(ValueError):
                    h.fresh_file(path, 1)
            link = root / 'link'
            link.symlink_to(target)
            for path in (link, Path('/dev/null')):
                with self.assertRaises(ValueError):
                    h.regular(path)
            hardlink = root / 'hardlink'
            os.link(target, hardlink)
            with self.assertRaises(ValueError):
                h.regular(target)


class ExtractedPermissions(unittest.TestCase):
    def exercise_read_only_tree(self, h, tree, root, fail=False):
        import hashlib
        import stat
        files = [path for path in tree.rglob('*') if path.is_file()]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        modes = {path: stat.S_IMODE(path.stat().st_mode) for path in files}
        menu = tree / 'boot/grub/grub.cfg'
        try:
            with h.writable_iso_tree(tree, root):
                self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in files}, before)
                record = h.instrument_menu(tree)  # Real write, including under cap-drop ALL.
                self.assertEqual(record['before_sha256'], before[menu])
                self.assertNotEqual(record['after_sha256'], before[menu])
                for path in files:
                    if path != menu:
                        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before[path])
                        self.assertEqual(stat.S_IMODE(path.stat().st_mode), modes[path])
                self.assertEqual(stat.S_IMODE(menu.stat().st_mode), modes[menu] | 0o200)
                for path in [tree] + [p for p in tree.rglob('*') if p.is_dir()]:
                    self.assertEqual(path.stat().st_mode & 0o300, 0o300)
                if fail:
                    raise RuntimeError('injected staging failure')
        except RuntimeError as error:
            if not fail or str(error) != 'injected staging failure':
                raise
        self.assertFalse(tree.exists(), 'validated scratch must be removed on success or failure')
        self.assertTrue(root.is_dir(), 'keep the evidence root')
        return len(before)

    def test_read_only_tree_instrumentation_preserves_other_bytes_and_cleans_up(self):
        h = load()
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                tree = root / 'tree'
                (tree / 'boot/grub/x86_64-efi').mkdir(parents=True)
                (tree / 'EFI/boot').mkdir(parents=True)
                menu = tree / 'boot/grub/grub.cfg'
                menu.write_text('linux /live/vmlinuz ' + ' '.join(sorted(h.REQUIRED_ARGS)) + '\n')
                (tree / 'EFI/boot/bootx64.efi').write_bytes(b'fixture loader, not bootable\x00')
                (tree / 'boot/grub/x86_64-efi/grub.cfg').write_bytes(b'platform bytes\n')
                for path in tree.rglob('*'):
                    path.chmod(0o555 if path.is_dir() else 0o444)
                tree.chmod(0o555)
                try:
                    self.exercise_read_only_tree(h, tree, root, fail)
                finally:
                    # RED-path teardown for this known, link-free test fixture.
                    if tree.exists():
                        for base, _, _ in os.walk(tree):
                            Path(base).chmod(0o755)

    @unittest.skipUnless(os.environ.get('GRAVESTONE_RUFUS_PERMISSION_TEST') == '1',
                         'opt-in real read-only ISO /boot/grub extraction in restricted container')
    def test_real_xorriso_read_only_grub_subtree(self):
        import hashlib
        import stat
        import subprocess
        h = load()
        status = Path('/proc/self/status').read_text()
        self.assertRegex(status, r'CapEff:\s+0+\n')
        self.assertRegex(status, r'CapBnd:\s+0+\n')
        self.assertRegex(status, r'NoNewPrivs:\s+1\n')
        h.validate_limits(Path('/sys/fs/cgroup/memory.max').read_text().strip(),
                          Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
                          [path.name for path in Path('/sys/class/net').iterdir()])
        iso = Path('/input/release.iso')
        def iso_digest():
            with iso.open('rb') as stream:
                return hashlib.file_digest(stream, 'sha256').hexdigest()
        before = iso_digest()
        self.assertEqual(before, '9c72b79cba370beae1f4bee9f74660467407c06e17df0b99f3a42323d5fbcf89')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tree = root / 'tree'
            (tree / 'boot').mkdir(parents=True)
            subprocess.run(['xorriso', '-osirrox', 'on', '-indev', str(iso), '-extract',
                            '/boot/grub', str(tree / 'boot/grub')],
                           check=True, capture_output=True, timeout=120)
            menu = tree / 'boot/grub/grub.cfg'
            self.assertEqual(stat.S_IMODE(menu.stat().st_mode), 0o444)
            self.assertEqual(stat.S_IMODE(menu.parent.stat().st_mode), 0o555)
            try:
                count = self.exercise_read_only_tree(h, tree, root)
                print(f'Actual ISO: {count} extracted file hashes checked; '
                      'only menu bytes changed; scratch removed', flush=True)
            finally:
                if tree.exists():
                    for base, _, _ in os.walk(tree):
                        Path(base).chmod(0o755)
        self.assertEqual(iso_digest(), before)
        print('Actual read-only ISO SHA-256 unchanged: ' + before, flush=True)

    def test_rejects_nonprivate_or_escaped_extraction_roots(self):
        h = load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scratch = root / 'scratch'
            scratch.mkdir(mode=0o700)
            tree = scratch / 'tree'
            grub = tree / 'boot/grub'
            grub.mkdir(parents=True)
            menu = grub / 'grub.cfg'
            menu.write_bytes(b'unchanged menu\n')
            menu.chmod(0o444)
            alias = root / 'alias'
            alias.symlink_to(scratch, target_is_directory=True)
            tree_alias = scratch / 'alias'
            tree_alias.symlink_to(tree, target_is_directory=True)
            for candidate, owner in ((tree, root), (scratch, scratch),
                                     (tree_alias, scratch), (alias / 'tree', alias),
                                     (tree / '..' / 'tree', scratch)):
                with self.subTest(candidate=candidate, owner=owner), self.assertRaises(ValueError):
                    with h.writable_iso_tree(candidate, owner):
                        self.fail('unconfined tree must not be yielded')
            scratch.chmod(0o755)
            with self.assertRaises(ValueError):
                with h.writable_iso_tree(tree, scratch):
                    self.fail('shared scratch must not be yielded')
            self.assertEqual(menu.read_bytes(), b'unchanged menu\n')
            self.assertEqual(menu.stat().st_mode & 0o777, 0o444)

    def test_rejects_unsafe_members_before_any_permission_change(self):
        import stat
        h = load()
        self.assertTrue(callable(getattr(h, 'writable_iso_tree', None)),
                        'validation-first extracted-tree permission helper is missing')
        for kind in ('file-link', 'directory-link', 'dangling-link', 'menu-link',
                     'hardlink', 'fifo', 'special-file-mode', 'special-directory-mode',
                     'noncanonical-name'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                tree = root / 'tree'
                grub = tree / 'boot/grub'
                grub.mkdir(parents=True)
                menu = grub / 'grub.cfg'
                menu.write_bytes(b'unchanged menu\n')
                outside = root / 'outside'
                outside.mkdir()
                victim = outside / 'victim'
                victim.write_bytes(b'outside bytes\n')
                victim.chmod(0o444)
                bad = grub / 'zz-unsafe'
                if kind == 'file-link':
                    bad.symlink_to(victim)
                elif kind == 'directory-link':
                    bad.symlink_to(outside, target_is_directory=True)
                elif kind == 'dangling-link':
                    bad.symlink_to(outside / 'missing')
                elif kind == 'menu-link':
                    menu.unlink()
                    menu.symlink_to(victim)
                elif kind == 'hardlink':
                    os.link(victim, bad)
                elif kind == 'special-file-mode':
                    bad.write_bytes(b'unsafe mode')
                    bad.chmod(0o444 | stat.S_ISUID)
                elif kind == 'special-directory-mode':
                    bad.mkdir()
                    bad.chmod(0o755 | stat.S_ISGID)
                elif kind == 'noncanonical-name':
                    (grub / 'bad,name').write_bytes(b'unsafe path')
                else:
                    os.mkfifo(bad)
                if not menu.is_symlink():
                    menu.chmod(0o444)
                directories = [tree, tree / 'boot', grub]
                for path in directories:
                    path.chmod(0o555)
                before = {path: path.lstat().st_mode for path in
                          directories + [menu, victim, outside]}
                try:
                    with self.assertRaises(ValueError):
                        with h.writable_iso_tree(tree, root):
                            self.fail('unsafe tree must not be yielded')
                    self.assertEqual({path: path.lstat().st_mode for path in before}, before)
                    self.assertEqual(victim.read_bytes(), b'outside bytes\n')
                    self.assertEqual(stat.S_IMODE(victim.stat().st_mode), 0o444)
                finally:
                    # Test-owned known directories only, even on the RED path.
                    for path in directories:
                        path.chmod(0o755)


class Fixture(unittest.TestCase):
    def test_same_usb_layout_and_only_menu_instrumentation(self):
        h = load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tree = root / 'tree'
            (tree / 'boot/grub/x86_64-efi').mkdir(parents=True)
            (tree / 'EFI/boot').mkdir(parents=True)
            (tree / '.disk').mkdir()
            (tree / '.disk/info').write_bytes(b'fixture marker\n')
            loader = tree / 'EFI/boot/bootx64.efi'
            loader.write_bytes(b'fixture loader, not bootable')
            platform = tree / 'boot/grub/x86_64-efi/grub.cfg'
            platform.write_text('if [ "$grub_platform" = efi ]; then true; fi\n')
            menu = tree / 'boot/grub/grub.cfg'
            original = ('set timeout=3\nmenuentry "live" {\n'
                        ' linux /live/vmlinuz boot=live persistence live-media=removable '
                        'persistence-media=removable-usb persistence-storage=filesystem\n'
                        ' initrd /live/initrd.img\n}\n')
            failsafe = ('menuentry "fail-safe" {\n linux /live/vmlinuz boot=live components noapic\n'
                        ' initrd /live/initrd.img\n}\n')
            menu.write_text(original + failsafe)
            h.instrument_menu(tree)
            self.assertTrue(menu.read_text().endswith(failsafe))
            self.assertEqual(loader.read_bytes(), b'fixture loader, not bootable')
            self.assertEqual(platform.read_text(), 'if [ "$grub_platform" = efi ]; then true; fi\n')
            self.assertIn('systemd.debug_shell=ttyS0', menu.read_text())
            layout = h.layout(80 * 1024**2)
            self.assertEqual(layout['persistence_bytes'], 4 * 1024**3)
            self.assertEqual(layout['fat_start'], 2048 * 512)
            self.assertEqual(layout['persistence_start'], layout['fat_start'] + layout['fat_bytes'])
            self.assertIn('label: gpt', h.partition_table(layout))
            self.assertIn('type=U', h.partition_table(layout))
            self.assertIn('type=L', h.partition_table(layout))
            disk = h.fresh_file(root / 'usb.raw', layout['disk_bytes'])
            code = h.fresh_file(root / 'code.fd')
            variables = h.fresh_file(root / 'vars.fd')
            cmd = h.vm_command(disk, code, variables, root)
            self.assertEqual(cmd.count('-drive'), 3)  # firmware pair + ONE USB
            self.assertEqual(cmd[cmd.index('-nic') + 1], 'none')
            self.assertEqual(cmd[cmd.index('-m') + 1], '2048')
            self.assertEqual(cmd[cmd.index('-smp') + 1], '1')
            self.assertIn('usb-storage,drive=stick,removable=on', cmd)
            self.assertIn('-nodefaults', cmd)  # no implicit floppy/CD drive
            for forbidden in ('-kernel', '-initrd', '-append', '-cdrom', '-hda'):
                self.assertNotIn(forbidden, cmd)
            self.assertNotIn('media=cdrom', ' '.join(cmd))
            menu.write_text(original.replace('persistence-media=removable-usb', ''))
            with self.assertRaises(ValueError):
                h.instrument_menu(tree)

    @unittest.skipUnless(os.environ.get('GRAVESTONE_RUFUS_FIXTURE_TEST') == '1',
                         'opt-in real mtools/ext4/GPT fixture requires container tools')
    def test_real_small_fat_plus_exact_sparse_4gib_ext4(self):
        import json
        import subprocess
        h = load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tree = root / 'tree'
            tree.mkdir()
            (tree / '.disk').mkdir()
            (tree / '.disk/info').write_bytes(b'fixture marker\n')
            (tree / 'payload').write_bytes(b'UTF-8: \xe9\x9b\xaa\n')
            disk, info = h.create_usb(tree, root)
            table = json.loads(subprocess.check_output(['sfdisk', '--json', str(disk)]))['partitiontable']
            self.assertEqual(len(table['partitions']), 2)
            self.assertEqual(table['label'], 'gpt')
            self.assertEqual(table['partitions'][1]['size'] * 512, 4 * 1024**3)
            marker = subprocess.check_output(['mtype', '-i', f'{disk}@@{info["fat_start"]}', '::.disk/info'])
            self.assertEqual(marker, b'fixture marker\n')
            h.check_ext4(disk, info, root, 0)
            self.assertIn('Pass 5: Checking group summary information',
                          (root / 'boot-0-fsck.log').read_text())
            self.assertLess(disk.stat().st_blocks * 512, 250 * 1024**2)
            self.assertFalse((root / 'persistence.part').exists())


class Protocol(unittest.TestCase):
    def test_exact_utf8_api_three_phases_against_real_application(self):
        import sys
        import threading
        sys.path.insert(0, str(SCRIPT.parents[1]))
        from app import DashboardServer
        h = load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = DashboardServer(('127.0.0.1', 0), SCRIPT.parents[1] / 'content', root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                records = [h.api_probe(phase, 'test-token', base) for phase in (1, 2, 3)]
                self.assertEqual(records[0]['before'], '')
                self.assertIn('雪', records[2]['after'])
                self.assertEqual(records[0]['after'], records[1]['before'])
                self.assertEqual(records[1]['after'], records[2]['before'])
                with self.assertRaises(AssertionError):
                    h.api_probe(1, 'different-token', base)
            finally:
                server.shutdown()
                thread.join(5)
                server.server_close()
        for phase in (1, 2, 3):
            source = h.guest_program(phase, 'test-token')
            compile(source, '<guest>', 'exec')
            self.assertIn('/api/status', source)
            self.assertIn('/proc/sys/kernel/random/boot_id', source)
        with self.assertRaises(ValueError):
            h.guest_program(4, 'token')

    def test_wrong_medium_or_home_only_union_fails_closed(self):
        import copy
        h = load()
        mounts = ('1 0 0:1 / / rw - overlay overlay rw,lowerdir=/rootfs,upperdir=/run/live/overlay/rw,workdir=/run/live/overlay/work\n'
                  '2 1 8:1 / /run/live/medium ro - vfat /dev/sda1 ro\n'
                  '3 1 8:2 / /run/live/persistence/sda2 rw - ext4 /dev/sda2 rw\n')
        record = {'mountinfo': mounts, 'upper_backing': '/dev/sda2[/rw] ext4',
                  'persistence_conf': '/ union\n',
                  'lsblk': {'blockdevices': [{'name': 'sda', 'type': 'disk', 'tran': 'usb', 'rm': True,
                           'children': [{'name': 'sda1', 'type': 'part', 'fstype': 'vfat'},
                                        {'name': 'sda2', 'type': 'part', 'fstype': 'ext4', 'label': 'persistence'}]}]}}
        h.validate_mounts(record)
        changes = [dict(persistence_conf='/home union\n'),
                   dict(upper_backing='tmpfs tmpfs'),
                   dict(mountinfo=mounts.replace('/dev/sda1', '/dev/sdb1')),
                   dict(mountinfo=mounts.replace(' - overlay overlay ', ' - tmpfs tmpfs '))]
        for change in changes:
            broken = copy.deepcopy(record)
            broken.update(change)
            with self.assertRaises((ValueError, AssertionError)):
                h.validate_mounts(broken)
        broken = copy.deepcopy(record)
        broken['lsblk']['blockdevices'][0]['rm'] = False
        with self.assertRaises((ValueError, AssertionError)):
            h.validate_mounts(broken)


class Lifecycle(unittest.TestCase):
    def test_network_and_container_resource_limits_fail_closed(self):
        h = load()
        h.validate_limits('2621440000', '100000 100000', ['lo'])
        for memory, cpu, interfaces in [('max', '100000 100000', ['lo']),
                                         ('3000000000', '100000 100000', ['lo']),
                                         ('2621440000', 'max 100000', ['lo']),
                                         ('2621440000', '200000 100000', ['lo']),
                                         ('2621440000', '100000 100000', ['lo', 'eth0'])]:
            with self.assertRaises(ValueError):
                h.validate_limits(memory, cpu, interfaces)

    def test_checkpoint_is_atomic_durable_and_refuses_links(self):
        import json
        h = load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            h.checkpoint(root, {'passed': False, 'boots': []})
            h.checkpoint(root, {'passed': False, 'error': 'interrupted'})
            self.assertEqual(json.loads((root / 'result.json').read_text())['error'], 'interrupted')
            self.assertFalse((root / 'result.tmp').exists())
            (root / 'result.json').unlink()
            victim = root / 'victim'
            victim.write_text('untouched')
            (root / 'result.json').symlink_to(victim)
            with self.assertRaises(ValueError):
                h.checkpoint(root, {'passed': True})
            self.assertEqual(victim.read_text(), 'untouched')

    def test_partial_boot_timeout_reaps_only_its_process_and_keeps_logs(self):
        import subprocess
        import sys
        h = load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spawned = []
            real_popen = subprocess.Popen
            def start(*args, **kwargs):
                proc = real_popen(*args, **kwargs)
                spawned.append(proc)
                return proc
            with patch.object(h.subprocess, 'Popen', side_effect=start):
                with self.assertRaises(TimeoutError):
                    h.boot_once([sys.executable, '-c', 'import time; time.sleep(30)'],
                                root, 1, 'token', timeout=.1)
            self.assertEqual(len(spawned), 1)
            self.assertIsNotNone(spawned[0].poll())
            self.assertTrue((root / 'boot-1-serial.log').is_file())
            self.assertTrue((root / 'boot-1-command.json').is_file())

    def test_clean_exit_marker_phase_and_unique_boot_ids_are_mandatory(self):
        h = load()
        import json
        api = {'phase': 1, 'before': '', 'after': 'token: boot one\nUTF-8: 雪\n<literal & text>\n',
               'boot_id': '11111111-1111-4111-8111-111111111111', 'cmdline': ' '.join(h.REQUIRED_ARGS)}
        # Mount validation is separately exercised with realistic mountinfo above.
        with patch.object(h, 'validate_mounts'):
            text = 'RUFUS_PERSISTENCE_RESULT=' + json.dumps(api) + '\r\nreboot: Power down\r\n'
            record = h.validate_boot(text, 0, 1, 'token', [])
            self.assertTrue(record['clean_poweroff'])
            # A debug shell prompt may precede un-echoed Python stdout.
            self.assertTrue(h.validate_boot('root@live:~# ' + text, 0, 1, 'token', [])['clean_poweroff'])
            for bad_text, code, ids in ((text, 1, []), (text.replace('Power down', 'halt'), 0, []),
                                        (text, 0, [api['boot_id']]), ('', 0, [])):
                with self.assertRaises((ValueError, AssertionError)):
                    h.validate_boot(bad_text, code, 1, 'token', ids)
            api['after'] = 'corrupt'
            with self.assertRaises(AssertionError):
                h.validate_boot('RUFUS_PERSISTENCE_RESULT=' + json.dumps(api) + '\nPower down', 0, 1, 'token', [])

    def test_cli_refuses_device_targets_instead_of_silently_succeeding(self):
        import subprocess
        import sys
        completed = subprocess.run([sys.executable, str(SCRIPT), '/dev/null'], capture_output=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(b'no path arguments', completed.stderr)

    def test_runner_requires_fresh_evidence_before_tools_or_writes(self):
        h = load()
        self.assertTrue(callable(getattr(h, 'run', None)), 'acceptance runner missing')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            iso = root / 'input.iso'
            iso.write_bytes(b'fixture')
            evidence = root / 'evidence'
            evidence.mkdir()
            with patch.dict(os.environ, {'GRAVESTONE_TEST_ISO_SHA256': 'a' * 64}):
                with self.assertRaises((ValueError, FileExistsError)):
                    h.run(iso, evidence)
            self.assertEqual(list(evidence.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
