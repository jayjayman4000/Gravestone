#!/usr/bin/env python3
"""Bounded OVMF loader-discovery gate; regular files only, no mounts/devices.

Requires bookworm live-build, grub-efi-amd64-bin, mtools, dosfstools, fdisk,
qemu-system-x86 and ovmf. This checks discovery/config loading, NOT Linux or
persistence. --loader tests unchanged release bytes against the same fixtures.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, timeout=30, **kwargs)


def successful_boot(log, returncode, timed_out):
    return (returncode == 0 and not timed_out
            and b'GRAVESTONE_EFI_FAT_OK root=hd' in log
            and b'error:' not in log)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper', type=Path, default=Path('/usr/lib/live/build/efi-image'))
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--loader', type=Path)
    source.add_argument('--iso', type=Path, help='Audit actual shipped loader and GRUB tree')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    with tempfile.TemporaryDirectory(prefix='gravestone-efi-') as temporary:
        work = Path(temporary)
        env = dict(os.environ, SOURCE_DATE_EPOCH='1793404800',
                   PATH=os.environ['PATH'] + ':/usr/lib/live/build')
        tree = work / 'generated'
        loader = work / 'bootx64.efi'
        if args.iso:
            (tree / 'boot').mkdir(parents=True)
            run(['xorriso', '-osirrox', 'on', '-indev', args.iso.resolve(),
                 '-extract', '/EFI/boot/bootx64.efi', loader,
                 '-extract', '/boot/grub', tree / 'boot/grub'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            run(['sh', args.helper.resolve(), tree, 'x86_64-efi', 'x64', 'debian-live/amd64'],
                cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            run(['mcopy', '-i', tree / 'efi.img', '::efi/boot/bootx64.efi', loader])
        if args.loader:
            shutil.copyfile(args.loader, loader)
        shutil.copyfile(loader, args.output / 'bootx64.efi')
        rendered = tree / 'boot/grub/x86_64-efi/grub.cfg'
        shutil.copyfile(rendered, args.output / 'platform-grub.cfg')
        # Inspect real PE mods/ELF .modname records, not incidental strings.
        binary = loader.read_bytes()
        pe = struct.unpack_from('<I', binary, 60)[0]
        assert binary[pe:pe + 4] == b'PE\0\0'
        count = struct.unpack_from('<H', binary, pe + 6)[0]
        optional = struct.unpack_from('<H', binary, pe + 20)[0]
        sections = pe + 24 + optional
        names = []
        for index in range(count):
            section = sections + index * 40
            if binary[section:section + 8].rstrip(b'\0') != b'mods':
                continue
            offset = struct.unpack_from('<I', binary, section + 20)[0]
            magic, _, start, size = struct.unpack_from('<IIQQ', binary, offset)
            assert magic == 0x676d696d
            position = offset + start
            while position < offset + size:
                kind, length = struct.unpack_from('<II', binary, position)
                assert length >= 8 and position + length <= offset + size
                elf = binary[position + 8:position + length]
                if kind == 0:
                    assert elf[:5] == b'\x7fELF\x02'
                    shoff = struct.unpack_from('<Q', elf, 40)[0]
                    entsize, number, strings_index = struct.unpack_from('<HHH', elf, 58)
                    header = struct.unpack_from('<IIQQQQIIQQ', elf, shoff + strings_index * entsize)
                    strings = elf[header[4]:header[4] + header[5]]
                    for i in range(number):
                        header = struct.unpack_from('<IIQQQQIIQQ', elf, shoff + i * entsize)
                        name = strings[header[0]:].split(b'\0')[0].decode()
                        if name == '.modname':
                            names.append(elf[header[4]:header[4] + header[5]].rstrip(b'\0').decode())
                position += length
        runtime_preserved = all(value in rendered.read_text() for value in ('$grub_platform', '$lockdown'))
        module_contract = {'part_gpt', 'part_msdos'} <= set(names)
        marker = work / 'info'
        marker.write_text('Gravestone extracted FAT fixture\n')
        config = tree / 'boot/grub/grub.cfg'
        config.write_text('serial --unit=0 --speed=115200\nterminal_output serial\n'
                          'echo GRAVESTONE_EFI_FAT_OK root=$root platform=$grub_platform\nhalt\n')
        for table, partition_type in [('gpt', 'U'), ('dos', 'ef')]:
            disk = work / (table + '.img')
            with disk.open('xb') as stream:
                stream.truncate(96 * 1024 * 1024)
            layout = f'label: {table}\nstart=2048, size=190464, type={partition_type}\n'
            run(['sfdisk', disk], input=layout.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            fat = work / (table + '.fat')
            run(['mkfs.vfat', '-F', '32', '-C', fat, '95232'], stdout=subprocess.PIPE)
            for directory in ['::EFI', '::EFI/BOOT', '::.disk', '::boot']:
                run(['mmd', '-i', fat, directory])
            run(['mcopy', '-i', fat, loader, '::EFI/BOOT/BOOTX64.EFI'])
            run(['mcopy', '-i', fat, marker, '::.disk/info'])
            run(['mcopy', '-s', '-i', fat, tree / 'boot/grub', '::boot/'])
            # Assert the marker bytes are genuinely on the FAT filesystem.
            found = subprocess.check_output(['mtype', '-i', str(fat), '::.disk/info'], timeout=10)
            assert found == marker.read_bytes()
            with disk.open('r+b') as destination, fat.open('rb') as source:
                destination.seek(2048 * 512)
                shutil.copyfileobj(source, destination)
            vars_file = work / (table + '-vars.fd')
            shutil.copyfile('/usr/share/OVMF/OVMF_VARS.fd', vars_file)
            command = ['qemu-system-x86_64', '-accel', 'tcg', '-m', '384', '-smp', '1',
                       '-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE.fd',
                       '-drive', f'if=pflash,format=raw,file={vars_file}',
                       '-drive', f'if=none,id=stick,format=raw,snapshot=on,file={disk}',
                       '-device', 'qemu-xhci', '-device', 'usb-storage,drive=stick,removable=on',
                       '-nic', 'none', '-nographic', '-monitor', 'none', '-no-reboot']
            timed_out = False
            try:
                boot = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=40)
                log, returncode = boot.stdout, boot.returncode
            except subprocess.TimeoutExpired as exc:
                log, returncode, timed_out = exc.stdout or b'', None, True
            (args.output / (table + '-serial.log')).write_bytes(log)
            passed = successful_boot(log, returncode, timed_out)
            results.append(dict(table=table, passed=passed, marker_present=True,
                                returncode=returncode, timed_out=timed_out, command=command))
            print(json.dumps(results[-1]), flush=True)
        report = dict(loader_sha256=hashlib.sha256(loader.read_bytes()).hexdigest(),
                      helper_sha256=hashlib.sha256(args.helper.read_bytes()).hexdigest(),
                      embedded_modules=names, runtime_variables_preserved=runtime_preserved,
                      module_contract=module_contract,
                      scope='UEFI extracted FAT discovery only; no kernel/persistence', results=results)
        (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if module_contract and runtime_preserved and all(item['passed'] for item in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
