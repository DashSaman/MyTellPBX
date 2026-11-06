#!/bin/bash
# ==========================================================================
# Build the MyTellPBX installer bundle (mytelpbx-bundle-<ver>.tgz).
#
# Assembles an explicit allowlist of files into a staging directory with a
# single top-level folder, generates SHA256SUMS and manifest.json, then
# creates the tarball. Prints the archive SHA-256 on success — that value
# must be embedded in install-mytellpbx.sh (MYTELLPBX_BUNDLE_SHA256).
#
# Usage:  bash scripts/build-installer-bundle.sh [repo-root]
# Default repo-root: parent directory of this script.
# ==========================================================================
set -euo pipefail

REPO_ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
VERSION="$(cat "${REPO_ROOT}/VERSION" | tr -d '[:space:]')"
BUNDLE_NAME="mytelpbx-bundle-${VERSION}"
STAGE="$(mktemp -d)/${BUNDLE_NAME}"
OUT_DIR="${REPO_ROOT}/dist"
OUT_TGZ="${OUT_DIR}/${BUNDLE_NAME}.tgz"

mkdir -p "${STAGE}" "${OUT_DIR}"

# ---- explicit allowlist (relative to repo root) ---------------------------
copy_path() {
    local rel="$1"
    local src="${REPO_ROOT}/${rel}" dst="${STAGE}/${rel}"
    if [ -e "${src}" ]; then
        mkdir -p "$(dirname "${dst}")"
        cp -a "${src}" "${dst}"
    else
        echo "MISSING allowlist entry: ${rel}" >&2
        exit 1
    fi
}

copy_path "installer/packages/rocky8-stage1.txt"
copy_path "installer/packages/rocky8-stage2-asterisk20.txt"
copy_path "installer/repos/mytelpbx-base.repo.in"
copy_path "installer/payload/lang/fa.lang"
copy_path "installer/payload/admin/assets/mytel/skin.css"
copy_path "installer/payload/admin/assets/mytel/sub.js"
copy_path "installer/payload/admin/assets/mytel/fonts/vazirmatn-regular.woff"
copy_path "installer/payload/admin/assets/mytel/fonts/vazirmatn-regular.woff2"
copy_path "admin-theme/patch-admin-theme.py"
copy_path "admin-theme/patch-debrand.py"
copy_path "admin-theme/mt-admin-dark.css"
copy_path "admin-fixes/fix-apply-config.py"
copy_path "THIRD_PARTY_NOTICES.md"
copy_path "theme/THIRD-PARTY-LICENSES.txt"

# theme/ tree (whole tree minus local caches; source of truth for the panel)
mkdir -p "${STAGE}/theme"
tar -C "${REPO_ROOT}/theme" \
    --exclude='./cache' \
    --exclude='*.tplc' \
    -cf - . | tar -C "${STAGE}/theme" -xf -

# ---- integrity manifests ---------------------------------------------------
(
    cd "${STAGE}"
    find . -type f ! -name SHA256SUMS ! -name manifest.json -print0 \
        | sort -z | xargs -0 sha256sum > SHA256SUMS
)

file_count=$(wc -l < "${STAGE}/SHA256SUMS" | tr -d ' ')
# Rocky minimal ships only platform-python; accept either interpreter
PY_BIN="$(command -v python3 || true)"
[ -n "${PY_BIN}" ] || PY_BIN="/usr/libexec/platform-python"
[ -x "${PY_BIN}" ] || { echo "no python3 interpreter found" >&2; exit 1; }
"${PY_BIN}" - "$STAGE" "$VERSION" "$file_count" <<'PY'
import datetime, hashlib, json, pathlib, sys
stage, version, count = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
files = {}
for line in (stage / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    files[name[2:] if name.startswith('./') else name] = {
        'sha256': digest,
        'bytes': (stage / name).stat().st_size,
    }
manifest = {
    'schema': 'mytelpbx-bundle/1',
    'name': f'mytelpbx-bundle-{version}',
    'version': version,
    'platform': 'rocky-8.10-x86_64',
    'asterisk': '20',
    'created_utc': datetime.datetime.utcnow().isoformat() + 'Z',
    'file_count': count,
    'patch_inputs': {
        'admin_header_anchor': "$html .= '<head>';",
        'subjs_marker': 'MyTellPBX v7.3.5: debrand IssabelPBX',
        'skinjs_marker': 'MyTellPBX v7.3.0 admin dark theme (marker)',
    },
    'files': files,
}
(stage / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
print('manifest.json written')
PY

rm -f "${OUT_TGZ}"
tar -C "$(dirname "${STAGE}")" -czf "${OUT_TGZ}" "${BUNDLE_NAME}"

echo "Bundle: ${OUT_TGZ}"
echo "Size:   $(du -h "${OUT_TGZ}" | cut -f1)"
echo "SHA256: $(sha256sum "${OUT_TGZ}" | awk '{print $1}')"
