#!/bin/bash
# ==========================================================================
# MyTellPBX theme installer for Issabel 5
# Installs/updates the Tabler-based MyTellPBX theme and activates it.
# Usage:    bash install-theme.sh [source_dir]
# Default source dir: the directory containing this script
# ==========================================================================
set -euo pipefail

SRC_DIR="${1:-$(cd "$(dirname "$0")" && pwd)}"
DEST_DIR="/var/www/html/themes/mytellpbx"
THEME_NAME="mytellpbx"

if [ ! -f "$SRC_DIR/themesetup.php" ] || [ ! -d "$SRC_DIR/_common" ]; then
    echo "ERROR: $SRC_DIR does not look like a MyTellPBX theme directory" >&2
    exit 1
fi

if [ ! -d /var/www/html/themes ] || [ ! -f /var/www/html/index.php ]; then
    echo "ERROR: Issabel 5 web tree not found at /var/www/html" >&2
    exit 1
fi

# Preserve owners/permissions of an existing install
if [ -d "$DEST_DIR" ]; then
    tar -C "$DEST_DIR" -cf /tmp/mytellpbx-theme-prev.tgz . 2>/dev/null || true
fi

echo "Installing theme files to $DEST_DIR ..."
mkdir -p "$DEST_DIR"
cp -a "$SRC_DIR"/. "$DEST_DIR"/

chown -R asterisk:asterisk "$DEST_DIR"
find "$DEST_DIR" -type d -exec chmod 755 {} +
find "$DEST_DIR" -type f -exec chmod 644 {} +

# Optional static extras: e.g. DataTables English language files referenced
# by some upstream report modules but missing from them. Files are only
# added when the module directory exists and the file is not already there,
# so upstream files are never overwritten.
if [ -d "$SRC_DIR/extras" ]; then
    echo "Installing optional module extras ..."
    cd "$SRC_DIR/extras"
    find . -type f | while read -r rel; do
        rel="${rel#./}"
        target="/var/www/html/modules/$rel"
        if [ ! -f "$target" ] && [ -d "$(dirname "$target")" ]; then
            cp "$SRC_DIR/extras/$rel" "$target"
            chown asterisk:asterisk "$target"
            chmod 644 "$target"
            echo "  added $target"
        fi
    done
    cd "$SRC_DIR"
fi

echo "Activating theme in framework settings ..."
php <<'PHP'
<?php
$db = new SQLite3('/var/www/db/settings.db');
if (!$db) { fwrite(STDERR, "cannot open settings.db\n"); exit(1); }
$db->exec("DELETE FROM settings WHERE key = 'theme'");
$db->exec("INSERT INTO settings (key, value) VALUES ('theme', 'mytellpbx')");
$row = $db->querySingle("SELECT value FROM settings WHERE key = 'theme'");
echo "active theme: " . $row . PHP_EOL;
PHP

if systemctl is-active --quiet httpd; then
    systemctl reload httpd
    echo "httpd reloaded"
fi

echo "MyTellPBX theme installed and activated."
echo "Open the panel and hard-refresh (Ctrl+Shift+R) to clear cached CSS."
