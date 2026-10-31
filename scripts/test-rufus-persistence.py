#!/usr/bin/env python3
"""Constructed Rufus-like GPT/FAT32 + 4 GiB root-union acceptance, NOT Rufus.

Run only in an offline, unprivileged disposable container (<=2500 MiB, 1 CPU),
with the pinned ISO read-only at /input/release.iso and fresh /evidence absent.
No path/device CLI arguments. No mounts, loop devices, CD-ROM or direct kernel.
The VM-only GRUB menu debug arguments never modify the ISO or checkout.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
import hashlib
import json
import shutil
import subprocess
import inspect
import urllib.request
import base64
import secrets
import socket
import time
import sys


def checkpoint(root, result):
    root = canonical(root)
    target = root / 'result.json'
    if target.exists() or target.is_symlink():
        regular(target)
    temporary = fresh_file(root / 'result.tmp')
    try:
        with temporary.open('w') as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def validate_boot(text, returncode, phase, token, previous_ids):
    matches = re.findall(r'RUFUS_PERSISTENCE_RESULT=(\{[^\r\n]+\})\r?$', text, re.MULTILINE)
    assert len(matches) == 1, 'missing/duplicate API assertion result'
    record = json.loads(matches[0])
    assert returncode == 0 and 'Power down' in text, 'clean kernel poweroff missing'
    assert record['phase'] == phase
    first = token + ': boot one\nUTF-8: 雪\n<literal & text>\n'
    second = first + 'Updated during boot two\n'
    assert record['before'] == ['', first, second][phase - 1]
    assert record['after'] == (first if phase == 1 else second)
    boot_id = record['boot_id']
    assert re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot_id)
    assert boot_id not in previous_ids, 'boot ID reused'
    assert REQUIRED_ARGS <= set(record['cmdline'].split()) and 'nopersistence' not in record['cmdline'].split()
    validate_mounts(record)
    record.update(qemu_exit=returncode, clean_poweroff=True, fsck_passed=False)
    return record


def boot_once(args, root, phase, token, previous_ids=(), timeout=300):
    """One monotonic boot budget; always reap ONLY the child we started."""
    if not 0 < timeout <= 300:
        raise ValueError('boot timeout must be positive and at most 300 seconds')
    root = canonical(root)
    serial = root / 'serial.sock'
    if serial.exists():
        if not stat.S_ISSOCK(serial.lstat().st_mode):
            raise ValueError('unexpected serial endpoint')
        serial.unlink()
    command_file = fresh_file(root / f'boot-{phase}-command.json')
    command_file.write_text(json.dumps(args, indent=2) + '\n')
    transcript = bytearray()
    proc = None
    conn = socket.socket(socket.AF_UNIX)
    deadline = time.monotonic() + timeout
    with (root / f'boot-{phase}-qemu.log').open('xb') as errors, (root / f'boot-{phase}-serial.log').open('xb') as log:
        try:
            proc = subprocess.Popen(args, stdout=errors, stderr=errors)
            connected, sent = False, False
            while time.monotonic() < deadline:
                if not connected:
                    try:
                        conn.connect(str(serial))
                        connected = True
                        conn.settimeout(min(1, timeout))
                    except (FileNotFoundError, ConnectionRefusedError):
                        if proc.poll() is not None:
                            break
                        time.sleep(min(.05, timeout))
                        continue
                try:
                    data = conn.recv(65536)
                except socket.timeout:
                    data = b''
                if data:
                    transcript.extend(data)
                    log.write(data)
                    log.flush()
                if len(transcript) > 32 * MIB:
                    raise RuntimeError('serial evidence exceeds 32 MiB bound')
                if not sent and b'GRAVESTONE_SERVICE_READY' in transcript:
                    payload = base64.b64encode(guest_program(phase, token).encode()).decode()
                    # Linux canonical TTY lines are bounded. Never send an 8 KiB
                    # single line: chunk base64 into <1 KiB commands instead.
                    conn.sendall(b'\nstty -echo\n: > /run/gravestone-acceptance.b64\n')
                    for offset in range(0, len(payload), 512):
                        conn.sendall(f"printf '%s' '{payload[offset:offset + 512]}' >> /run/gravestone-acceptance.b64\n".encode())
                    conn.sendall(b'python3 -c "import base64,pathlib;exec(base64.b64decode(pathlib.Path(\'/run/gravestone-acceptance.b64\').read_bytes()))"; systemctl poweroff\n')
                    sent = True
                if proc.poll() is not None:
                    # Drain buffered serial bytes after the child exits.
                    conn.settimeout(.1)
                    while True:
                        try:
                            tail = conn.recv(65536)
                        except (socket.timeout, ConnectionResetError):
                            break
                        if not tail:
                            break
                        transcript.extend(tail)
                        log.write(tail)
                    break
            if proc.poll() is None:
                raise TimeoutError(f'boot {phase}: no clean shutdown within {timeout}s')
            return validate_boot(transcript.decode(errors='replace'), proc.returncode,
                                 phase, token, previous_ids)
        finally:
            conn.close()
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


def validate_limits(memory, cpu, interfaces):
    quota, period = cpu.split()
    if (memory == 'max' or not 0 < int(memory) <= 2500 * MIB or
            quota == 'max' or not 0 < int(quota) <= int(period) or
            set(interfaces) != {'lo'}):
        raise ValueError('require offline Docker --network none --memory 2500m --cpus 1 (or lower limits)')


def run(iso=Path('/input/release.iso'), root=Path('/evidence')):
    """No CLI targets. Use fresh container storage, not host devices or mounts."""
    pin = expected_iso_digest()  # Validate format before filesystem operations.
    iso, root = regular(iso), canonical(root)
    if root.exists() or root.is_symlink():
        raise FileExistsError('evidence must not exist; refusing storage reuse')
    if not Path('/.dockerenv').is_file() or not __debug__:
        raise ValueError('requires disposable Docker container and Python assertions enabled')
    root.mkdir(mode=0o700)
    result = {'passed': False, 'boots': [], 'expected_iso_sha256': pin,
              'method': 'constructed Rufus-like equivalent, NOT actual Rufus execution; '
                        'OVMF extracted whole-ISO FAT32 + same single removable USB 4 GiB '
                        'ext4 / union; VM-only serial debug arguments; no Secure Boot/graphics/hardware claim',
              'rufus_source': RUFUS_SOURCE}
    checkpoint(root, result)
    try:
        validate_limits(Path('/sys/fs/cgroup/memory.max').read_text().strip(),
                        Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
                        [p.name for p in Path('/sys/class/net').iterdir()])
        with iso.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        result['iso_sha256'] = digest
        if digest != pin:
            raise ValueError('ISO SHA-256 does not match explicit pin')
        # Extraction + FAT staging + streamed USB peak. Never fill this shared host.
        needed = 4 * iso.stat().st_size + 512 * MIB
        result['required_free_bytes'] = needed
        if shutil.disk_usage(root).free < needed:
            raise ValueError('insufficient scratch space; use an external CI runner')
        checkpoint(root, result)
        tree = root / 'iso-tree'
        with (root / 'extract.log').open('xb') as log:
            command(['xorriso', '-osirrox', 'on', '-indev', iso, '-extract', '/', tree], stdout=log, stderr=log)
        with writable_iso_tree(tree, root):
            result['menu_instrumentation'] = instrument_menu(tree)
            disk, info = create_usb(tree, root)
            result['layout'] = info
            # Check copied shipped EFI loaders/platform configs byte-for-byte on FAT.
            shipped = [p for p in tree.rglob('*') if p.is_file() and
                       (p.suffix.lower() == '.efi' or (p.name == 'grub.cfg' and p.parent.name.endswith('-efi')))]
            if not shipped or not (tree / '.disk/info').is_file():
                raise ValueError('missing shipped UEFI loader/platform tree or discovery marker')
            result['shipped_efi_files'] = {}
            for path in shipped + [tree / '.disk/info']:
                relative = path.relative_to(tree).as_posix()
                contents = subprocess.check_output(['mtype', '-i', f'{disk}@@{info["fat_start"]}', '::/' + relative], timeout=30)
                if contents != path.read_bytes():
                    raise ValueError('FAT copy differs from shipped file: ' + relative)
                result['shipped_efi_files'][relative] = hashlib.sha256(contents).hexdigest()
        code = regular(Path('/usr/share/OVMF/OVMF_CODE.fd'))
        variables = fresh_file(root / 'OVMF_VARS.fd')
        shutil.copyfile(regular(Path('/usr/share/OVMF/OVMF_VARS.fd')), variables)
        result['token'] = secrets.token_hex(16)
        checkpoint(root, result)
        for phase in (1, 2, 3):
            record = boot_once(vm_command(disk, code, variables, root), root, phase,
                               result['token'], [b['boot_id'] for b in result['boots']])
            result['boots'].append(record)
            checkpoint(root, result)
            check_ext4(disk, info, root, phase)
            record['fsck_passed'] = True
            checkpoint(root, result)
        assert len(result['boots']) == 3 and len({b['boot_id'] for b in result['boots']}) == 3
        result['passed'] = True
    except BaseException as exc:
        result['passed'] = False
        result['error'] = repr(exc)
        raise
    finally:
        checkpoint(root, result)
    print('PASS: same-USB extracted UEFI / union notebook continuity across three clean boots', flush=True)
    return result


def api_probe(phase, token, base='http://127.0.0.1:8766'):
    """Exact JSON/UTF-8 assertions, including HTTP status readiness."""
    if phase not in (1, 2, 3):
        raise ValueError('phase must be 1, 2 or 3')
    first = token + ': boot one\nUTF-8: 雪\n<literal & text>\n'
    second = first + 'Updated during boot two\n'
    expected = ['', first, second][phase - 1]
    target = first if phase == 1 else second
    def request(path, payload=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(base + path, data=data,
                                     headers={'Origin': base, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as response:
            assert response.status == 200
            return json.loads(response.read().decode('utf-8'))
    request('/api/status')
    before = request('/api/notes')['text']
    assert before == expected, ('notebook mismatch', before, expected)
    if phase < 3:
        assert request('/api/notes', {'text': target}) == {'text': target}
    after = request('/api/notes')['text']
    assert after == target
    return {'phase': phase, 'before': before, 'after': after}


def validate_mounts(record):
    """Prove FAT boot + full-root writable ext4 upper are the SAME USB disk."""
    disks = [d for d in record['lsblk']['blockdevices'] if d['type'] == 'disk']
    assert len(disks) == 1, 'exactly one guest disk required'
    disk = disks[0]
    assert disk['tran'] == 'usb' and disk['rm'] in (True, 1), 'not removable USB'
    parts = disk['children']
    assert len(parts) == 2
    first, second = parts
    assert first['name'] == disk['name'] + '1' and first['fstype'] == 'vfat'
    assert second['name'] == disk['name'] + '2' and second['fstype'] == 'ext4'
    assert second['label'] == 'persistence'
    mounts = [line.split() for line in record['mountinfo'].splitlines()]
    root = [m for m in mounts if m[4] == '/']
    assert len(root) == 1
    sep = root[0].index('-')
    assert root[0][sep + 1] == 'overlay', 'root is not overlay'
    assert 'rw' in root[0][5].split(',')
    assert 'upperdir=' in root[0][sep + 3], 'root union is not writable'
    media = [m for m in mounts if m[4] in ('/run/live/medium', '/lib/live/mount/medium', '/live/image')]
    assert media and any(m[m.index('-') + 2] == '/dev/' + first['name'] and
                         m[m.index('-') + 1] == 'vfat' for m in media), 'wrong boot medium'
    backing = record['upper_backing'].split()
    assert len(backing) == 2 and backing[0].split('[')[0] == '/dev/' + second['name']
    assert backing[1] == 'ext4', 'root upperdir is not on persistent ext4'
    assert record['persistence_conf'] == '/ union\n', 'not Rufus root-union scope'


def guest_program(phase, token):
    if phase not in (1, 2, 3):
        raise ValueError('phase must be 1, 2 or 3')
    return ('import json, pathlib, subprocess, urllib.request\n' +
            inspect.getsource(api_probe) + '\n' + inspect.getsource(validate_mounts) + f'''
record = api_probe({phase}, {token!r})
record['mountinfo'] = pathlib.Path('/proc/self/mountinfo').read_text()
record['lsblk'] = json.loads(subprocess.check_output(['lsblk', '--json', '-o', 'NAME,TYPE,TRAN,RM,FSTYPE,LABEL'], text=True))
root = next(line.split() for line in record['mountinfo'].splitlines() if line.split()[4] == '/')
options = root[root.index('-') + 3].split(',')
upper = next(value.split('=', 1)[1] for value in options if value.startswith('upperdir='))
record['upper_backing'] = subprocess.check_output(['findmnt', '-n', '-o', 'SOURCE,FSTYPE', '--target', upper], text=True).strip()
conf = [pathlib.Path(line.split()[4]) / 'persistence.conf' for line in record['mountinfo'].splitlines()
        if ' - ext4 /dev/' in line and line.split()[4].startswith(('/run/live/', '/lib/live/', '/live/'))]
record['persistence_conf'] = next(path.read_text() for path in conf if path.is_file())
validate_mounts(record)
record['boot_id'] = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
record['cmdline'] = pathlib.Path('/proc/cmdline').read_text()
print('RUFUS_PERSISTENCE_RESULT=' + json.dumps(record), flush=True)
''')

MIB = 1024**2
PERSISTENCE_BYTES = 4 * 1024**3
RUFUS_SOURCE = {
    'commit': 'acf7de640848ab249bedeb6feb59b33001f656b6',
    'file': 'src/format_ext.c',
    'sha256': 'ef2c1026baeace5130837cabc43485340081bad482517a2727e796fef099516a',
    'persistence_conf': '/ union\n',
}
REQUIRED_ARGS = {'boot=live', 'persistence', 'live-media=removable',
                 'persistence-media=removable-usb', 'persistence-storage=filesystem'}
DEBUG_ARGS = ('console=tty0 console=ttyS0,115200 systemd.debug_shell=ttyS0 '
              'systemd.mask=serial-getty@ttyS0.service')


def command(args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, timeout=120, **kwargs)


@contextmanager
def writable_iso_tree(tree, root):
    """Validate the entire private extraction before changing scratch permissions.

    The caller owns a fresh 0700 container evidence root; no concurrent writers.
    Rejected trees stay untouched for diagnosis in that disposable container.
    """
    root, tree = canonical(root), canonical(tree)
    root_info = root.lstat()
    if (tree.parent != root or not stat.S_ISDIR(root_info.st_mode) or
            root_info.st_uid != os.geteuid() or root_info.st_mode & 0o077):
        raise ValueError('extraction requires a direct child of private owned scratch')
    directories, files, pending = [], set(), [tree]
    while pending:
        path = pending.pop()
        info = path.lstat()  # Never follow ISO symlinks, including directories.
        if (info.st_uid != os.geteuid() or
                info.st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX)):
            raise ValueError('unsupported ISO ownership/permissions: ' + str(path))
        if stat.S_ISDIR(info.st_mode):
            directories.append((canonical(path), stat.S_IMODE(info.st_mode)))
            with os.scandir(path) as entries:
                pending.extend(Path(entry.path) for entry in entries)
        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            files.add(canonical(path))
        else:
            raise ValueError('unsupported ISO member: ' + str(path))
    menu = tree / 'boot/grub/grub.cfg'
    if not directories or directories[0][0] != tree or menu not in files:
        raise ValueError('missing extracted directory/menu')
    # xorriso restores publisher 0555/0444 modes. Only private scratch changes.
    for path, mode in directories:
        path.chmod(mode | stat.S_IWUSR | stat.S_IXUSR, follow_symlinks=False)
    try:
        menu.chmod(stat.S_IMODE(menu.lstat().st_mode) | stat.S_IWUSR,
                   follow_symlinks=False)
        yield tree
    finally:
        shutil.rmtree(tree)  # Keep small logs/result evidence, not the ISO copy.


def instrument_menu(tree):
    """Change kernel arguments ONLY; preserve every shipped EFI/platform file."""
    menu = regular(Path(tree) / 'boot/grub/grub.cfg')
    lines = menu.read_text().splitlines(keepends=True)
    count = 0
    for index, line in enumerate(lines):
        if re.match(r'^\s*linux(?:efi)?\s+', line):
            words = line.split()
            if not REQUIRED_ARGS <= set(words) or 'nopersistence' in words:
                raise ValueError('shipped live entry lacks removable/root persistence constraints')
            lines[index] = line.rstrip('\n') + ' ' + DEBUG_ARGS + '\n'
            count += 1
            break  # Default first entry only; never change the shipped failsafe.
    if not count:
        raise ValueError('no shipped Linux GRUB menu entry')
    before = hashlib.sha256(menu.read_bytes()).hexdigest()
    menu.write_text(''.join(lines))
    return {'path': 'boot/grub/grub.cfg', 'before_sha256': before,
            'after_sha256': hashlib.sha256(menu.read_bytes()).hexdigest(),
            'vm_only_added_args': DEBUG_ARGS}


def layout(fat_bytes):
    fat_bytes = max(80 * MIB, ((fat_bytes + MIB - 1) // MIB) * MIB)
    start = MIB + fat_bytes
    return {'fat_start': MIB, 'fat_bytes': fat_bytes,
            'persistence_start': start, 'persistence_bytes': PERSISTENCE_BYTES,
            'disk_bytes': start + PERSISTENCE_BYTES + MIB}


def partition_table(info):
    return ('label: gpt\nunit: sectors\n'
            f'start=2048, size={info["fat_bytes"] // 512}, type=U\n'
            f'start={info["persistence_start"] // 512}, '
            f'size={info["persistence_bytes"] // 512}, type=L\n')


def sparse_copy(source, destination, source_offset, destination_offset, length):
    """Bounded streaming, skip all-zero blocks in freshly sparse destinations."""
    source, destination = regular(source), regular(destination)
    if source == destination or length < 0 or min(source_offset, destination_offset) < 0:
        raise ValueError('invalid copy bounds')
    if source_offset + length > source.stat().st_size or destination_offset + length > destination.stat().st_size:
        raise ValueError('copy exceeds regular-file extent')
    with source.open('rb') as src, destination.open('r+b') as dst:
        src.seek(source_offset)
        dst.seek(destination_offset)
        remaining = length
        while remaining:
            block = src.read(min(MIB, remaining))
            if not block:
                raise ValueError('short partition read')
            if block.count(0) == len(block):
                dst.seek(len(block), os.SEEK_CUR)
            else:
                dst.write(block)
            remaining -= len(block)
        dst.flush()
        os.fsync(dst.fileno())


def create_usb(tree, root):
    """Fresh regular files only. No host mount, loop or block-device operations."""
    tree, root = canonical(tree), canonical(root)
    if not tree.is_dir() or not tree.is_relative_to(root):
        raise ValueError('extraction tree must be inside owned scratch root')
    entries = sorted(tree.rglob('*'))
    for entry in entries:
        if entry.is_symlink() or not (entry.is_dir() or entry.is_file()):
            raise ValueError('unsupported ISO member: ' + str(entry))
        if entry.is_file() and regular(entry).stat().st_size >= 2**32:
            raise ValueError('ISO member too large for FAT32')
    payload_bytes = sum(p.stat().st_size for p in entries if p.is_file())
    info = layout(payload_bytes + payload_bytes // 5 + 32 * MIB)
    disk = fresh_file(root / 'usb.raw', info['disk_bytes'])
    fat = fresh_file(root / 'boot.part', info['fat_bytes'])
    ext = fresh_file(root / 'persistence.part', PERSISTENCE_BYTES)
    seed = root / 'seed'
    seed.mkdir(mode=0o700)
    (seed / 'persistence.conf').write_bytes(b'/ union\n')
    with (root / 'fixture.log').open('xb') as log:
        command(['sfdisk', disk], input=partition_table(info).encode(), stdout=log, stderr=log)
        command(['mkfs.vfat', '-F', '32', '-n', 'GRAVESTONE', fat], stdout=log, stderr=log)
        # -d seeds exact root-union bytes; no mount even inside the container.
        command(['mkfs.ext4', '-F', '-L', 'persistence', '-m', '0',
                 '-E', 'lazy_itable_init=0,lazy_journal_init=0', '-d', seed, ext], stdout=log, stderr=log)
        for child in sorted(tree.iterdir()):
            command(['mcopy', '-s', '-i', fat, child, '::/'], stdout=log, stderr=log)
    sparse_copy(fat, disk, 0, info['fat_start'], info['fat_bytes'])
    fat.unlink()
    sparse_copy(ext, disk, 0, info['persistence_start'], PERSISTENCE_BYTES)
    ext.unlink()
    return disk, info


def check_ext4(disk, info, root, phase):
    """Extract ONLY the 4 GiB partition sparsely; e2fsck -fn never repairs it."""
    scratch = fresh_file(Path(root) / 'fsck.part', info['persistence_bytes'])
    try:
        sparse_copy(disk, scratch, info['persistence_start'], 0, info['persistence_bytes'])
        with (Path(root) / f'boot-{phase}-fsck.log').open('xb') as log:
            command(['e2fsck', '-fn', scratch], stdout=log, stderr=log)
    finally:
        scratch.unlink()


def vm_command(disk, code, variables, root):
    disk, code, variables = (regular(path) for path in (disk, code, variables))
    root = canonical(root)
    return ['qemu-system-x86_64', '-nodefaults', '-accel', 'tcg', '-m', '2048', '-smp', '1',
            '-nic', 'none', '-display', 'none', '-monitor', 'none', '-no-reboot',
            '-serial', f'unix:{root}/serial.sock,server=on,wait=off',
            '-drive', f'if=pflash,format=raw,readonly=on,file={code}',
            '-drive', f'if=pflash,format=raw,file={variables}',
            '-device', 'qemu-xhci,id=xhci',
            '-drive', f'if=none,id=stick,format=raw,file={disk}',
            '-device', 'usb-storage,drive=stick,removable=on']


def canonical(path):
    path = Path(path)
    if (not path.is_absolute() or path != path.resolve() or
            path.is_relative_to('/dev') or any(c in str(path) for c in ',\n\r\0')):
        raise ValueError('only canonical paths outside /dev are accepted')
    return path


def regular(path):
    path = canonical(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('only unaliased regular files are accepted')
    return path


def fresh_file(path, size=0):
    path = canonical(path)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.truncate(size)
    return path


def expected_iso_digest():
    value = os.environ.get('GRAVESTONE_TEST_ISO_SHA256', '')
    if re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('explicit 64 lowercase hex SHA-256 pin required')
    return value


if __name__ == '__main__':
    if len(sys.argv) != 1:
        raise SystemExit('no path arguments accepted; use only disposable container /input/release.iso')
    run()
