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
cd "$build"
# auto/config is the single source of lb config options.
lb config
lb build
name=gravestone-0.1.0-amd64.iso
shopt -s nullglob
images=(*.hybrid.iso *.iso)
# .hybrid.iso also matches *.iso; deduplicate before selecting.
mapfile -t images < <(printf '%s\n' "${images[@]}" | sort -u)
[[ ${#images[@]} == 1 && -s ${images[0]} ]] || { printf 'Expected exactly one built ISO\n' >&2; exit 1; }
size=$(stat -c %s "${images[0]}")
(( size <= 14000000000 )) || { printf 'ISO exceeds 14,000,000,000 bytes: %s\n' "$size" >&2; exit 1; }
cp -- "${images[0]}" "$out/$name"
cp -- binary/live/filesystem.packages "$out/filesystem.packages"
cd "$out"
sha256sum "$name" >"$name.sha256"
sha256sum -c "$name.sha256"
printf 'ISO size: %s bytes\n' "$size"
