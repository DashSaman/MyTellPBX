#!/usr/bin/env python3
"""GPL-3.0-or-later: scoped, guarded Asternic 1.6.6 report direction repair.

No module installation, CDR/configuration changes or service actions. Existing
production sites use the separately reviewed report-only rollout profile.
"""
import argparse
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import tempfile
import xml.etree.ElementTree as ET

SOURCE = Path(__file__).resolve().parent
BEGIN = '// MYTEL_ASTERNIC_DIRECTION_V760_BEGIN'
END = '// MYTEL_ASTERNIC_DIRECTION_V760_END'
LOAD = BEGIN + "\nrequire_once(dirname(__FILE__) . '/mytell-direction.php');\n" + END
DIRECTION_COMMENTS = {
    '// اگر فقط خروجی واقعی می‌خواهیم (شماره‌هایی که با 9 شروع می‌شوند)': '// خروجی بر اساس ترانک واقعی مقصد تعیین می‌شود، مستقل از پیش‌شماره.',
    '// خروجی به بیرون: شماره مقصد با 9 شروع شود': '// خروجی به بیرون: ترانک مقصد یا هدف دقیق Dial به ترانک پیکربندی‌شده.',
    '// Outgoing: فقط شماره‌هایی که با 9 شروع می‌شوند': '// Outgoing: مسیر ترانک واقعی؛ بدون وابستگی به ارقام مقصد.',
    '// شماره تماس گیرنده عددی و بین 7 تا 11 رقم': '// ورودی بر اساس کانال ترانک مبدا تعیین می‌شود.',
    '// تماس ورودی از بیرون: شماره تماس‌گیرنده عددی 7 تا 11 رقم': '// تماس ورودی از بیرون: کانال مبدا متعلق به ترانک پیکربندی‌شده است.',
    '// Incoming: فقط شماره‌های بیرونی (7 تا 11 رقمی)': '// Incoming: مسیر ترانک مبدا؛ بدون وابستگی به قالب Caller ID.',
    '// فقط تماس‌های خروجی واقعی (مثلا شماره‌هایی که با 9 شروع می‌شوند)': '// فقط مسیرهای خروجی دارای شاهد واقعی ترانک، مستقل از پیش‌شماره.',
    '// داخلی‌ها سه‌رقمی‌اند، تماس بیرون شماره‌ی 7 تا 11 رقمی دارد.': '// شناسه تمام داخلی‌های پیکربندی‌شده از فهرست مجوزهای کاربر جداست.',
    '// این شرط می‌گوید: src فقط اعداد و طول 7 تا 11 رقم': '// مبدا ترانک، جهت ورودی را مشخص می‌کند؛ قالب شماره ملاک نیست.',
}


class DirectionPlan(dict):
    """Bind each candidate to the exact original bytes read during planning."""
    def __init__(self, changes, originals, directory_identity):
        super().__init__(changes)
        self.originals = originals
        self.directory_identity = directory_identity


def replace_exact(text, old, new, expected):
    if text.count(old) != expected:
        raise ValueError('Unknown Asternic direction source anchor')
    return text.replace(old, new)


def validate_result(text, expected):
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError('Incomplete Asternic direction marker')
    for direction, count in expected.items():
        call = "asternic_mytel_direction_sql($db, '" + direction + "')"
        if text.count(call) != count:
            raise ValueError('Unknown or incomplete Asternic direction calls')
    if re.search(r"dst\s+LIKE\s+'9%'|src\s+REGEXP\s+'\^\[0-9\]\{7,11\}\$'|preg_match\('/\^9", text):
        raise ValueError('Legacy Asternic direction gate remains')


def transform_page(text):
    newline = '\r\n' if '\r\n' in text else '\n'
    text = text.replace('\r\n', '\n')
    expected = {'outgoing': 5, 'incoming': 5, 'internal': 1}
    if BEGIN not in text:
        text = replace_exact(text, "require_once(dirname(__FILE__) . '/functions.inc.php');",
                             "require_once(dirname(__FILE__) . '/functions.inc.php');\n" + LOAD, 1)
        for direction, original in (('outgoing', "dst LIKE '9%'"), ('incoming', "src REGEXP '^[0-9]{7,11}$'")):
            call = "asternic_mytel_direction_sql($db, '" + direction + "')"
            text = replace_exact(text, '"AND ' + original + ' "', '"AND " . ' + call + ' . " "', 3)
            text = replace_exact(text, '" AND ' + original + '"', '" AND " . ' + call, 1)
        anchor = 'function asternic_home($appconfig) {'
        if text.count(anchor) != 1:
            raise ValueError('Unknown Asternic home source')
        before, home = text.split(anchor, 1)
        home = replace_exact(home, "if(j1.dial is not null and j2.dial is null,'outbound','')",
                             "if(\" . asternic_mytel_direction_sql($db, 'outgoing') . \",'outbound','')", 1)
        home = replace_exact(home, "if(j1.dial is null and j2.dial is not null,'inbound','')",
                             "if(\" . asternic_mytel_direction_sql($db, 'incoming') . \",'inbound','')", 1)
        home = replace_exact(home, "if(j1.dial is not null and j2.dial is not null,'internal','')",
                             "if(\" . asternic_mytel_direction_sql($db, 'internal') . \",'internal','')", 1)
        text = before + anchor + home
    for old, new in DIRECTION_COMMENTS.items():
        text = text.replace(old, new)
    validate_result(text, expected)
    return text.replace('\n', newline)


def transform_functions(text):
    newline = '\r\n' if '\r\n' in text else '\n'
    text = text.replace('\r\n', '\n')
    expected = {'outgoing': 1, 'incoming': 1, 'external': 1}
    if BEGIN not in text:
        if not text.startswith('<?php') or text.count('function asternic_getrecords(') != 1:
            raise ValueError('Unknown Asternic records helper')
        text = text.replace('<?php', '<?php\n' + LOAD, 1)
        for direction, original in (('outgoing', "dst LIKE '9%'"), ('incoming', "src REGEXP '^[0-9]{7,11}$'")):
            text = replace_exact(text, '" AND ' + original + '"',
                                 '" AND " . asternic_mytel_direction_sql($db, \'' + direction + "')", 1)
        start = '            // --- فیلتر تماس‌های خارجی برای تب Combined ---'
        end = '            // --- پایان فیلتر خارجی ---'
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError('Unknown Asternic combined direction filter')
        left, remainder = text.split(start, 1)
        block, right = remainder.split(end, 1)
        if block.count("preg_match('/^9[0-9]*/'") != 1 or block.count("preg_match('/^[0-9]{7,11}$/'") != 1:
            raise ValueError('Unknown Asternic combined predicate')
        text = left + '            // External direction is filtered by the shared SQL predicate.' + right
        query = "    if($gtype=='combined') {\n        $query  = \"SELECT substring(channel"
        insertion = ("    if ($gtype === 'combined' && $comb_type === 'external') {\n"
                     "        $condicionextra .= \" AND \" . asternic_mytel_direction_sql($db, 'external');\n"
                     "    }\n\n")
        text = replace_exact(text, query, insertion + query, 1)
    for old, new in DIRECTION_COMMENTS.items():
        text = text.replace(old, new)
    validate_result(text, expected)
    return text.replace('\n', newline)


def safe_file(path, root):
    if path.is_symlink() or root not in path.resolve().parents or not path.is_file():
        raise ValueError('Unsafe Asternic source path')
    return path.read_bytes()


def plan(module_root):
    module_root = Path(module_root).absolute()
    if module_root.is_symlink():
        raise ValueError('Symlinked Asternic module path')
    if not module_root.exists():
        return {}
    if any(parent.is_symlink() for parent in (module_root,) + tuple(module_root.parents)):
        raise ValueError('Symlinked Asternic module path')
    root = module_root.resolve()
    directory_info = root.stat()
    metadata = safe_file(root / 'module.xml', root)
    try:
        version = ET.fromstring(metadata).findtext('version')
    except ET.ParseError as error:
        raise ValueError('Invalid Asternic metadata') from error
    if version != '1.6.6':
        raise ValueError('Unsupported optional Asternic version')
    page = safe_file(root / 'page.asternic_cdr.php', root)
    functions = safe_file(root / 'functions.inc.php', root)
    helper = (SOURCE / 'asternic-direction.php').read_bytes()
    target = root / 'mytell-direction.php'
    previous_helper = None
    if target.exists() or target.is_symlink():
        previous_helper = safe_file(target, root)
        if previous_helper != helper:
            raise ValueError('Unknown existing Asternic direction helper')
    # Helper first: interrupted fresh installations can safely resume without a
    # patched PHP source ever requiring an absent dependency.
    return DirectionPlan({target: helper, root / 'functions.inc.php': transform_functions(functions.decode('utf-8')).encode('utf-8'),
                          root / 'page.asternic_cdr.php': transform_page(page.decode('utf-8')).encode('utf-8')},
                         {'mytell-direction.php': previous_helper, 'functions.inc.php': functions, 'page.asternic_cdr.php': page},
                         (directory_info.st_dev, directory_info.st_ino))


def read_at(directory, name):
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    except FileNotFoundError:
        return None, None
    with os.fdopen(descriptor, 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Asternic target is not a regular file')
        return source.read(), info


def open_directory(path):
    """Open every ancestor without following links, then keep its descriptor."""
    path = Path(os.path.abspath(str(path)))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open(path.anchor, flags)
    try:
        for component in path.parts[1:]:
            following = os.open(component, flags, dir_fd=directory)
            os.close(directory)
            directory = following
        return directory
    except OSError as error:
        os.close(directory)
        raise ValueError('Unsafe Asternic module directory component') from error


def apply(changes, backup_root):
    if not changes:
        return None
    if not isinstance(changes, DirectionPlan):
        raise ValueError('Asternic writes require an original-bound plan')
    root = next(iter(changes)).parent
    if any(path.parent != root for path in changes) or {path.name for path in changes} != set(changes.originals):
        raise ValueError('Unexpected Asternic write targets')
    directory = open_directory(root)
    try:
        info = os.fstat(directory)
        if (info.st_dev, info.st_ino) != changes.directory_identity:
            raise ValueError('Asternic module directory changed after preparation')
        expected = {path.name: read_at(directory, path.name) for path in changes}
        if any(expected[name][0] != original for name, original in changes.originals.items()):
            raise ValueError('Asternic source changed after preparation')
        backup_root = Path(backup_root).absolute()
        if root == backup_root or root in backup_root.parents:
            raise ValueError('Asternic backups must stay outside the module')
        if any(parent.is_symlink() for parent in (backup_root,) + tuple(backup_root.parents)):
            raise ValueError('Symlinked Asternic backup path')
        backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = backup_root.stat()
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Asternic backup directory must be private and owned')
        backup = Path(tempfile.mkdtemp(prefix='direction-', dir=str(backup_root)))
        for path, content in changes.items():
            original, info = expected[path.name]
            if original == content:
                continue
            if original is not None:
                archived = backup / path.name
                archived.write_bytes(original); archived.chmod(0o600)
            temporary = '.mytell-direction-' + secrets.token_hex(12)
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=directory)
            try:
                with os.fdopen(descriptor, 'wb') as staged:
                    staged.write(content); staged.flush()
                    if info:
                        os.fchmod(staged.fileno(), stat.S_IMODE(info.st_mode))
                        if os.geteuid() == 0: os.fchown(staged.fileno(), info.st_uid, info.st_gid)
                    os.fsync(staged.fileno())
                current, _ = read_at(directory, path.name)
                if current != original:
                    raise ValueError('Asternic source changed during preparation')
                os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
                os.fsync(directory)
            finally:
                try: os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError: pass
    finally:
        os.close(directory)
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module-root', type=Path, default=Path('/var/www/html/admin/modules/asternic_cdr'))
    parser.add_argument('--backup-root', type=Path, default=Path('/var/backups/mytellpbx/asternic-direction-v760'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    changes = plan(args.module_root)
    if not changes:
        print('OPTIONAL ASTERNIC ABSENT: no module installed or changed')
        return
    with tempfile.TemporaryDirectory(prefix='asternic-php-check-') as work:
        for index, content in enumerate(changes.values()):
            target = Path(work) / (str(index) + '.php'); target.write_bytes(content)
            subprocess.check_call(['php', '-l', str(target)])
    if not args.check:
        apply(changes, args.backup_root)
    print('CHECKED' if args.check else 'UPDATED', 'Asternic 1.6.6 direction policy')


if __name__ == '__main__':
    main()
