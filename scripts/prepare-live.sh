#!/bin/bash
# Stage into a fresh directory. Never delete a caller's existing build.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $# == 1 ]] || { printf 'Usage: %s EMPTY_BUILD_DIR\n' "$0" >&2; exit 2; }
build=$(realpath -m -- "$1")
case "$build/" in
    "$repo/"*) printf 'Build directory must be outside the source repository\n' >&2; exit 2 ;;
esac
mkdir -p -- "$build"
[[ -z $(ls -A -- "$build") ]] || { printf 'Build directory must be empty: %s\n' "$build" >&2; exit 2; }
for required in app content; do
    [[ -d "$repo/$required" ]] || { printf 'Missing source: %s\n' "$required" >&2; exit 2; }
done
cp -a -- "$repo/live/auto" "$repo/live/config" "$build/"
target="$build/config/includes.chroot/opt/gravestone"
mkdir -p -- "$target"
# Include the repository sources/docs, never history, build output or caches.
tar -C "$repo" --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.venv' --exclude='dist' --exclude='build' --exclude='.pytest_cache' \
    --exclude='.github' --exclude='live' --exclude='scripts' --exclude='tests' \
    -cf - . | tar -C "$target" -xf -
chmod 0755 "$build/auto/config"
printf 'Staged live build in %s\n' "$build"
