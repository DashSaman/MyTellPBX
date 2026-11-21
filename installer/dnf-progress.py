#!/usr/bin/env python3
"""Keep raw DNF output private while showing observed package progress.

This foreground stdin consumer never starts DNF, retries it or infers success.
Only known phase labels, validated counters and optional RPM names reach the
console. Python 3.6 compatible; no background timer or runtime dependency.
"""
import argparse
import os
from pathlib import Path
import re
import select
import shutil
import stat
import sys
import time

KINDS = {'update': 'به‌روزرسانی سیستم', 'packages': 'نصب بسته‌ها', 'repositories': 'آماده‌سازی مخازن',
         'iso': 'نصب از ISO'}
ENGLISH_KINDS = {'update': 'System update', 'packages': 'Package installation', 'repositories': 'Repository setup',
                 'iso': 'Install from ISO'}
DOWNLOAD = re.compile(rb'^\(\s*([0-9]{1,9})\s*/\s*([0-9]{1,9})\s*\):\s+')
TRANSACTION = re.compile(rb'^\s*(Installing|Upgrading|Updating|Downgrading|Reinstalling|Erasing|Cleanup|Verifying|Running scriptlet|Preparing)\s*:\s+(.*?)\s+([0-9]{1,9})\s*/\s*([0-9]{1,9})\s*$')
RPM_DOWNLOAD_NAME = re.compile(rb'([A-Za-z0-9][A-Za-z0-9_.+%-]{0,179}\.rpm)\s')
RPM_TRANSACTION_NAME = re.compile(rb'([A-Za-z0-9][A-Za-z0-9_.+%-]{0,179}\.(?:x86_64|noarch|i[3-6]86))')
UPSTREAM_PACKAGE = re.compile(r'^issabel(?:pbx)?', re.IGNORECASE)
TRANSFER_ERROR = re.compile(rb'^\s*(?:-\s*|\[MIRROR\]\s+[^\s:]+:\s*)?(Curl error \([0-9]{1,3}\)|Status code: [45][0-9]{2}):?\s')


class ProgressReporter:
    def __init__(self, output, kind, clock=time.monotonic, interval=30.0, english=False, detail=False):
        if kind not in KINDS:
            raise ValueError('Unknown DNF stage kind')
        self.output = output; self.kind = kind; self.clock = clock; self.english = english
        self.interval = interval; self.last_emit = None; self.seen = set()
        self.detail = detail
        self.started = clock()
        self.last_counter = None
        self.live = detail and getattr(output, 'isatty', lambda: False)() and os.environ.get('TERM') != 'dumb'
        self.line_length = 0
        self.last_idle = None
        self.transfer_problem_shown = False

    def detail_line(self, label):
        text = '      · ' + label
        if self.live:
            width = max(1, shutil.get_terminal_size((80, 24)).columns - 1)
            text = text[:width]
            self.output.write('\r' + text.ljust(min(self.line_length, width)))
            self.line_length = len(text)
        else:
            self.output.write(text + '\n')
        self.output.flush()

    def finish(self):
        if self.line_length:
            self.output.write('\n')
            self.output.flush()

    def waiting(self):
        now = self.clock()
        if self.last_emit is not None and now - self.last_emit < self.interval:
            return
        if not self.live and self.last_idle is not None and now - self.last_idle < 120:
            return
        seconds = int(now - self.started)
        label = 'Waiting for package manager output' if self.english else 'در انتظار خروجی سامانهٔ بسته‌ها'
        self.detail_line('{} · {}s'.format(label, seconds))
        self.last_emit = now
        self.last_idle = now

    def observe(self, record):
        download = DOWNLOAD.match(record)
        transaction = TRANSACTION.match(record) if download is None else None
        if download is not None:
            major = 'download'; label = 'دریافت بسته'; current, total = map(int, download.groups())
        elif transaction is not None:
            operation, target, current, total = transaction.groups(); current = int(current); total = int(total)
            major = 'verify' if operation == b'Verifying' else 'transaction'
            label = 'بررسی بسته' if major == 'verify' else 'عملیات بسته'
        else:
            if self.detail and not self.transfer_problem_shown and TRANSFER_ERROR.match(record):
                self.transfer_problem_shown = True
                # Detailed retry and transport diagnostics are in the private log.
                message = ('Package source is having connection problems' if self.english else
                           'اتصال به منبع بسته با مشکل روبه‌رو است')
                self.detail_line(message)
            return
        if self.kind == 'iso' and major == 'download':
            label = 'خواندن بسته از ISO'
        if not 1 <= current <= total:
            return
        now = self.clock()
        if self.detail:
            counter = (major, current, total)
            if counter == self.last_counter:
                return
            if self.last_counter and self.last_counter[0] == major and current != total:
                previous = self.last_counter[1]
                elapsed = now - self.last_emit
                if self.live and elapsed < 0.25:
                    return
                if not self.live and total > 10 and current * 10 // total == previous * 10 // total and elapsed < 60:
                    return
            self.last_counter = counter
        elif major in self.seen and self.last_emit is not None and now - self.last_emit < self.interval:
            return
        if self.detail:
            match = (RPM_DOWNLOAD_NAME.match(record, download.end()) if download is not None
                     else RPM_TRANSACTION_NAME.fullmatch(target))
            package = '  ' + UPSTREAM_PACKAGE.sub('MytelPBX', match.group(1).decode('ascii')) if match else ''
            if self.english:
                label = self.english_label(major)
            progress = '{}  {}/{}'.format(label, current, total)
            if self.live:
                percent = current * 100 // total
                if shutil.get_terminal_size((80, 24)).columns >= 70:
                    filled = current * 12 // total
                    progress += '  [{}{}]'.format('=' * filled, '-' * (12 - filled))
                progress += ' {:3d}%'.format(percent)
            self.detail_line(progress + package)
            self.last_emit = now
            self.last_idle = None
            return
        if self.english:
            label = self.english_label(major)
            self.output.write('[MyTellPBX] {}: {} {} of {}\n'.format(ENGLISH_KINDS[self.kind], label, current, total))
        else:
            self.output.write('[MyTellPBX] {}: {} {} از {}\n'.format(KINDS[self.kind], label, current, total))
        self.output.flush(); self.seen.add(major); self.last_emit = now

    def english_label(self, major):
        if major == 'download' and self.kind == 'iso':
            return 'Read from ISO'
        return {'download': 'Download', 'verify': 'Verification', 'transaction': 'Transaction'}[major]


def copy_progress(source, private_log, reporter, console_failed=False, wait_for_input=None):
    record = bytearray(); oversized = False; log_failed = False
    read = getattr(source, 'read1', source.read)
    while True:
        if wait_for_input is not None and not console_failed and not log_failed and not wait_for_input():
            try: reporter.waiting()
            except (OSError, ValueError): console_failed = True
            continue
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
    if not console_failed:
        try: reporter.finish()
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
    parser.add_argument('--detail', action='store_true', help='show package progress in the interactive installer')
    args = parser.parse_args()
    english = os.environ.get('MYTELL_CONSOLE_ENGLISH') == '1'
    try:
        with open_private_log(args.log) as private_log:
            if args.check_log: return 0
            console_failed = False
            try:
                if args.detail and args.kind in ('repositories', 'iso'):
                    print('      · ' + (ENGLISH_KINDS[args.kind] if english else KINDS[args.kind]), flush=True)
                elif not args.detail and english:
                    print('[MyTellPBX] {}: running; full output is recorded in the private installer log.'.format(ENGLISH_KINDS[args.kind]), flush=True)
                elif not args.detail:
                    print('[MyTellPBX] {}: در حال اجرا؛ گزارش کامل در فایل خصوصی نصب ثبت می‌شود.'.format(KINDS[args.kind]), flush=True)
            except (OSError, ValueError): console_failed = True
            source = sys.stdin.buffer
            wait_for_input = None
            if args.detail and os.name == 'posix' and stat.S_ISFIFO(os.fstat(source.fileno()).st_mode):
                # `read1` has no read-ahead beyond the returned chunk. Polling
                # the actual pipe lets us report waiting without pacing DNF.
                def wait_for_input():
                    return bool(select.select([source], [], [], 20)[0])
            reporter = ProgressReporter(sys.stdout, args.kind, interval=20 if args.detail else 30,
                                        english=english, detail=args.detail)
            valid = copy_progress(source, private_log, reporter, console_failed=console_failed,
                                  wait_for_input=wait_for_input)
            if not valid: return 1
    except (OSError, ValueError):
        if not args.check_log:
            read = getattr(sys.stdin.buffer, 'read1', sys.stdin.buffer.read)
            while read(65536): pass
        try: print('[MyTellPBX] Private package logging failed; installation stopped.' if english else '[MyTellPBX] ثبت امن گزارش بسته‌ها ناموفق بود؛ نصب متوقف شد.', file=sys.stderr)
        except (OSError, ValueError): pass
        return 1
    return 0


if __name__ == '__main__': sys.exit(main())
