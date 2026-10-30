#!/bin/bash
# Verify backend boot from extracted kernel, then whole BIOS and UEFI media.
set -euo pipefail
iso=$(realpath "${1:?Usage: smoke-iso.sh ISO [LOG_DIR]}")
logs=$(realpath -m "${2:-logs}")
mkdir -p "$logs"
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
xorriso -indev "$iso" -report_el_torito plain >"$logs/boot-catalog.log" 2>&1
# Extract only the kernel and initrd, not the entire compressed filesystem.
xorriso -osirrox on -indev "$iso" \
    -extract /live/vmlinuz "$work/vmlinuz" \
    -extract /live/initrd.img "$work/initrd.img" >"$logs/extract.log" 2>&1
# The attached ISO supplies /live/filesystem.squashfs to live-boot.
set +e
timeout 240 qemu-system-x86_64 -accel tcg -m 2048 -smp 2 \
    -display none -serial stdio -monitor none -nic none -no-reboot \
    -kernel "$work/vmlinuz" -initrd "$work/initrd.img" \
    -append 'boot=live components live-media=removable username=user hostname=gravestone noswap swap=false ip=frommedia nopersistence noeject console=ttyS0,115200 gravestone.smoke=1' \
    -cdrom "$iso" >"$logs/direct-kernel.log" 2>&1
status=$?
set -e
[[ $status == 0 ]] || { printf 'Direct-kernel VM exited %s\n' "$status" >&2; exit 1; }
grep -q 'GRAVESTONE_BOOT_OK' "$logs/direct-kernel.log"

firmware_boot() {
    local label=$1
    shift
    local log="$logs/$label.log"
    # These are the unchanged deliverable ISO, without the smoke shutdown flag.
    timeout 240 qemu-system-x86_64 -accel tcg -m 2048 -smp 2 \
        -display none -serial stdio -monitor none -nic none -no-reboot \
        -boot d -cdrom "$iso" "$@" >"$log" 2>&1 &
    local vm=$!
    while kill -0 "$vm" 2>/dev/null; do
        if grep -q 'GRAVESTONE_SERVICE_READY' "$log"; then
            kill "$vm" 2>/dev/null || true
            wait "$vm" || true
            printf '%s whole-ISO backend boot passed\n' "$label"
            return 0
        fi
        sleep 1
    done
    wait "$vm" || true
    printf '%s whole-ISO boot failed; see %s\n' "$label" "$log" >&2
    return 1
}
firmware_boot BIOS
ovmf=${OVMF_DIR:-/usr/share/OVMF}
cp "$ovmf/OVMF_VARS_4M.fd" "$work/OVMF_VARS.fd"
firmware_boot UEFI \
    -drive "if=pflash,format=raw,readonly=on,file=$ovmf/OVMF_CODE_4M.fd" \
    -drive "if=pflash,format=raw,file=$work/OVMF_VARS.fd"
printf 'All ISO smoke checks passed\n'
