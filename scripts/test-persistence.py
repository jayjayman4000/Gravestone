#!/usr/bin/env python3
"""Offline disposable-VM acceptance; never accepts a host disk or mounts one."""
import os
import base64
import hashlib
import json
import re
import secrets
import socket
import subprocess
import time
from pathlib import Path


def create_scratch(root):
    root = Path(root)
    if root.is_symlink() or root.resolve() != root.absolute() or root.resolve().is_relative_to('/dev'):
        raise ValueError('scratch directory must be canonical, not a device or symlink')
    disk = root / 'persistence.raw'
    fd = os.open(disk, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.truncate(256 * 1024 * 1024)
    return disk


def vm_command(iso, disk, root):
    for path in (iso, disk):
        path = Path(path)
        if (path.is_symlink() or not path.is_file() or
                path.absolute() != path.resolve() or path.resolve().is_relative_to('/dev') or
                ',' in str(path)):
            raise ValueError('only canonical regular files are accepted')
    return ['qemu-system-x86_64', '-accel', 'tcg', '-m', '2048', '-smp', '1',
            '-nic', 'none', '-display', 'none', '-no-reboot',
            '-serial', f'unix:{root}/serial.sock,server=on,wait=off',
            '-kernel', str(root / 'vmlinuz'), '-initrd', str(root / 'initrd.img'),
            '-append', 'boot=live components live-media=removable username=user hostname=gravestone '
            'persistence persistence-media=removable-usb persistence-storage=filesystem '
            'persistence-label=persistence swap=false noswap ip=frommedia noeject '
            'console=tty0 console=ttyS0,115200 systemd.debug_shell=ttyS0 '
            'systemd.mask=serial-getty@ttyS0.service',
            '-drive', f'file={iso},format=raw,media=cdrom,readonly=on',
            '-device', 'qemu-xhci,id=xhci', '-drive', f'file={disk},format=raw,if=none,id=persist',
            '-device', 'usb-storage,drive=persist,removable=true']


def guest_program(phase, token):
    first = token + ': boot one\nUTF-8: 雪\n<literal & text>\n'
    second = first + 'Updated during boot two\n'
    expected = ['', first, second][phase - 1]
    target = first if phase == 1 else second
    return f"""
import json, pathlib, subprocess, urllib.request
base = 'http://127.0.0.1:8766'
expected = {expected!r}
target = {target!r}
request = lambda: json.load(urllib.request.urlopen(base + '/api/notes', timeout=10))['text']
before = request()
assert before == expected, ('notebook mismatch', before, expected)
if {phase} < 3:
    req = urllib.request.Request(base + '/api/notes', json.dumps({{'text': target}}).encode(), headers={{'Origin': base, 'Content-Type': 'application/json'}}, method='POST')
    assert json.load(urllib.request.urlopen(req, timeout=10)) == {{'text': target}}
after = request()
assert after == target
mounts = pathlib.Path('/proc/self/mountinfo').read_text()
assert ' /home ' in mounts and '/live/persistence/' in mounts, mounts
record = {{'phase': {phase}, 'boot_id': pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'before': before, 'after': after, 'mountinfo': mounts, 'cmdline': pathlib.Path('/proc/cmdline').read_text(), 'lsblk': subprocess.check_output(['lsblk', '-o', 'NAME,TYPE,TRAN,RM,FSTYPE,LABEL,MOUNTPOINTS'], text=True)}}
print('PERSISTENCE_RESULT=' + json.dumps(record), flush=True)
"""


def expected_iso_digest():
    digest = os.environ.get('GRAVESTONE_TEST_ISO_SHA256',
                            '63be2439540ce02b5821791ea93e4cda5669f2b8adcd7a7d3d96fe921accc001')
    if re.fullmatch(r'[0-9a-f]{64}', digest) is None:
        raise ValueError('expected ISO pin must be exactly 64 lowercase SHA-256 hex characters')
    return digest


def run():
    # The CLI takes no disk/path parameters. Only the isolated Docker filesystem is writable.
    if not Path('/.dockerenv').is_file():
        raise RuntimeError('run only in the documented disposable unprivileged Docker container')
    iso = Path('/input/release.iso')
    if iso.is_symlink() or not iso.is_file():
        raise ValueError('input must be a regular ISO file')
    with iso.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert digest == expected_iso_digest(), digest
    root = Path('/evidence')
    root.mkdir(mode=0o700)  # Refuse reuse; never overwrite another test.
    result = {'iso_sha256': digest, 'passed': False, 'boots': [], 'method': 'direct-kernel; VM-only debug serial shell; no firmware claim'}
    try:
        disk = create_scratch(root)
        seed = root / 'seed'
        seed.mkdir()
        (seed / 'persistence.conf').write_text('/home union\n')
        subprocess.run(['mkfs.ext4', '-F', '-L', 'persistence', '-d', str(seed), str(disk)], check=True)
        for name in ('vmlinuz', 'initrd.img'):
            subprocess.run(['xorriso', '-osirrox', 'on', '-indev', str(iso), '-extract', '/live/' + name, str(root / name)], check=True)
        token = secrets.token_hex(16)
        result['token'] = token
        for phase in (1, 2, 3):
            serial = root / 'serial.sock'
            serial.unlink(missing_ok=True)
            command = vm_command(iso, disk, root)
            (root / f'boot-{phase}-command.json').write_text(json.dumps(command, indent=2))
            transcript = bytearray()
            with (root / f'boot-{phase}-qemu.log').open('wb') as errors:
                proc = subprocess.Popen(command, stdout=errors, stderr=errors)
                conn = socket.socket(socket.AF_UNIX)
                serial_eof = False
                try:
                    deadline = time.monotonic() + 300
                    while not serial.exists():
                        if proc.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError('QEMU failed before serial connection')
                        time.sleep(.1)
                    conn.connect(str(serial))
                    conn.settimeout(1)
                    sent = False
                    while time.monotonic() < deadline:
                        # Process exit does not consume bytes queued on its socket.
                        # Keep the original boot deadline while draining to EOF.
                        conn.settimeout(min(1, max(.001, deadline - time.monotonic())))
                        try:
                            data = conn.recv(65536)
                            serial_eof = not data
                        except socket.timeout:
                            data = b''
                        transcript.extend(data)
                        (root / f'boot-{phase}-serial.log').write_bytes(transcript)
                        if not sent and b'GRAVESTONE_SERVICE_READY' in transcript:
                            # base64 avoids quoting/terminal echo resembling the result marker.
                            payload = base64.b64encode(guest_program(phase, token).encode()).decode()
                            shell = f"python3 -c \"import base64;exec(base64.b64decode('{payload}'))\"; systemctl poweroff\n"
                            conn.sendall(shell.encode())
                            sent = True
                        if serial_eof:
                            if proc.poll() is not None:
                                break
                            time.sleep(min(.01, max(0, deadline - time.monotonic())))
                    if proc.poll() is None:
                        raise TimeoutError(f'boot {phase}: no clean poweroff within 300 seconds')
                    text = transcript.decode(errors='replace')
                    match = re.search(r'PERSISTENCE_RESULT=(\{[^\r\n]+\})', text)
                    if not match:
                        raise RuntimeError(f'boot {phase}: no API assertion result; inspect serial log')
                    record = json.loads(match.group(1))
                    record['qemu_exit'] = proc.returncode
                    record['clean_poweroff'] = 'Power down' in text and proc.returncode == 0
                    assert record['clean_poweroff'], 'clean kernel poweroff missing'
                    result['boots'].append(record)
                    (root / 'result.json').write_text(json.dumps(result, indent=2))
                    print(f'Boot {phase}: exact notebook API assertions and clean poweroff PASS', flush=True)
                except Exception:
                    # Capture the observed exit BEFORE any timeout cleanup kills it.
                    result['failed_boot'] = {
                        'phase': phase, 'qemu_exit': proc.poll(),
                        'serial_bytes': len(transcript), 'serial_eof': serial_eof,
                        'serial_tail': transcript[-2048:].decode(errors='replace'),
                    }
                    raise
                finally:
                    conn.close()
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait(timeout=15)
            with (root / f'boot-{phase}-fsck.log').open('w') as fsck_log:
                subprocess.run(['e2fsck', '-fn', str(disk)], stdout=fsck_log,
                               stderr=subprocess.STDOUT, check=True)
        assert len({boot['boot_id'] for boot in result['boots']}) == 3
        result['passed'] = True
    except Exception as exc:
        result['error'] = repr(exc)
        raise
    finally:
        (root / 'result.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    run()
