#!/usr/bin/env bash
set -euo pipefail

if (( $# != 3 )) || [[ ! $3 =~ ^[0-9]+$ ]]; then
    printf 'Usage: %s REPOSITORY_DIRECTORY OUTPUT.tar.gz REVISION_EPOCH\n' "$0" >&2
    exit 2
fi

source_tree=$(cd -- "$1" && pwd -P)
output_directory=$(cd -- "$(dirname -- "$2")" && pwd -P)
output="$output_directory/$(basename -- "$2")"
revision=$3
if [[ -e $output || -L $output ]]; then
    printf 'An archive already exists at the requested output path.\n' >&2
    exit 1
fi

export LC_ALL=C TZ=UTC
umask 077
scratch=$(mktemp -d -- "$output_directory/.mytel-vendor.XXXXXXXX")
trap 'rm -rf -- "$scratch"' EXIT
tree="$scratch/repository"
mkdir -p -- "$tree/Packages" "$tree/licenses"

shopt -s nullglob
packages=("$source_tree"/Packages/*.rpm)
notices=("$source_tree"/licenses/*.txt)
if (( ! ${#packages[@]} || ! ${#notices[@]} )); then
    printf 'Expected source Packages/*.rpm and licenses/*.txt.\n' >&2
    exit 1
fi

for member in "${packages[@]}" "${notices[@]}"; do
    directory=$(basename -- "$(dirname -- "$member")")
    filename=$(basename -- "$member")
    if [[ ! -f $member || -L $member || ! $filename =~ ^[A-Za-z0-9_][A-Za-z0-9+_.-]*$ ]]; then
        printf 'Invalid package or notice entry.\n' >&2
        exit 1
    fi
    install -m 0600 -- "$member" "$tree/$directory/$filename"
    touch -d "@$revision" -- "$tree/$directory/$filename"
done

createrepo_c --workers 1 --no-database --general-compress-type gz \
    --checksum sha256 --revision "$revision" --set-timestamp-to-revision "$tree"
tar -C "$tree" --sort=name --format=ustar --mtime="@$revision" \
    --owner=0 --group=0 --numeric-owner --mode='u+rwX,go+rX,go-w' \
    -cf - Packages licenses repodata | gzip -n -1 > "$scratch/asset.tar.gz"

# Use a same-filesystem hard link to avoid overwriting someone else's release.
ln -T -- "$scratch/asset.tar.gz" "$output"
sha256sum -- "$output"
