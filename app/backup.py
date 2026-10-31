"""Bounded, unencrypted notebook/map snapshots; Linux descriptor-relative publication.

No archive extraction API is used. Only an exact regular-file allowlist is copied.
Restore always requires a nonexistent destination, never merges or overwrites.
"""
import argparse
import ctypes
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tarfile

from . import open_root

MAX_ARCHIVE = 50 * 1024 * 1024
MAX_TOTAL = 48 * 1024 * 1024
MAX_FILE = 32 * 1024 * 1024
MAX_FILES = 1000
MAX_MANIFEST = 512 * 1024
PACK = re.compile(r'[0-9]{5}-(roads|water)')
MEMBERS = {'original.zip', 'data.geojson', 'metadata.json'}


def _allowed(name):
    if name == 'notes.txt':
        return True
    parts = name.split('/') if isinstance(name, str) else []
    return (len(parts) == 3 and parts[0] == 'maps' and PACK.fullmatch(parts[1]) is not None
            and parts[2] in MEMBERS)


def _limit(name):
    return 256 * 1024 if name == 'notes.txt' else 32768 if name.endswith('/metadata.json') else MAX_FILE


def _directory(parent, name):
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)


def _read(parent, name, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise ValueError('Not a bounded, single-link regular file: ' + name)
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(raw) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns) or len(raw) != after.st_size:
            raise ValueError('File changed while reading or exceeded bound: ' + name)
        return raw


def _same_root(path, directory):
    check = open_root(path)
    try:
        a, b = os.fstat(check), os.fstat(directory)
        if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
            raise ValueError('Directory changed during operation')
    finally:
        os.close(check)


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (UnicodeError, RecursionError) as error:
        raise ValueError('Invalid JSON') from error


def _validate_files(files):
    if len(files) > MAX_FILES or sum(len(raw) for raw in files.values()) > MAX_TOTAL:
        raise ValueError('Snapshot exceeds file count or total byte limit')
    packs = {}
    for name, raw in files.items():
        if not _allowed(name) or len(raw) > _limit(name):
            raise ValueError('Unexpected or oversized file: ' + name)
        if name.startswith('maps/'):
            _, ident, leaf = name.split('/')
            packs.setdefault(ident, set()).add(leaf)
    for ident, leaves in packs.items():
        if leaves != MEMBERS:
            raise ValueError('Incomplete map pack')
        prefix = 'maps/' + ident + '/'
        meta = _json(files[prefix + 'metadata.json'])
        if (not isinstance(meta, dict) or meta.get('id') != ident
                or meta.get('sha256') != hashlib.sha256(files[prefix + 'original.zip']).hexdigest()
                or meta.get('data_sha256') != hashlib.sha256(files[prefix + 'data.geojson']).hexdigest()):
            raise ValueError('Installed map metadata/hash mismatch')


def _collect(directory):
    files = {}
    try:
        files['notes.txt'] = _read(directory, 'notes.txt', _limit('notes.txt'))
    except FileNotFoundError:
        pass
    try:
        maps = _directory(directory, 'maps')
    except FileNotFoundError:
        maps = None
    if maps is not None:
        try:
            # Enumeration itself is bounded; unrelated root files are never inspected.
            count = 0
            with os.scandir(maps) as entries:
                for entry in entries:
                    count += 1
                    if count > MAX_FILES:
                        raise ValueError('Too many map directory entries')
                    if not PACK.fullmatch(entry.name):
                        continue
                    pack = _directory(maps, entry.name)
                    try:
                        for leaf in sorted(MEMBERS):
                            name = 'maps/' + entry.name + '/' + leaf
                            files[name] = _read(pack, leaf, _limit(name))
                            if len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_TOTAL:
                                raise ValueError('Snapshot exceeds limits')
                    finally:
                        os.close(pack)
        finally:
            os.close(maps)
    _validate_files(files)
    return files


def _manifest(files):
    return {'schema': 1, 'files': [{'path': name, 'size': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in sorted(files.items())]}


def _encode(files):
    report = _manifest(files)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in [('manifest.json', json.dumps(report, separators=(',', ':')).encode())] + sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(raw), 0o600, 0
            archive.addfile(info, io.BytesIO(raw))
    raw = output.getvalue()
    if len(raw) > MAX_ARCHIVE:
        raise ValueError('Archive exceeds 50 MiB')
    return raw, report


def _decode(raw):
    if len(raw) > MAX_ARCHIVE or len(raw) % 512:
        raise ValueError('Invalid archive length')
    offset, files, total = 0, {}, 0
    while offset + 512 <= len(raw):
        header = raw[offset:offset + 512]
        if header == b'\0' * 512:
            if len(raw) - offset < 1024 or any(raw[offset:]):
                raise ValueError('Invalid tar terminator/trailing data')
            break
        try:
            info = tarfile.TarInfo.frombuf(header, 'utf-8', 'strict')
        except (tarfile.TarError, UnicodeError, ValueError) as error:
            raise ValueError('Invalid tar header/checksum') from error
        name = info.name
        if (header[257:265] != b'ustar\x0000' or any(header[345:500])
                or header[:100] != name.encode('utf-8').ljust(100, b'\0')
                or any(header[157:257])):
            raise ValueError('Noncanonical USTAR header/name')
        if (info.type not in (tarfile.REGTYPE, tarfile.AREGTYPE) or info.linkname
                or not (name == 'manifest.json' or _allowed(name)) or name in files
                or info.size < 0 or info.size > (MAX_MANIFEST if name == 'manifest.json' else _limit(name))
                or len(files) >= MAX_FILES + 1):
            raise ValueError('Unsafe, duplicate, unknown or oversized archive entry')
        start = offset + 512
        end = start + info.size
        offset = start + ((info.size + 511) // 512) * 512
        total += info.size
        if offset > len(raw) or total > MAX_TOTAL + MAX_MANIFEST:
            raise ValueError('Archive exceeds bounds or is truncated')
        if any(raw[end:offset]):
            raise ValueError('Nonzero file padding')
        files[name] = raw[start:end]
    else:
        raise ValueError('Missing tar terminator')
    if 'manifest.json' not in files:
        raise ValueError('Manifest missing')
    manifest = _json(files.pop('manifest.json'))
    if (not isinstance(manifest, dict) or set(manifest) != {'schema', 'files'}
            or type(manifest['schema']) is not int or manifest['schema'] != 1
            or not isinstance(manifest['files'], list) or len(manifest['files']) > MAX_FILES):
        raise ValueError('Unknown or invalid manifest schema')
    seen = set()
    for record in manifest['files']:
        if (not isinstance(record, dict) or set(record) != {'path', 'size', 'sha256'}
                or not isinstance(record['path'], str) or not _allowed(record['path'])
                or record['path'] in seen or type(record['size']) is not int
                or record['size'] < 0 or not isinstance(record['sha256'], str)
                or re.fullmatch('[0-9a-f]{64}', record['sha256']) is None):
            raise ValueError('Invalid manifest record')
        name = record['path']
        seen.add(name)
        if (name not in files or len(files[name]) != record['size']
                or hashlib.sha256(files[name]).hexdigest() != record['sha256']):
            raise ValueError('Backup byte/hash verification failed')
    if seen != set(files):
        raise ValueError('Unmanifested archive files')
    _validate_files(files)
    return files, manifest


def _parent(path):
    # Reject '..' rather than normalizing away a potentially symlinked ancestor.
    text = os.fspath(path)
    if '\x00' in text or '\\' in text or '..' in Path(text).parts:
        raise ValueError('Unsafe target path')
    path = Path(os.path.abspath(text))
    if not path.name:
        raise ValueError('A named target is required')
    return path, open_root(path.parent)


def _absent(parent, name):
    try:
        os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise FileExistsError('Target exists; no replacement or merging is permitted: ' + name)


def _write(directory, name, raw):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            return os.fstat(stream.fileno())
    except BaseException:
        os.unlink(name, dir_fd=directory)
        raise


def _same_entry(parent, name, expected):
    actual = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if (actual.st_dev, actual.st_ino, actual.st_mode) != (expected.st_dev, expected.st_ino, expected.st_mode):
        raise ValueError('Staging entry changed during operation')


def _publish(parent, temporary, target):
    rename = getattr(ctypes.CDLL(None, use_errno=True), 'renameat2', None)
    if rename is None:
        raise OSError(errno.ENOSYS, 'Atomic no-replace publication requires Linux renameat2')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(parent, os.fsencode(temporary), parent, os.fsencode(target), 1):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), target)


def _clear(directory):
    for name in os.listdir(directory):
        mode = os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode
        if stat.S_ISDIR(mode):
            child = _directory(directory, name)
            try:
                _clear(child)
            finally:
                os.close(child)
            os.rmdir(name, dir_fd=directory)
        else:
            os.unlink(name, dir_fd=directory)


def export_backup(data_dir, archive_path):
    """Save only notes.txt and complete installed map triples. Never overwrite."""
    if '..' in Path(data_dir).parts:
        raise ValueError('Unsafe source path')
    directory = open_root(data_dir)
    try:
        files = _collect(directory)
        _same_root(data_dir, directory)
    finally:
        os.close(directory)
    raw, report = _encode(files)
    path, parent = _parent(archive_path)
    temporary = '.backup-' + secrets.token_hex(16)
    created = False
    try:
        _absent(parent, path.name)
        # O_EXCL also prevents substituting a symlink for the temporary file.
        written = _write(parent, temporary, raw)
        created = True
        _same_root(path.parent, parent)
        _same_entry(parent, temporary, written)
        _publish(parent, temporary, path.name)
        created = False
        os.fsync(parent)
    finally:
        try:
            if created:
                os.unlink(temporary, dir_fd=parent)
        finally:
            os.close(parent)
    return report


def restore_backup(archive_path, data_dir):
    """Validate every byte before staging, then atomically publish a NEW data dir."""
    archive, source = _parent(archive_path)
    try:
        raw = _read(source, archive.name, MAX_ARCHIVE)
    finally:
        os.close(source)
    files, report = _decode(raw)
    path, parent = _parent(data_dir)
    temporary = '.restore-' + secrets.token_hex(16)
    staging = None
    created = False
    try:
        _absent(parent, path.name)
        os.mkdir(temporary, 0o700, dir_fd=parent)
        created = True
        staging = _directory(parent, temporary)
        for name, body in sorted(files.items()):
            current = os.dup(staging)
            try:
                parts = name.split('/')
                for part in parts[:-1]:
                    try:
                        os.mkdir(part, 0o700, dir_fd=current)
                    except FileExistsError:
                        pass
                    previous = current
                    current = _directory(previous, part)
                    try:
                        os.fsync(previous)
                    finally:
                        os.close(previous)
                _write(current, parts[-1], body)
                os.fsync(current)
            finally:
                os.close(current)
        os.fsync(staging)
        _same_root(path.parent, parent)
        _same_entry(parent, temporary, os.fstat(staging))
        _publish(parent, temporary, path.name)
        created = False
        os.fsync(parent)
    finally:
        try:
            try:
                if created and staging is not None:
                    _clear(staging)
            finally:
                if staging is not None:
                    os.close(staging)
            if created:
                if stat.S_ISLNK(os.stat(temporary, dir_fd=parent, follow_symlinks=False).st_mode):
                    os.unlink(temporary, dir_fd=parent)
                else:
                    os.rmdir(temporary, dir_fd=parent)
        finally:
            os.close(parent)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Unencrypted bounded notebook/map backups. Stop the app before export. No overwrites.')
    sub = parser.add_subparsers(dest='command', required=True)
    for operation in ('export', 'restore'):
        item = sub.add_parser(operation)
        item.add_argument('--data-dir', required=True, help='Source directory for export; NONEXISTENT new directory for restore')
        item.add_argument('--archive', required=True, help='Uncompressed .tar archive; nonexistent for export')
    args = parser.parse_args(argv)
    print('WARNING: backup is NOT encrypted; protect private notes and map location data.', file=sys.stderr)
    try:
        report = (export_backup(args.data_dir, args.archive) if args.command == 'export'
                  else restore_backup(args.archive, args.data_dir))
    except (OSError, ValueError, tarfile.TarError) as error:
        print('Refused: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
