"""Scratch-only backup security and byte preservation tests."""
import importlib.util
import tempfile
import unittest
from pathlib import Path


class BackupTests(unittest.TestCase):
    def test_exact_allowlisted_roundtrip_and_no_replace(self):
        self.assertIsNotNone(importlib.util.find_spec('app.backup'), 'Safe backup is missing')
        from app.backup import export_backup, restore_backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            notes = b'Human notebook\n\x00exact bytes\r\n'
            (source / 'notes.txt').write_bytes(notes)
            (source / 'Firefox').mkdir()
            (source / 'Firefox' / 'secret').write_text('never export')
            (source / 'host-secret').write_text('never export')
            archive = root / 'backup.tar'
            report = export_backup(source, archive)
            self.assertEqual([f['path'] for f in report['files']], ['notes.txt'])
            self.assertNotIn(b'never export', archive.read_bytes())
            target = root / 'restored'
            restore_backup(archive, target)
            self.assertEqual((target / 'notes.txt').read_bytes(), notes)
            with self.assertRaises((OSError, ValueError)):
                restore_backup(archive, target)
            with self.assertRaises((OSError, ValueError)):
                export_backup(source, archive)
            self.assertEqual((target / 'notes.txt').read_bytes(), notes)

    def make_archive(self, path, entries, schema=1, mutate=None):
        import hashlib
        import io
        import json
        import tarfile
        records = [{'path': name, 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                   for name, raw, kind in entries]
        manifest = {'schema': schema, 'files': records}
        if mutate:
            mutate(manifest)
        with tarfile.open(path, 'w', format=tarfile.USTAR_FORMAT) as archive:
            raw = json.dumps(manifest).encode()
            info = tarfile.TarInfo('manifest.json')
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
            for name, raw, kind in entries:
                info = tarfile.TarInfo(name)
                info.type = kind
                info.linkname = 'notes.txt' if kind in (tarfile.LNKTYPE, tarfile.SYMTYPE) else ''
                info.size = len(raw)
                archive.addfile(info, io.BytesIO(raw))

    def test_invalid_archives_never_publish(self):
        import tarfile
        from app.backup import restore_backup
        cases = [(name, b'bad', tarfile.REGTYPE) for name in
                 ('../escape', '/absolute', 'maps/../notes.txt', 'maps\\escape', './notes.txt',
                  'random.txt', 'maps/51013-roads/unknown', 'notes.txt/child')]
        cases += [('notes.txt', b'', kind) for kind in
                  (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE,
                   tarfile.BLKTYPE, tarfile.DIRTYPE, tarfile.XHDTYPE, tarfile.GNUTYPE_SPARSE)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / 'bad.tar'
            target = root / 'new'
            for entry in cases:
                with self.subTest(entry=entry):
                    self.make_archive(archive, [entry])
                    with self.assertRaises((ValueError, OSError)):
                        restore_backup(archive, target)
                    self.assertFalse(target.exists())
                    self.assertEqual(sorted(p.name for p in root.iterdir()), ['bad.tar'])
            for schema in (0, 2, True, '1', None):
                self.make_archive(archive, [('notes.txt', b'abc', tarfile.REGTYPE)], schema=schema)
                with self.assertRaises((ValueError, OSError)):
                    restore_backup(archive, target)
            self.make_archive(archive, [('notes.txt', b'abc', tarfile.REGTYPE)] * 2)
            with self.assertRaises((ValueError, OSError)):
                restore_backup(archive, target)
            self.make_archive(archive, [('notes.txt', b'abc', tarfile.REGTYPE)],
                              mutate=lambda m: m['files'][0].update(sha256='0' * 64))
            with self.assertRaises((ValueError, OSError)):
                restore_backup(archive, target)
            self.assertFalse(target.exists())

    def test_symlink_ancestors_nonregular_and_hardlinks_refused(self):
        from app.backup import export_backup, restore_backup
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (root / 'alias').symlink_to(source, target_is_directory=True)
            with self.assertRaises((ValueError, OSError)):
                export_backup(root / 'alias', root / 'out.tar')
            for kind in ('symlink', 'fifo', 'hardlink'):
                with self.subTest(kind=kind):
                    note = source / 'notes.txt'
                    if kind == 'symlink':
                        note.symlink_to(root / 'outside')
                    elif kind == 'fifo':
                        os.mkfifo(note)
                    else:
                        (root / 'outside').write_text('secret')
                        os.link(root / 'outside', note)
                    with self.assertRaises((ValueError, OSError)):
                        export_backup(source, root / 'out.tar')
                    note.unlink()
            (source / 'notes.txt').write_text('safe')
            export_backup(source, root / 'out.tar')
            with self.assertRaises((ValueError, OSError)):
                restore_backup(root / 'out.tar', root / 'alias' / 'target')
            for path in (source, Path('/dev/null')):
                with self.assertRaises((ValueError, OSError)):
                    restore_backup(path, root / 'target')

    def test_limits_corruption_truncation_and_manifest_strictness(self):
        import tarfile
        from unittest.mock import patch
        from app import backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, target = root / 'bad.tar', root / 'new'
            self.make_archive(archive, [('notes.txt', b'abc', tarfile.REGTYPE)])
            original = archive.read_bytes()
            for raw in (original[:-1024], original[:-1], b'not a tar', original + b'x' * 512,
                        original[:512] + b'x' + original[513:], b'\x1f\x8b' + original[2:]):
                # Removing only final padding is still valid; require actual content truncation.
                if raw == original[:-1024]:
                    raw = original[:1600]
                archive.write_bytes(raw)
                with self.assertRaises((ValueError, OSError)):
                    backup.restore_backup(archive, target)
                self.assertFalse(target.exists())
            for change in (lambda m: m.update(unexpected=True),
                           lambda m: m.update(files=[]),
                           lambda m: m['files'][0].update(size=True),
                           lambda m: m['files'].append(dict(m['files'][0])),
                           lambda m: m['files'][0].update(path='../escape')):
                self.make_archive(archive, [('notes.txt', b'abc', tarfile.REGTYPE)], mutate=change)
                with self.assertRaises((ValueError, OSError)):
                    backup.restore_backup(archive, target)
            self.make_archive(archive, [('notes.txt', b'abc', tarfile.REGTYPE)])
            for limit, value in [('MAX_ARCHIVE', 1024), ('MAX_TOTAL', 2), ('MAX_FILES', 0), ('MAX_MANIFEST', 2)]:
                with patch.object(backup, limit, value), self.assertRaises((ValueError, OSError)):
                    backup.restore_backup(archive, target)
            # Declared giant member: refuse before reading/allocating its payload.
            info = tarfile.TarInfo('notes.txt')
            info.size = 2**32
            archive.write_bytes(info.tobuf(format=tarfile.USTAR_FORMAT) + b'\0' * 1024)
            with self.assertRaises((ValueError, OSError)):
                backup.restore_backup(archive, target)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['bad.tar'])

    def test_directory_replacement_races_remain_confined_and_rollback(self):
        from unittest.mock import patch
        from app import backup
        for operation in ('export-source', 'export-parent', 'restore-parent'):
            for ancestor in (False, True):
                with self.subTest(operation=operation, ancestor=ancestor), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    container = root / 'container'
                    container.mkdir()
                    source = container / 'source'
                    source.mkdir()
                    (source / 'notes.txt').write_bytes(b'only safe notes')
                    destination = container / 'dest'
                    destination.mkdir()
                    outside = root / 'outside'
                    outside.mkdir()
                    (outside / 'sentinel').write_bytes(b'never change external data')
                    archive = root / 'input.tar'
                    backup.export_backup(source, archive)
                    swapped = False
                    original = backup._collect if operation == 'export-source' else backup._write
                    replacement = container if ancestor else (source if operation == 'export-source' else destination)
                    moved = root / 'moved'
                    def swap(*args):
                        nonlocal swapped
                        result = original(*args)
                        if not swapped:
                            replacement.rename(moved)
                            replacement.symlink_to(outside, target_is_directory=True)
                            swapped = True
                        return result
                    hook = '_collect' if operation == 'export-source' else '_write'
                    with patch.object(backup, hook, side_effect=swap):
                        with self.assertRaises((ValueError, OSError)):
                            if operation == 'export-source':
                                backup.export_backup(source, root / 'out.tar')
                            elif operation == 'export-parent':
                                backup.export_backup(source, destination / 'out.tar')
                            else:
                                backup.restore_backup(archive, destination / 'new')
                    self.assertEqual([p.name for p in outside.iterdir()], ['sentinel'],
                                     'Wrote through a replaced root/ancestor')
                    self.assertEqual((outside / 'sentinel').read_bytes(), b'never change external data')
                    checked = moved / 'dest' if ancestor and operation != 'export-source' else moved
                    if operation != 'export-source':
                        self.assertEqual(list(checked.iterdir()), [], 'Failed operation leaked staging')

    def test_atomic_publish_never_replaces_concurrently_created_target(self):
        from unittest.mock import patch
        from app import backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'notes.txt').write_text('private')
            archive = root / 'input.tar'
            backup.export_backup(source, archive)
            target = root / 'new'
            publish = backup._publish
            def collide(parent, temporary, name):
                target.mkdir()
                (target / 'sentinel').write_text('keep')
                return publish(parent, temporary, name)
            with patch.object(backup, '_publish', side_effect=collide), self.assertRaises(OSError):
                backup.restore_backup(archive, target)
            self.assertEqual((target / 'sentinel').read_text(), 'keep')
            self.assertFalse(any(p.name.startswith('.restore-') for p in root.iterdir()))

    def test_failed_export_write_cleans_partial_and_preserves_existing(self):
        from unittest.mock import patch
        from app import backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'notes.txt').write_text('safe')
            with patch.object(backup.os, 'fsync', side_effect=OSError('injected I/O failure')):
                with self.assertRaises(OSError):
                    backup.export_backup(source, root / 'out.tar')
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['source'])

    def test_cli_standalone_export_restore_and_existing_directory_refusal(self):
        import json
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'notes.txt').write_text('saved human text')
            script = Path(__file__).resolve().parents[1] / 'scripts/gravestone-backup.py'
            self.assertTrue(script.is_file(), 'Standalone backup CLI missing')
            archive = root / 'backup.tar'
            def run(command, data):
                return subprocess.run([sys.executable, str(script), command, '--data-dir', str(data),
                                       '--archive', str(archive)], cwd=tmp, capture_output=True, text=True)
            result = run('export', source)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('NOT encrypted', result.stderr)
            self.assertEqual(json.loads(result.stdout)['schema'], 1)
            target = root / 'restored'
            self.assertEqual(run('restore', target).returncode, 0)
            empty = root / 'empty'
            empty.mkdir()
            self.assertNotEqual(run('restore', empty).returncode, 0)
            self.assertEqual(list(empty.iterdir()), [])
            self.assertNotEqual(run('restore', target).returncode, 0)
            self.assertEqual((target / 'notes.txt').read_bytes(), (source / 'notes.txt').read_bytes())

    def test_postpublication_fsync_failure_does_not_erase_verified_data(self):
        import os
        from unittest.mock import patch
        from app import backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'notes.txt').write_text('preserve after publication')
            archive = root / 'input.tar'
            backup.export_backup(source, archive)
            target = root / 'new'
            sync = os.fsync
            def fail_after_commit(fd):
                if target.exists() and os.fstat(fd).st_ino == root.stat().st_ino:
                    raise OSError('injected publication durability failure')
                return sync(fd)
            with patch.object(backup.os, 'fsync', side_effect=fail_after_commit), self.assertRaises(OSError):
                backup.restore_backup(archive, target)
            self.assertEqual((target / 'notes.txt').read_text(), 'preserve after publication')

    def test_noncanonical_embedded_nul_archive_names_are_rejected(self):
        import tarfile
        from app import backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / 'bad.tar'
            self.make_archive(archive, [('notes.txt', b'abc', tarfile.REGTYPE)])
            raw = bytearray(archive.read_bytes())
            # Third 512-byte block: manifest header+body, then data header.
            offset = 1024
            header = raw[offset:offset + 512]
            header[:100] = b'notes.txt\0../hidden'.ljust(100, b'\0')
            header[148:156] = b' ' * 8
            checksum = sum(header)
            header[148:156] = ('%06o\0 ' % checksum).encode('ascii')
            raw[offset:offset + 512] = header
            archive.write_bytes(raw)
            with self.assertRaises((ValueError, OSError)):
                backup.restore_backup(archive, root / 'new')

    def test_restore_staging_substitution_fails_without_outside_writes(self):
        from unittest.mock import patch
        from app import backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'notes.txt').write_text('safe')
            archive = root / 'input.tar'
            backup.export_backup(source, archive)
            outside = root / 'outside'
            outside.mkdir()
            (outside / 'sentinel').write_bytes(b'never delete external data')
            original = backup._write
            def substitute(*args):
                result = original(*args)
                staging = next(root.glob('.restore-*'))
                staging.rename(root / 'moved-staging')
                staging.symlink_to(outside, target_is_directory=True)
                return result
            with patch.object(backup, '_write', side_effect=substitute), self.assertRaises((OSError, ValueError)):
                backup.restore_backup(archive, root / 'new')
            self.assertFalse((root / 'new').exists())
            self.assertEqual([p.name for p in outside.iterdir()], ['sentinel'])
            self.assertEqual((outside / 'sentinel').read_bytes(), b'never delete external data')
            self.assertEqual(list((root / 'moved-staging').iterdir()), [])

    def test_pack_integrity_bounds_and_unknown_files_not_exported(self):
        import hashlib
        import json
        from app import backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            pack = source / 'maps/51013-roads'
            pack.mkdir(parents=True)
            original, geometry = b'opaque ZIP bytes', b'geometry bytes'
            (pack / 'original.zip').write_bytes(original)
            (pack / 'data.geojson').write_bytes(geometry)
            metadata = {'id': '51013-roads', 'sha256': hashlib.sha256(original).hexdigest(),
                        'data_sha256': hashlib.sha256(geometry).hexdigest()}
            (pack / 'metadata.json').write_text(json.dumps(metadata))
            (pack / 'random-secret').write_text('never copy')
            report = backup.export_backup(source, root / 'valid.tar')
            self.assertEqual(len(report['files']), 3)
            self.assertNotIn(b'never copy', (root / 'valid.tar').read_bytes())
            (pack / 'data.geojson').write_bytes(b'corruption')
            with self.assertRaises(ValueError):
                backup.export_backup(source, root / 'out.tar')
            (pack / 'original.zip').unlink()
            with self.assertRaises((OSError, ValueError)):
                backup.export_backup(source, root / 'out.tar')
            (source / 'notes.txt').write_bytes(b'n' * (256 * 1024 + 1))
            with self.assertRaises(ValueError):
                backup.export_backup(source, root / 'out.tar')
            self.assertFalse((root / 'out.tar').exists())

    def test_duplicate_json_and_unmanifested_files_fail_before_staging(self):
        import io
        import tarfile
        from unittest.mock import patch
        from app import backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / 'bad.tar'
            for manifest in (b'{"schema":1,"schema":1,"files":[]}',
                             b'{"schema":1,"files":[],"unexpected":null}'):
                with tarfile.open(archive, 'w', format=tarfile.USTAR_FORMAT) as tar:
                    info = tarfile.TarInfo('manifest.json')
                    info.size = len(manifest)
                    tar.addfile(info, io.BytesIO(manifest))
                with patch.object(backup, '_write', side_effect=AssertionError('Must not stage invalid data')):
                    with self.assertRaises(ValueError):
                        backup.restore_backup(archive, root / 'new')
            self.make_archive(archive, [('notes.txt', b'abc', tarfile.REGTYPE)],
                              mutate=lambda m: m.update(files=[]))
            with patch.object(backup, '_write', side_effect=AssertionError('Must not stage invalid data')):
                with self.assertRaises(ValueError):
                    backup.restore_backup(archive, root / 'new')
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['bad.tar'])

    def test_restore_parent_fsync_failure_closes_opened_child_descriptor(self):
        import hashlib
        import json
        import os
        import tarfile
        from unittest.mock import patch
        from app import backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, target = root / 'input.tar', root / 'new'
            original, geometry = b'opaque ZIP bytes', b'geometry bytes'
            metadata = {'id': '51013-roads', 'sha256': hashlib.sha256(original).hexdigest(),
                        'data_sha256': hashlib.sha256(geometry).hexdigest()}
            self.make_archive(archive, [
                ('maps/51013-roads/original.zip', original, tarfile.REGTYPE),
                ('maps/51013-roads/data.geojson', geometry, tarfile.REGTYPE),
                ('maps/51013-roads/metadata.json', json.dumps(metadata).encode(), tarfile.REGTYPE),
            ])
            directory, sync = backup._directory, os.fsync
            opened = {}
            failed = False
            def track_child(parent, name):
                child = directory(parent, name)
                if name == 'maps' and not opened:
                    opened.update(parent=parent, child=child)
                return child
            def fail_parent_after_child_open(fd):
                nonlocal failed
                if not failed and fd == opened.get('parent'):
                    self.assertTrue(os.readlink('/proc/self/fd/' + str(fd)).startswith(str(root / '.restore-')))
                    self.assertTrue(os.readlink('/proc/self/fd/' + str(opened['child'])).endswith('/maps'))
                    failed = True
                    raise OSError('injected staging-parent fsync failure after child open')
                return sync(fd)
            before = set(os.listdir('/proc/self/fd'))
            with patch.object(backup, '_directory', side_effect=track_child):
                with patch.object(backup.os, 'fsync', side_effect=fail_parent_after_child_open):
                    with self.assertRaisesRegex(OSError, 'injected staging-parent fsync failure after child open'):
                        backup.restore_backup(archive, target)
            self.assertTrue(failed, 'Did not reach parent fsync after opening the child')
            self.assertFalse(target.exists())
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['input.tar'])
            after = set(os.listdir('/proc/self/fd'))
            try:
                remaining_child = os.readlink('/proc/self/fd/' + str(opened['child']))
            except FileNotFoundError:
                remaining_child = None
            self.assertEqual(len(after), len(before), 'Leaked child descriptor: ' + str(remaining_child))

    def test_cleanup_error_closes_all_directory_descriptors(self):
        import os
        from unittest.mock import patch
        from app import backup
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'notes.txt').write_text('safe')
            archive = root / 'input.tar'
            backup.export_backup(source, archive)
            before = set(os.listdir('/proc/self/fd'))
            with patch.object(backup, '_publish', side_effect=OSError('publish failed')):
                with patch.object(backup, '_clear', side_effect=OSError('cleanup failed')):
                    with self.assertRaises(OSError):
                        backup.restore_backup(archive, root / 'new')
            self.assertEqual(set(os.listdir('/proc/self/fd')), before)


if __name__ == '__main__':
    unittest.main()
