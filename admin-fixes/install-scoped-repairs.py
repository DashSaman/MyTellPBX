#!/usr/bin/env python3
"""Installer hook. Validate every patch and PHP file before writing any source.

Production incremental updates use scripts/ui/rollout.py and its review receipt.
This hook is for the explicitly invoked complete installer, with private backups.
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--web-root', type=Path, default=Path('/var/www/html'))
    parser.add_argument('--backup-root', type=Path, default=Path('/var/backups/mytellpbx/repairs-v752'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root, backup = args.web_root.resolve(), args.backup_root.resolve()
    if backup == root or root in backup.parents:
        raise ValueError('Backups must be outside the served root')
    theme = load('theme_patcher', SOURCE.parent / 'admin-theme/patch-admin-theme.py')
    changes = load('apply_patcher', SOURCE / 'patch-apply-backend.py').plan(root / 'admin')
    changes.update(load('calendar_patcher', SOURCE / 'patch-calendar.py').plan(
        root / 'modules/calendar', root / 'modules/calendar/scenarios/rest/CalendarEvent.class.php'))
    # Clean up the old installer global toast after its compatibility patch.
    sub = root / 'admin/assets/mytel/sub.js'
    changes[sub] = theme.transform_subtitle(sub.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='mytell-php-check-') as work:
        for i, (path, content) in enumerate(changes.items()):
            if path.is_symlink() or root not in path.resolve().parents:
                raise ValueError('Unsafe installed patch path: ' + str(path))
            if path.suffix == '.php':
                staged = Path(work) / (str(i) + '.php')
                staged.write_text(content, encoding='utf-8')
                subprocess.check_call(['php', '-l', str(staged)])
    for path, content in changes.items():
        if not args.check:
            theme.write_atomic(path, content, backup)
        print('CHECKED' if args.check else 'UPDATED', path)


if __name__ == '__main__':
    main()
