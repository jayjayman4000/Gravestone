#!/bin/bash
# Run as root inside the privileged Debian bookworm build container.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
build=${1:-/build/work}
out=${2:-/out}
[[ $(id -u) == 0 ]] || { printf 'Root required inside build container\n' >&2; exit 2; }
command -v lb >/dev/null
mkdir -p "$out"
"$repo/scripts/prepare-live.sh" "$build"
# binary_grub-efi copies this helper into the chroot; reject upstream drift.
# Exercise real firmware before model download/compilation or lb build.
python3 "$repo/scripts/patch-live-build-efi.py"
python3 "$repo/scripts/test-efi-fat.py" --output "$out/efi-fat-bootstrap"
"$repo/scripts/prepare-ai.sh" "$build/config/includes.chroot/opt/gravestone"
# Test the exact packaged runtime/model, not an HTTP mock or a host prebuilt.
app_root="$build/config/includes.chroot/opt/gravestone"
cd "$repo"
GRAVESTONE_AI_PACKAGE_ROOT="$app_root" \
GRAVESTONE_AI_SERVER="$app_root/ai/runtime/llama-server" \
GRAVESTONE_AI_MODEL="$app_root/models/Qwen3-0.6B-Q8_0.gguf" \
GRAVESTONE_AI_EVIDENCE="$out/real-inference.json" \
    python3 -m unittest discover -s tests -p test_ai_package.py -v
# Exercise substantive source overviews against the exact packaged model too.
# Let compile/inference load decay; timeout fails the build, never skips the gate.
python3 -u "$repo/scripts/wait-for-host-load.py"
GRAVESTONE_OVERVIEW_REAL_ROOT="$app_root" \
GRAVESTONE_OVERVIEW_EVIDENCE="$out/overview-inference" \
    python3 -m unittest discover -s tests -p test_overview_real.py -v
cp -- "$app_root/ai/BUILD_PROVENANCE.json" "$out/AI_BUILD_PROVENANCE.json"
cd "$build"
# auto/config is the single source of lb config options.
lb config
lb build
name=gravestone-0.4.2-amd64.iso
shopt -s nullglob
images=(*.hybrid.iso *.iso)
# .hybrid.iso also matches *.iso; deduplicate before selecting.
mapfile -t images < <(printf '%s\n' "${images[@]}" | sort -u)
[[ ${#images[@]} == 1 && -s ${images[0]} ]] || { printf 'Expected exactly one built ISO\n' >&2; exit 1; }
size=$(stat -c %s "${images[0]}")
(( size <= 14000000000 )) || { printf 'ISO exceeds 14,000,000,000 bytes: %s\n' "$size" >&2; exit 1; }
cp -- "${images[0]}" "$out/$name"
# Repeat against the shipped executable/template, not just a helper sample.
python3 "$repo/scripts/test-efi-fat.py" --iso "$out/$name" --output "$out/efi-fat-shipped"
cp -- binary/live/filesystem.packages "$out/filesystem.packages"
cd "$out"
sha256sum "$name" >"$name.sha256"
sha256sum -c "$name.sha256"
printf 'ISO size: %s bytes\n' "$size"
