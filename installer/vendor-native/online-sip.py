#!/usr/bin/env python3
"""Prepare the native SIP and Persian locale steps for guided terminal setup."""

import importlib.util
import os
from pathlib import Path
import stat
import sys


MYSQL_CLIENT = b'''function mytel_native_mysql()
{
    mysql --defaults-extra-file=/dev/fd/3 "$@" \\
        3< <(printf '[client]\\npassword="%s"\\n' "$mysqlrootpwd")
}

'''


def branding_module():
    path = Path(__file__).with_name('brand-native-dialogs.py')
    spec = importlib.util.spec_from_file_location('mytel_native_branding', str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive(source):
    source = branding_module().transform('sip', source)

    def replace(before, after, count=1):
        nonlocal source
        if source.count(before) != count:
            raise ValueError('Unexpected native SIP setup boundary')
        source = source.replace(before, after)

    replace(b'#!/bin/bash\n', b'#!/bin/bash\nset +x\n')
    start = source.index(b'check_astVer\ncheck_dialog\nsource /etc/issabel.conf\n')
    end = source.index(b'#Set ports\n', start)
    replace(source[start:end], b'''selSIP=${MYTEL_ONLINE_SIP_DRIVER:-}
case "$selSIP" in
    pjsip|sip) ;;
    *) echo 'Invalid SIP driver choice.' >&2; exit 1 ;;
esac
[[ $(asterisk -V) == 'Asterisk 20.'* ]] || exit 1
source /etc/issabel.conf || exit 1
[ -n "${mysqlrootpwd:-}" ] || exit 1
check_database

''')
    replace(b'function check_database()\n', MYSQL_CLIENT + b'function check_database()\n')
    replace(b'mysql -uroot -p$mysqlrootpwd asterisk', b'mytel_native_mysql -uroot asterisk', 6)
    source = b'\n'.join(line + b' || exit $?' if line.startswith(b'  mytel_native_mysql ') else line
                        for line in source.split(b'\n'))
    end_of_sql = b') &> /dev/null\nlogo\nif ! amportal a r &> /dev/null\n'
    start = source.index(end_of_sql)
    replace(source[start:], b') &> /dev/null || exit $?\namportal a r &> /dev/null\n')
    return source


def derive_language(source):
    # The vendor's noninteractive `pr` option still calls a dialog logo and
    # clears the controlling terminal during reload. Reuse its pinned setting
    # functions and apply changes directly in the transient installer helper.
    source = branding_module().transform('language', source)
    start = source.index(b'function set_lang_variables()')
    end = source.index(b'function reload_amportal()')
    settings = source[start:end]
    client = b'mysql -uroot $MYSQLAUTH asterisk'
    if settings.count(client) != 4:
        raise ValueError('Unexpected native locale SQL boundary')
    settings = settings.replace(client, b'mytel_native_mysql -uroot asterisk')
    writes = (b'sqlite3 ', b'mytel_native_mysql ')
    lines = settings.split(b'\n')
    if sum(line.lstrip().startswith(writes) for line in lines) != 6:
        raise ValueError('Unexpected native locale database writes')
    settings = b'\n'.join(line.rstrip(b';') + b' || exit $?' if line.lstrip().startswith(writes) else line
                          for line in lines)
    dahdi_start = settings.index(b'  if grep -q "language=" $DAHDI_CFG\n')
    dahdi_end = settings.index(b'  sed -i "s/.*defaultlanguage', dahdi_start)
    dahdi = settings[dahdi_start:dahdi_end].splitlines()
    guarded = [b'  ' + line + (b' || exit $?' if line.lstrip().startswith(b'sed ') else b'') for line in dahdi]
    settings = (settings[:dahdi_start] + b'  if [ -f "$DAHDI_CFG" ]; then\n' + b'\n'.join(guarded)
                + b'\n  fi\n' + settings[dahdi_end:])
    settings = settings.replace(b'      write_selection\n', b'      return 1\n')
    return (b'#!/bin/bash\nset +x\n' + MYSQL_CLIENT + settings + b'''
source /etc/issabel.conf || exit 1
[ -n "${mysqlrootpwd:-}" ] || exit 1
selLang=pr
set_lang_variables
set_language || exit $?
amportal a r >/dev/null 2>&1
''')


def main():
    if len(sys.argv) != 2 or os.geteuid() != 0:
        raise SystemExit('A private root-owned installer workspace is required.')
    workspace = Path(sys.argv[1]).absolute()
    info = workspace.lstat()
    if (workspace.resolve() != workspace or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != 0 or info.st_mode & 0o077):
        raise SystemExit('Invalid private installer workspace.')
    for tool, render in (('sip', derive), ('language', derive_language)):
        stock = Path('/usr/bin/issabel-change-' + tool)
        branding_module().regular(stock)
        generated = render(stock.read_bytes())
        output = workspace / ('mytel-online-' + tool + '.sh')
        descriptor = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o700)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(generated)


if __name__ == '__main__':
    main()
