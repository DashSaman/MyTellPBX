#!/usr/bin/env python3
"""Prepare the pinned native SIP configurator for the online installer's choice."""

import importlib.util
import os
from pathlib import Path
import stat
import sys


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
    replace(b'function check_database()\n', b'''function mytel_sip_mysql()
{
    mysql --defaults-extra-file=/dev/fd/3 "$@" \\
        3< <(printf '[client]\\npassword="%s"\\n' "$mysqlrootpwd")
}

function check_database()
''')
    replace(b'mysql -uroot -p$mysqlrootpwd asterisk', b'mytel_sip_mysql -uroot asterisk', 6)
    source = b'\n'.join(line + b' || exit $?' if line.startswith(b'  mytel_sip_mysql ') else line
                        for line in source.split(b'\n'))
    end_of_sql = b') &> /dev/null\nlogo\nif ! amportal a r &> /dev/null\n'
    start = source.index(end_of_sql)
    replace(source[start:], b') &> /dev/null || exit $?\namportal a r &> /dev/null\n')
    return source


def main():
    if len(sys.argv) != 2 or os.geteuid() != 0:
        raise SystemExit('A private root-owned installer workspace is required.')
    workspace = Path(sys.argv[1]).absolute()
    info = workspace.lstat()
    if (workspace.resolve() != workspace or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != 0 or info.st_mode & 0o077):
        raise SystemExit('Invalid private installer workspace.')
    stock = Path('/usr/bin/issabel-change-sip')
    branding_module().regular(stock)
    generated = derive(stock.read_bytes())
    output = workspace / 'mytel-online-sip.sh'
    descriptor = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o700)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(generated)


if __name__ == '__main__':
    main()
