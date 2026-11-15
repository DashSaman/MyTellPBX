#!/usr/bin/env python3
"""Keep DNF output private while showing bounded, observed package counters.

This foreground stdin consumer never starts DNF, retries it or infers success.
Only fixed phase labels and validated integer counters reach the console.
Python 3.6 compatible; no background timer or additional runtime dependency.
"""
import argparse
import os
from pathlib import Path
import re
import stat
import sys
import time

KINDS = {'update': 'به‌روزرسانی سیستم', 'packages': 'نصب بسته‌ها', 'repositories': 'آماده‌سازی مخازن'}
DOWNLOAD = re.compile(rb'^\(\s*([0-9]{1,9})\s*/\s*([0-9]{1,9})\s*\):\s')
TRANSACTION = re.compile(rb'^\s*(Installing|Upgrading|Updating|Downgrading|Reinstalling|Erasing|Cleanup|Verifying|Running scriptlet|Preparing)\s*:\s+.*?\s+([0-9]{1,9})\s*/\s*([0-9]{1,9})\s*$')


class ProgressReporter:
    def __init__(self, output, kind, clock=time.monotonic, interval=30.0):
        if kind not in KINDS:
            raise ValueError('Unknown DNF stage kind')
        self.output = output; self.kind = kind; self.clock = clock
        self.interval = interval; self.last_emit = None; self.seen = set()

    def observe(self, record):
        download = DOWNLOAD.match(record)
        transaction = TRANSACTION.match(record) if download is None else None
        if download is not None:
            major = 'download'; label = 'دریافت بسته'; current, total = map(int, download.groups())
        elif transaction is not None:
            operation, current, total = transaction.groups(); current = int(current); total = int(total)
            major = 'verify' if operation == b'Verifying' else 'transaction'
            label = 'بررسی بسته' if major == 'verify' else 'عملیات بسته'
        else:
            return
        if not 1 <= current <= total:
            return
        now = self.clock()
        # A first real download/transaction/verification observation can appear
        # immediately. Alternating scriptlet/install lines share one category.
        if major in self.seen and self.last_emit is not None and now - self.last_emit < self.interval:
            return
        self.output.write('[MyTellPBX] {}: {} {} از {}\n'.format(KINDS[self.kind], label, current, total))
        self.output.flush(); self.seen.add(major); self.last_emit = now


def copy_progress(source, private_log, reporter, console_failed=False):
    record = bytearray(); oversized = False; log_failed = False
    read = getattr(source, 'read1', source.read)
    while True:
        chunk = read(65536)
        if not chunk:
            break
        if not log_failed:
            try:
                pending = memoryview(chunk)
                while pending:
                    written = private_log.write(pending)
                    if written is None or written <= 0:
                        raise OSError('Incomplete private log write')
                    pending = pending[written:]
                private_log.flush()
            except (OSError, ValueError):
                log_failed = True
        # A failed console/log must not close the pipe underneath a live RPM
        # transaction. Keep consuming DNF to its natural EOF, then fail.
        if console_failed or log_failed:
            continue
        for value in chunk:
            if value in (10, 13):
                if record and not oversized:
                    try: reporter.observe(bytes(record))
                    except (OSError, ValueError): console_failed = True
                record.clear(); oversized = False
                if console_failed: break
            elif not oversized:
                if len(record) < 16384:
                    record.append(value)
                else:
                    record.clear(); oversized = True
    if record and not oversized and not console_failed and not log_failed:
        try: reporter.observe(bytes(record))
        except (OSError, ValueError): console_failed = True
    return not (log_failed or console_failed)


def open_private_log(path):
    path = Path(path)
    if path.resolve() != path.absolute():
        raise ValueError('DNF log path must not contain symlinks')
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(str(path), flags, 0o600)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError('DNF log must be a regular file')
        if os.name == 'posix' and (metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o600):
            raise ValueError('DNF log must be owned by the installer and mode 0600')
        return os.fdopen(fd, 'ab', buffering=0)
    except BaseException:
        os.close(fd); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', required=True, type=Path)
    parser.add_argument('--kind', required=True, choices=sorted(KINDS))
    parser.add_argument('--check-log', action='store_true', help='validate private logging before DNF starts')
    args = parser.parse_args()
    try:
        with open_private_log(args.log) as private_log:
            if args.check_log: return 0
            console_failed = False
            try:
                print('[MyTellPBX] {}: در حال اجرا؛ گزارش کامل در فایل خصوصی نصب ثبت می‌شود.'.format(KINDS[args.kind]), flush=True)
            except (OSError, ValueError): console_failed = True
            valid = copy_progress(sys.stdin.buffer, private_log, ProgressReporter(sys.stdout, args.kind), console_failed=console_failed)
            if not valid: return 1
    except (OSError, ValueError):
        if not args.check_log:
            read = getattr(sys.stdin.buffer, 'read1', sys.stdin.buffer.read)
            while read(65536): pass
        try: print('[MyTellPBX] ثبت امن گزارش بسته‌ها ناموفق بود؛ نصب متوقف شد.', file=sys.stderr)
        except (OSError, ValueError): pass
        return 1
    return 0


if __name__ == '__main__': sys.exit(main())
