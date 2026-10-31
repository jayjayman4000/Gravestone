#!/usr/bin/env python3
"""Patch only the reviewed Debian bookworm live-build 1:20230502 helper.

binary_grub-efi copies this host helper into the build chroot. Fail closed on
upstream drift; do not replace the helper or alter the signed/Secure Boot path.
"""
import argparse
import hashlib
from pathlib import Path

UPSTREAM_SHA256 = '984becd0c48c7f9c5e20590ca8fc4a2a6a0c8bf583e13355efbf7f8dde31263e'


def patched(source):
    if hashlib.sha256(source).hexdigest() != UPSTREAM_SHA256:
        raise ValueError('Unreviewed live-build efi-image; refusing to patch')
    text = source.decode()
    text = text.replace('(echo "if [ x$grub_platform == xefi -a x$lockdown != xy ] ; then ";',
                        '{ echo \'if [ x$grub_platform == xefi -a x$lockdown != xy ] ; then \';')
    text = text.replace('echo "source /boot/grub/grub.cfg") >',
                        'echo "source /boot/grub/grub.cfg"; } >')
    return text.encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('helper', nargs='?', type=Path, default=Path('/usr/lib/live/build/efi-image'))
    args = parser.parse_args()
    try:
        replacement = patched(args.helper.read_bytes())
    except ValueError as exc:
        parser.exit(1, str(exc) + '\n')
    args.helper.write_bytes(replacement)
    print('Patched reviewed bookworm EFI helper: partition modules + runtime variables')


if __name__ == '__main__':
    main()
