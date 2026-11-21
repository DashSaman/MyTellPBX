#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd -P)
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
/usr/libexec/platform-python - "$here" "$work" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys
here, work = map(Path, sys.argv[1:])
manifest = json.loads((here / 'build-deps.json').read_text())
key = here.parent.parent / 'installer/vendor-native/keys/issabel.asc'
policy = manifest['rpm_signing_key']
if hashlib.sha256(key.read_bytes()).hexdigest() != policy['sha256']:
    raise SystemExit('Unexpected signing key for build dependencies')
subprocess.run(['rpm', '--import', str(key)], check=True)
for package in manifest['packages']:
    rpm = work / package['filename']
    for url in package['urls']:
        got = subprocess.run(['curl', '--disable', '-fsSL', '--connect-timeout', '8',
                              '--max-time', '35', '-o', str(rpm), url])
        if got.returncode == 0 and rpm.stat().st_size == package['bytes'] and hashlib.sha256(rpm.read_bytes()).hexdigest() == package['sha256']:
            break
    else:
        raise SystemExit('Could not obtain verified ' + rpm.name)
    result = subprocess.check_output(['rpmkeys', '-Kv', str(rpm)]).lower()
    if policy['rpm_key_id'].lower().encode() + b': ok' not in result:
        raise SystemExit('Expected the recorded signer for ' + rpm.name)
PY
dnf -y --setopt=localpkg_gpgcheck=1 install "$work"/*.rpm
