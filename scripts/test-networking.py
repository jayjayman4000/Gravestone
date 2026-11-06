#!/usr/bin/env python3
"""Exact-ISO live-root networking/API acceptance, not firmware or graphical QA.

Run only in the workflow's network-none disposable container. QEMU's slirp
network reaches a loopback-only HTTP fixture in that container, not the Internet.
The root serial debug shell exists only in external QA kernel arguments.
"""
from pathlib import Path
import base64
import contextlib
import hashlib
import http.server
import json
import os
import re
import socket
import subprocess
import threading
import time


# One boot-through-kernel-poweroff budget. The retained 300s run completed
# import/offline checks but reached only poweroff.target before timing out.
# Allow the parser's 12 -> 40s increase plus 90s TCG shutdown headroom,
# rounded up (300 + 28 + 90 = 418). Never renew this deadline per phase.
NETWORK_TOTAL_SECONDS = 420


def pdf_bytes():
    # Synthetic QA text, explicitly not survival guidance or shipped content.
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    text = b'BT /F1 12 Tf 10 100 Td (Quasar networking QA fixture) Tj ET'
    objects.append(b'<< /Length ' + str(len(text)).encode() + b' >>\nstream\n' + text + b'\nendstream')
    raw, offsets = b'%PDF-1.4\n', []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(raw))
        raw += str(number).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
    start = len(raw)
    raw += b'xref\n0 6\n0000000000 65535 f \n'
    raw += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets)
    return raw + b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(start).encode() + b'\n%%EOF\n'


@contextlib.contextmanager
def fixture_server(port=8000):
    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(2)

        def do_GET(self):
            hits.append(self.path[:256])
            if len(hits) > 100:
                self.send_error(429)
                return
            if self.path != '/fixture.pdf':
                self.send_error(404)
                return
            raw = pdf_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format, *args):
            pass

    class FixtureServer(http.server.HTTPServer):
        hits: list[str]

    server = FixtureServer(('127.0.0.1', port), Handler)
    server.hits = hits
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def expected_iso_digest():
    digest = os.environ.get('GRAVESTONE_TEST_ISO_SHA256', '')
    if re.fullmatch('[0-9a-f]{64}', digest) is None:
        raise ValueError('explicit 64 lowercase hex ISO SHA-256 pin required')
    return digest


def vm_command(iso, root):
    iso, root = Path(iso), Path(root)
    for path in (iso, root):
        if (path.is_symlink() or path.absolute() != path.resolve() or
                path.resolve().is_relative_to('/dev') or
                any(c in str(path) for c in ',\n\r')):
            raise ValueError('only canonical paths without QEMU delimiters accepted')
    if not iso.is_file() or not root.is_dir():
        raise ValueError('ISO must be a regular file and scratch an existing directory')
    return ['qemu-system-x86_64', '-accel', 'tcg', '-m', '2048', '-smp', '1',
            '-netdev', 'user,id=acceptance,ipv6=off',
            '-device', 'e1000,netdev=acceptance,mac=52:54:00:12:34:56',
            '-display', 'none', '-no-reboot',
            '-serial', f'unix:{root}/serial.sock,server=on,wait=off',
            '-kernel', str(root / 'vmlinuz'), '-initrd', str(root / 'initrd.img'),
            '-append', 'boot=live components live-media=removable username=user hostname=gravestone '
            'swap=false noswap ip=frommedia noeject console=tty0 console=ttyS0,115200 '
            'systemd.debug_shell=ttyS0 systemd.mask=serial-getty@ttyS0.service',
            '-drive', f'file={iso},format=raw,media=cdrom,readonly=on']


# Standalone guest program: stdlib and the production image's existing tools only.
GUEST_SOURCE = r'''
import hashlib, json, os, pathlib, pwd, subprocess, time, urllib.request, urllib.error
BASE = 'http://127.0.0.1:8766'
FIXTURE = 'http://10.0.2.2:8000'
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def command(args, timeout=8):
    return subprocess.check_output(args, text=True, timeout=timeout).strip()


def state():
    return {'addresses': json.loads(command(['ip', '-j', 'address', 'show'])),
            'routes4': json.loads(command(['ip', '-j', '-4', 'route', 'show', 'table', 'all'])),
            'routes6': json.loads(command(['ip', '-j', '-6', 'route', 'show', 'table', 'all']))}


def assert_offline(value):
    for interface in value['addresses']:
        if interface['ifname'] == 'lo':
            continue
        for address in interface.get('addr_info', []):
            assert address['family'] != 'inet', value
            assert not (address['family'] == 'inet6' and address['scope'] == 'global'), value
    for family in ('routes4', 'routes6'):
        assert not any(route.get('dst') == 'default' for route in value[family]), value


def online_interface(value):
    for interface in value['addresses']:
        if any(a.get('local') == '10.0.2.15' for a in interface.get('addr_info', [])):
            if any(r.get('dst') == 'default' and r.get('gateway') == '10.0.2.2'
                   and r.get('dev') == interface['ifname'] for r in value['routes4']):
                return interface['ifname']
    return None


def bounded_wait(predicate, seconds=40):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.25)
    raise TimeoutError('guest network transition did not finish')


def get(url, timeout=8):
    with HTTP.open(url, timeout=timeout) as response:
        assert response.status == 200
        raw = response.read(2 * 1024 * 1024 + 1)
        assert len(raw) <= 2 * 1024 * 1024
        return raw


def cannot_download(path):
    try:
        get(FIXTURE + path, timeout=2)
    except (OSError, TimeoutError):
        return
    raise AssertionError('offline guest reached host fixture')


def helper(action):
    # Same unprivileged user and exact sudo-allowlisted command as native setup.
    subprocess.run(['/usr/sbin/runuser', '-u', 'user', '--', '/usr/bin/sudo', '-n',
                    '/usr/local/sbin/gravestone-network', action],
                   check=True, timeout=25)


def diagnostic_command(args, raw=None, timeout=8):
    # Pipes are essential: the SAME production worker sets RLIMIT_FSIZE=0.
    # Never redirect its stdout to an evidence file or loosen its limits.
    start = time.monotonic()
    result = {'returncode': None}
    try:
        proc = subprocess.run(args, input=raw, cwd='/opt/gravestone',
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        result.update(status='exited', returncode=proc.returncode,
                      stdout=proc.stdout, stderr=proc.stderr)
    except subprocess.TimeoutExpired as exc:
        result.update(status='timeout', stdout=exc.output or b'', stderr=exc.stderr or b'')
    except Exception as exc:
        result.update(status='unavailable', stdout=b'', stderr=type(exc).__name__.encode())
    result['elapsed_seconds'] = round(time.monotonic() - start, 3)
    for key in ('stdout', 'stderr'):
        value = result[key]
        result[key + '_truncated'] = len(value) > 4096
        result[key] = value[-4096:].decode('utf-8', errors='replace')
    return result


def import_document(request, raw):
    try:
        with HTTP.open(request, timeout=60) as response:
            assert response.status == 201
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Diagnostic only: no retry, acceptance marker or private-data API reads.
        record = {'http_status': exc.code}
        try:
            body = exc.read(4097)
            record.update(http_body=body[:4096].decode('utf-8', errors='replace'),
                          http_body_truncated=len(body) > 4096)
        except Exception as read_error:
            record['http_body_error'] = type(read_error).__name__
        user_python = ['/usr/sbin/runuser', '-u', 'user', '--', '/usr/bin/python3']
        record['worker'] = diagnostic_command(user_python + ['-m', 'app.personal_parser'],
                                               raw=raw, timeout=40)
        record['parser_module'] = diagnostic_command(user_python + ['-c',
            'try:\n import pypdf as parser\nexcept ImportError:\n import PyPDF2 as parser\n'
            'print(parser.__name__, parser.__version__, parser.__file__)'])
        record['systemctl'] = diagnostic_command(['systemctl', 'show', 'gravestone.service',
            '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result', '-p', 'ExecMainStatus',
            '-p', 'User', '-p', 'WorkingDirectory', '-p', 'MemoryCurrent', '-p', 'MemoryMax',
            '-p', 'TasksCurrent', '-p', 'TasksMax', '-p', 'LimitAS', '-p', 'LimitFSIZE'])
        record['journal'] = diagnostic_command(['journalctl', '-b', '-u', 'gravestone.service',
            '--no-pager', '-n', '40', '-o', 'short-monotonic'])
        print('IMPORT_DIAGNOSTIC=' + json.dumps(record, ensure_ascii=True), flush=True)
        raise


def main():
    nics = [p for p in pathlib.Path('/sys/class/net').iterdir()
            if (p / 'address').read_text().strip() == '52:54:00:12:34:56']
    assert len(nics) == 1, 'e1000 device absent'
    assert (nics[0] / 'device/driver').resolve().name == 'e1000'
    # Do not repair default state. Absence of a helper/offline feature must fail.
    before = state()
    assert_offline(before)
    cannot_download('/baseline.pdf')
    time.sleep(3)
    assert_offline(state())
    helper('online')
    interface = bounded_wait(lambda: online_interface(state()))
    online = state()
    dhcp = command(['/usr/bin/nmcli', '-g', 'DHCP4.OPTION', 'device', 'show', interface])
    assert 'dhcp_server_identifier' in dhcp and '10.0.2.2' in dhcp, dhcp
    raw = get(FIXTURE + '/fixture.pdf')
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256
    downloads = pathlib.Path('/home/user/Downloads')
    downloads.mkdir(exist_ok=True)
    target = downloads / 'network-acceptance.pdf'
    with target.open('xb') as stream:
        stream.write(raw)
    owner = pwd.getpwnam('user')
    os.chown(target, owner.pw_uid, owner.pw_gid)
    assert target.read_bytes() == raw
    request = urllib.request.Request(BASE + '/api/personal/import', target.read_bytes(),
        headers={'Origin': BASE, 'Content-Type': 'application/pdf',
                 'X-Personal-Rights': 'acknowledged', 'X-Document-Title': 'Networking QA fixture'},
        method='POST')
    document = import_document(request, raw)
    assert document['personal'] is True and document['sha256'] == EXPECTED_SHA256
    assert get(BASE + '/' + document['file']) == raw
    helper('offline')
    def is_offline():
        try:
            assert_offline(state())
            return True
        except AssertionError:
            return False
    bounded_wait(is_offline)
    cannot_download('/after-offline.pdf')
    after = state()
    assert_offline(after)
    assert get(BASE + '/' + document['file']) == raw
    library = json.loads(get(BASE + '/api/library'))
    assert any(d['id'] == document['id'] for d in library['documents'])
    results = json.loads(get(BASE + '/api/search?q=Quasar'))['results']
    assert any(r['id'] == document['id'] and r['page'] == 1 and
               'Quasar' in r['excerpt'] for r in results), results
    print('NETWORK_RESULT=' + json.dumps({'baseline': before, 'online': online,
        'offline': after, 'dhcp': dhcp, 'download_sha256': EXPECTED_SHA256,
        'import_id': document['id'], 'local_read_after_offline': True,
        'search_after_offline': True, 'graphical_browser_proved': False}), flush=True)


if __name__ == '__main__':
    main()
'''


def guest_program(digest):
    if re.fullmatch('[0-9a-f]{64}', digest) is None:
        raise ValueError('fixture digest must be lowercase SHA-256')
    return 'EXPECTED_SHA256 = ' + repr(digest) + '\n' + GUEST_SOURCE


def shell_upload(source):
    """Ack each short line; never overflow the serial TTY canonical buffer."""
    payload = base64.b64encode(source.encode()).decode()
    commands = [": > /run/gravestone-network-qa.b64"]
    commands.extend("printf %s '" + payload[i:i + 600] + "' >> /run/gravestone-network-qa.b64"
                    for i in range(0, len(payload), 600))
    lines = [command + f"; printf '\\nQA_CHUNK_{i}\\n'\n" for i, command in enumerate(commands)]
    lines.append('python3 -c "import base64;exec(compile(base64.b64decode(open(\'/run/gravestone-network-qa.b64\').read()),\'<network-qa>\',\'exec\'))"; systemctl poweroff\n')
    return lines


def collect_serial(proc, conn, deadline, source, log_path):
    """Drain through EOF, including bytes buffered after QEMU process exit."""
    transcript = bytearray()
    lines = shell_upload(source)
    next_line = 0
    with Path(log_path).open('wb') as log:
        while time.monotonic() < deadline:
            conn.settimeout(min(1, max(.001, deadline - time.monotonic())))
            try:
                data = conn.recv(65536)
            except socket.timeout:
                continue
            if not data:
                proc.wait(timeout=max(.001, deadline - time.monotonic()))
                return transcript.decode(errors='replace')
            log.write(data)
            log.flush()
            transcript.extend(data)
            if len(transcript) > 2 * 1024 * 1024:
                raise RuntimeError('serial evidence exceeded 2 MiB limit')
            text = bytes(transcript).replace(b'\r', b'')
            ready = (b'GRAVESTONE_SERVICE_READY' in text if next_line == 0 else
                     f'\nQA_CHUNK_{next_line - 1}\n'.encode() in text)
            if next_line < len(lines) and ready:
                conn.sendall(lines[next_line].encode())
                next_line += 1
    raise TimeoutError('networking boot did not power off before total deadline')


def validate_result(text, exit_code, hits, fixture_digest):
    matches = re.findall(r'^NETWORK_RESULT=(\{[^\r\n]+\})\r?$', text, re.MULTILINE)
    if len(matches) != 1 or exit_code != 0 or 'Power down' not in text:
        raise RuntimeError('one guest assertion result and clean kernel poweroff required')
    if hits != ['/fixture.pdf']:
        raise RuntimeError('fixture must see exactly one online download, no offline hits: ' + repr(hits))
    record = json.loads(matches[0])
    if (record.get('download_sha256') != fixture_digest or
            record.get('local_read_after_offline') is not True or
            record.get('search_after_offline') is not True or
            record.get('graphical_browser_proved') is not False):
        raise RuntimeError('guest did not prove exact downloaded/imported bytes and offline API reading/search')
    return record


def check_isolation(names, status):
    caps = re.search(r'^CapEff:\s*([0-9a-f]+)$', status, re.MULTILINE)
    if names != ['lo'] or caps is None or int(caps[1], 16) != 0 or 'NoNewPrivs:\t1' not in status:
        raise RuntimeError('network-none, cap-drop ALL and no-new-privileges required')


def run():
    # Fixed paths only, no host disk, mount, caller-provided command or network.
    if not __debug__:
        raise RuntimeError('assertions must remain enabled')
    if not Path('/.dockerenv').is_file():
        raise RuntimeError('run only in disposable QA Docker container')
    names = [line.split(':', 1)[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]]
    check_isolation(names, Path('/proc/self/status').read_text())
    iso = Path('/input/release.iso')
    pin = expected_iso_digest()
    if iso.is_symlink() or not iso.is_file() or iso.absolute() != iso.resolve():
        raise ValueError('input must be a canonical regular ISO')
    if not os.statvfs(iso).f_flag & os.ST_RDONLY:
        raise ValueError('ISO must be mounted read-only')
    def iso_digest():
        with iso.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    digest = iso_digest()
    if digest != pin:
        raise ValueError('input ISO digest differs from explicit pin')
    root = Path('/evidence')
    root.mkdir(mode=0o700)  # Exclusive scratch; refuse reuse.
    result = {'passed': False, 'iso_sha256': digest,
              'method': 'direct-kernel exact-ISO live-root, external serial debug shell',
              'graphical_browser_proved': False, 'firmware_proved': False}
    try:
        with (root / 'extract.log').open('wb') as log:
            for name in ('vmlinuz', 'initrd.img'):
                subprocess.run(['xorriso', '-osirrox', 'on', '-indev', str(iso),
                                '-extract', '/live/' + name, str(root / name)],
                               stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
        command = vm_command(iso, root)
        (root / 'command.json').write_text(json.dumps(command, indent=2))
        fixture_digest = hashlib.sha256(pdf_bytes()).hexdigest()
        with fixture_server() as fixture, (root / 'qemu.log').open('wb') as log:
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            conn = socket.socket(socket.AF_UNIX)
            try:
                deadline = time.monotonic() + NETWORK_TOTAL_SECONDS
                serial = root / 'serial.sock'
                while not serial.exists():
                    if proc.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError('QEMU failed before serial connection')
                    time.sleep(.1)
                conn.settimeout(min(2, max(.001, deadline - time.monotonic())))
                conn.connect(str(serial))
                text = collect_serial(proc, conn, deadline, guest_program(fixture_digest), root / 'serial.log')
                result['guest'] = validate_result(text, proc.returncode, fixture.hits, fixture_digest)
                result['clean_poweroff'] = True
            finally:
                result['qemu_observed_exit'] = proc.poll()
                result['fixture_hits'] = list(fixture.hits)
                conn.close()
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
    except Exception as exc:
        result['error'] = repr(exc)
        raise
    finally:
        try:
            result['iso_sha256_after'] = iso_digest()
            if result['iso_sha256_after'] != pin:
                result['passed'] = False
                raise RuntimeError('ISO hash changed during acceptance')
            result['passed'] = result.get('clean_poweroff') is True and 'error' not in result
        finally:
            (root / 'result.json').write_text(json.dumps(result, indent=2))
    print('Exact-ISO networking, DHCP, download/import, offline API read/search and clean poweroff PASS', flush=True)


if __name__ == '__main__':
    run()
