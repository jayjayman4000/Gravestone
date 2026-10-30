#!/bin/sh
# Builder dependencies: build-essential cmake curl ca-certificates python3.
# No sudo/apt/root here: build in the target distribution's disposable builder.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/../ai/package.py" "$@"
