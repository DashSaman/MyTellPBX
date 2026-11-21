#!/usr/bin/env python3
"""Check the real DNF metadata and HTTPS bootstrap RPMs before installation."""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPO_DIRECTORY = '/etc/yum.repos.d'
REPO_ID = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.:-]*')
CURL_ERROR = re.compile(r'(?:Curl error\s*|curl:\s*)\(([0-9]{1,3})\)')
BAD_CHECKSUM = re.compile(r"\bbad [^\n]*checksum|\bchecksum[^\n]*(?:mismatch|does not match|doesn't match|failed)", re.I)
PROGRESS_INTERVAL = 45


def public_url(raw):
    """Omit proxy/repository credentials and signed URL parameters from the terminal."""
    try:
        url = urlsplit(raw)
        return urlunsplit((url.scheme, url.netloc.rsplit('@', 1)[-1], url.path, '', ''))
    except ValueError:
        return '[invalid URL]'


def repository_inventory(scratch, staged, enabled):
    import dnf

    with dnf.Base() as base:
        base.conf.read()
        base.conf.cachedir = str(scratch / 'inventory-cache')
        base.conf.persistdir = str(scratch / 'inventory-state')
        base.conf.logdir = str(scratch)
        defaults = list(base.conf.reposdir)
        if staged:
            # Overlay the same names the installer writes without touching the OS.
            overlay = scratch / 'repo-overlay'
            overlay.mkdir()
            for directory in (Path(REPO_DIRECTORY), staged):
                for path in directory.glob('*.repo'):
                    if path.is_file():
                        shutil.copyfile(str(path), str(overlay / path.name))
            defaults = [str(overlay) if directory.rstrip('/') == REPO_DIRECTORY else directory
                        for directory in defaults]
            if str(overlay) not in defaults:
                raise ValueError('DNF does not read the installer repository directory')
            base.conf.reposdir = defaults
        base.read_all_repos()
        selected = {repo.id for repo in base.repos.values() if repo.enabled}
        unknown = sorted(set(enabled) - {repo.id for repo in base.repos.values()})
    selected.update(set(enabled) - set(unknown))
    if any(not REPO_ID.fullmatch(name) for name in selected):
        raise ValueError('DNF inventory contains an unsupported repository ID')
    return defaults, sorted(selected), unknown


def dnf_command(repo, dirs, scratch):
    return [
        'dnf', '--verbose', '--assumeyes', '--noplugins', '--refresh',
        '--disablerepo=*', '--enablerepo=' + repo,
        '--setopt=reposdir=' + ','.join(dirs),
        '--setopt=cachedir=' + str(scratch / 'cache'),
        '--setopt=persistdir=' + str(scratch / 'state'),
        '--setopt=logdir=' + str(scratch),
        '--setopt=' + repo + '.skip_if_unavailable=False',
        '--setopt=' + repo + '.timeout=10',
        '--setopt=' + repo + '.retries=2',
        'makecache',
    ]


def curl_command(url):
    return [
        'curl', '--disable', '--fail', '--silent', '--show-error', '--location',
        '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '8',
        '--max-time', '18', '--retry', '1', '--retry-max-time', '25',
        '--output', os.devnull, url,
    ]


def failure_category(message, code):
    """Report only known categories to the console. Raw details stay in the log."""
    if code == 124:
        return 'source check timed out'
    match = CURL_ERROR.search(message)
    if match:
        detail = int(match.group(1))
        if detail in (35, 51, 58, 60, 77, 83, 90, 91):
            return 'secure connection failed'
        if detail == 28:
            return 'connection timed out'
        if detail in (5, 6):
            return 'source name could not be resolved'
    if BAD_CHECKSUM.search(message):
        return 'source integrity check failed'
    return 'source unavailable'


def process_activity(pid):
    """Count transfer/disk work and CPU spent parsing DNF metadata on Linux."""
    proc = Path('/proc') / str(pid)
    try:
        counts = dict(line.split(':', 1) for line in (proc / 'io').read_text().splitlines())
        fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        return (int(counts['rchar']) + int(counts['wchar']), int(fields[11]) + int(fields[12]))
    except (OSError, KeyError, IndexError, ValueError):
        return None


def wait_for_metadata(process, tick=time.monotonic):
    started = last_work = tick()
    previous = process_activity(process.pid)
    ticks_per_second = os.sysconf('SC_CLK_TCK') if hasattr(os, 'sysconf') else 100
    while True:
        try:
            return process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            now = tick()
            activity = process_activity(process.pid)
            if activity and (previous is None or activity[0] - previous[0] >= 65536 or
                             activity[1] - previous[1] >= ticks_per_second):
                last_work, previous = now, activity
            if now - started >= 1800 or (previous and now - last_work >= 150):
                raise subprocess.TimeoutExpired(process.args, int(now - started))


def probe(job):
    label, command, logfile = job
    with logfile.open('x', encoding='utf-8') as output:
        try:
            with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output,
                                  stderr=subprocess.STDOUT) as process:
                try:
                    code = wait_for_metadata(process) if command[0] == 'dnf' else process.wait(timeout=60)
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
        except subprocess.TimeoutExpired as exc:
            output.write('\nCheck exceeded its progress or overall time limit ({}s elapsed).\n'.format(exc.timeout))
            code = 124
        except OSError:
            output.write('\nError: cannot launch the repository check.\n')
            code = 1
    reason = failure_category(logfile.read_text(encoding='utf-8', errors='replace'), code) if code else ''
    return label, code, reason, logfile


def move_repo_metadata(repo, source, target):
    # Native DNF keys directories by repo ID and source URL. Move only the
    # verified metadata, leaving solver indexes, locks and unrelated repos alone.
    if not source.is_dir():
        return
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    for entry in source.iterdir():
        if re.fullmatch(re.escape(repo) + r'-[0-9a-f]{16}', entry.name) and entry.is_dir() and not entry.is_symlink():
            entry.rename(target / entry.name)


def run(workdir, staged, enabled, urls, keep_cache=False):
    report = workdir / 'repository-checks'
    report.mkdir(mode=0o700, exist_ok=True)
    # Keep results across stages, but discard downloaded test metadata.
    result_dir = Path(tempfile.mkdtemp(prefix='run-', dir=str(report)))
    with tempfile.TemporaryDirectory(prefix='dnf-', dir=str(workdir)) as temp:
        scratch = Path(temp)
        dirs, installed, unknown = repository_inventory(scratch, staged, enabled)
        if not installed:
            raise ValueError('DNF has no usable configured repositories')
        jobs, repo_caches = [], {}
        for i, repo in enumerate(installed, 1):
            private = scratch / ('repo-' + str(i))
            private.mkdir()
            if keep_cache:
                repo_caches[repo] = private / 'cache'
                move_repo_metadata(repo, workdir / 'dnf-cache', private / 'cache')
            jobs.append((repo, dnf_command(repo, dirs, private), result_dir / ('repo-' + repo + '.log')))
        for i, url in enumerate(urls, 1):
            jobs.append((public_url(url), curl_command(url), result_dir / ('rpm-' + str(i) + '.log')))
        total = len(jobs) + len(unknown)
        print(f'  Checking {total} package sources…', flush=True)
        failed = len(unknown)
        reasons = Counter()
        if unknown:
            (result_dir / 'missing-sources.log').write_text('\n'.join(unknown) + '\n', encoding='utf-8')
            reasons['required source missing'] = failed
        with ThreadPoolExecutor(max_workers=6) as pool:
            pending = {pool.submit(probe, job) for job in jobs}
            next_update = time.monotonic() + PROGRESS_INTERVAL
            while pending:
                timeout = max(0, next_update - time.monotonic())
                completed, pending = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
                for ready in completed:
                    label, code, reason, _ = ready.result()
                    if code:
                        failed += 1
                        reasons[reason] += 1
                    elif label in repo_caches:
                        move_repo_metadata(label, repo_caches[label], workdir / 'dnf-cache')
                now = time.monotonic()
                if pending and now >= next_update:
                    print(f'    {total - len(pending)}/{total} checked · {failed} failed · {len(pending)} remaining',
                          flush=True)
                    next_update = now + PROGRESS_INTERVAL
    print(f'  Package sources: {total - failed} passed, {failed} failed.', flush=True)
    if failed:
        print('    ' + ' · '.join('{} ({})'.format(reason, reasons[reason]) for reason in sorted(reasons)), flush=True)
        print(f'    Private logs: {result_dir}', flush=True)
    return int(bool(failed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workdir', type=Path)
    parser.add_argument('--staged-repos', type=Path)
    parser.add_argument('--enable', action='append', default=[])
    parser.add_argument('--package-url', action='append', default=[])
    parser.add_argument('--keep-cache', action='store_true', help='Reuse verified metadata within this installation')
    args = parser.parse_args()
    if args.staged_repos and not args.staged_repos.is_dir():
        parser.error('staged repository directory is missing')
    if any(not REPO_ID.fullmatch(repo) for repo in args.enable):
        parser.error('invalid required repository ID')
    if any(not url.startswith('https://') for url in args.package_url):
        parser.error('repository package URLs require HTTPS')
    os.umask(0o077)
    try:
        return run(args.workdir, args.staged_repos, args.enable, args.package_url, args.keep_cache)
    except (ImportError, OSError, ValueError) as error:
        print('  Could not prepare package source checks.', file=sys.stderr)
        report = args.workdir / 'repository-checks'
        try:
            report.mkdir(mode=0o700, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=str(report),
                                             prefix='inventory-', suffix='.log', delete=False) as log:
                log.write(str(error) + '\n')
                print(f'    Private log: {log.name}', file=sys.stderr)
        except OSError:
            print('    Could not write the private source check log.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
