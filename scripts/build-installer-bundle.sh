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
REPO_ROOT="$(cd "${REPO_ROOT}" && pwd -P)"
command -v git >/dev/null 2>&1 || { echo 'Git is required to build reviewed tracked sources.' >&2; exit 1; }
git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { echo 'Build from a clean Git checkout.' >&2; exit 1; }
[ -z "$(git -C "${REPO_ROOT}" status --porcelain=v1 --untracked-files=all)" ] \
    || { echo 'Build requires a clean Git checkout; commit reviewed source changes first.' >&2; exit 1; }
VERSION="$(cat "${REPO_ROOT}/VERSION" | tr -d '[:space:]')"
[[ "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Invalid release version.' >&2; exit 1; }
BUNDLE_NAME="mytelpbx-bundle-${VERSION}"
STAGE_ROOT="$(mktemp -d)"
trap 'rm -rf -- "${STAGE_ROOT}"' EXIT
STAGE="${STAGE_ROOT}/${BUNDLE_NAME}"
OUT_DIR="${REPO_ROOT}/dist"
OUT_TGZ="${OUT_DIR}/${BUNDLE_NAME}.tgz"

mkdir -p "${STAGE}" "${OUT_DIR}"

# ---- explicit allowlist (relative to repo root) ---------------------------
copy_path() {
    local rel="$1"
    local src="${REPO_ROOT}/${rel}" dst="${STAGE}/${rel}"
    git -C "${REPO_ROOT}" ls-files --error-unmatch -- "${rel}" >/dev/null 2>&1 \
        || { echo "Untracked allowlist input: ${rel}" >&2; exit 1; }
    if [ -f "${src}" ] && [ ! -L "${src}" ]; then
        mkdir -p "$(dirname "${dst}")"
        # A clean worktree may still use CRLF/smudge-filter output. Ship exact
        # committed bytes, not a platform-dependent presentation of those bytes.
        git -C "${REPO_ROOT}" cat-file blob "HEAD:${rel}" >"${dst}"
        local mode
        mode="$(git -C "${REPO_ROOT}" ls-files -s -- "${rel}" | cut -d ' ' -f1)"
        if [ "${mode}" = "100755" ]; then chmod 755 "${dst}"; else chmod 644 "${dst}"; fi
    else
        echo "MISSING allowlist entry: ${rel}" >&2
        exit 1
    fi
}

copy_path "installer/packages/rocky8-stage1.txt"
copy_path "installer/packages/rocky8-stage2-asterisk20.txt"
copy_path "installer/repos/mytelpbx-base.repo.in"
copy_path "installer/payload/lang/fa.lang"
copy_path "installer/install-myteldesk.py"
copy_path "installer/myteldesk-release.json"
copy_path "modules/mytellpbxopdesk/launcher-access.php"
copy_path "modules/mytellpbxopdesk/index.php"
copy_path "installer/payload/admin/assets/mytel/skin.css"
copy_path "installer/payload/admin/assets/mytel/sub.js"
copy_path "installer/payload/admin/assets/mytel/fonts/vazirmatn-regular.woff"
copy_path "installer/payload/admin/assets/mytel/fonts/vazirmatn-regular.woff2"
copy_path "admin-theme/patch-admin-theme.py"
copy_path "admin-theme/patch-debrand.py"
copy_path "admin-theme/mt-admin-dark.css"
copy_path "admin-theme/workspace.js"
copy_path "admin-theme/workspace.css"
copy_path "admin-theme/feedback.js"
copy_path "admin-theme/save.js"
copy_path "admin-theme/apply.js"
copy_path "admin-theme/apply.css"
copy_path "admin-fixes/patch-apply-backend.py"
copy_path "admin-fixes/reload-guard.php"
copy_path "admin-fixes/patch-calendar.py"
copy_path "admin-fixes/patch-submit.py"
copy_path "admin-fixes/sip-save-transaction.php"
copy_path "admin-fixes/install-scoped-repairs.py"
copy_path "admin-fixes/fix-apply-config.py"
copy_path "THIRD_PARTY_NOTICES.md"
copy_path "LICENSE"
copy_path "theme/THIRD-PARTY-LICENSES.txt"

# Theme inputs come from the reviewed Git index, never ignored local secrets,
# screenshots, cache files or unrelated operator material in the worktree.
mkdir -p "${STAGE}/theme"
while IFS= read -r -d '' rel; do
    case "${rel}" in
        */cache/*|*/__pycache__/*|*.tplc|*.pyc|*/.env|*/.env.*|*.pem|*.key|*.p8|*.p12|*.pfx|*.db|*.sqlite*|*.log|*.bak*)
            echo "Private/generated theme input refused: ${rel}" >&2; exit 1 ;;
    esac
    copy_path "${rel}"
done < <(git -C "${REPO_ROOT}" ls-files -z -- theme/)

# ---- integrity manifests ---------------------------------------------------
(
    cd "${STAGE}"
    find . -type f ! -name SHA256SUMS ! -name manifest.json -print0 \
        | sort -z | xargs -0 sha256sum --text > SHA256SUMS
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
