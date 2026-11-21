#!/usr/bin/env bash
# Build unsigned release candidates. Public signing keys and signed RPMs are
# checked separately by the release maintainer on a clean Rocky system.
set -euo pipefail
repo=$(cd -- "$(dirname -- "$0")/../.." && pwd -P)
spec="$repo/packaging/asterisk20/asterisk20.spec"
out=${1:?Provide an empty RPM build directory}
mkdir -p -- "$out"
out=$(cd -- "$out" && pwd -P)
if [[ -n $(ls -A -- "$out") ]]; then
    echo 'The RPM build directory must be empty.' >&2
    exit 2
fi
mkdir -p "$out"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
cp "$repo"/packaging/asterisk20/SOURCES/* "$out/SOURCES/"
cp "$spec" "$out/SPECS/"
while read -r digest url; do
    [[ $digest =~ ^[0-9a-f]{64}$ && $url == https://* ]] || exit 2
    file=${url##*/}
    [[ $file =~ ^[a-zA-Z0-9._-]+$ ]] || exit 2
    curl --proto '=https' --proto-redir '=https' -fsSL --retry 3 --connect-timeout 20 \
        "$url" -o "$out/SOURCES/$file"
    (cd "$out/SOURCES" && printf '%s  %s\n' "$digest" "$file" | sha256sum --check --status)
done < "$repo/packaging/asterisk20/source-downloads.sha256"
rpmbuild -ba --define "_topdir $out" "$out/SPECS/asterisk20.spec"
python3 "$out/SOURCES/package-layout.py" verify "$out/SOURCES/native-layout.tsv" "$out/RPMS"
