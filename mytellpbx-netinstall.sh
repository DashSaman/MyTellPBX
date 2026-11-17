#!/bin/bash
# Compatibility entry point; use the reviewed sibling release bootstrap.
set -u
set -o pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || exit 1
exec bash "$root/install-mytellpbx.sh" "$@"
