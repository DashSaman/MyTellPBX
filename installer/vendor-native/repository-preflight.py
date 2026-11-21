#!/usr/bin/env python3
"""Check the real DNF metadata and HTTPS bootstrap RPMs before installation."""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPO_DIRECTORY = '/etc/yum.repos.d'
REPO_ID = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.:-]*')
URL = re.compile(r'https?://[^\s<>\]]+')


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


def diagnostic(message):
    lines = message.splitlines()
    for indicators in (('Curl error', 'curl: ('), ('Check exceeded', 'Error:')):
        for line in lines:
            if any(marker in line for marker in indicators):
                line = ''.join(char for char in line if char.isprintable()).strip()
                return URL.sub(lambda match: public_url(match[0]), line)[:320]
    return 'See the diagnostic log.'


def probe(job):
    label, command, logfile = job
    with logfile.open('x', encoding='utf-8') as output:
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=90, check=False)
            code = result.returncode
        except subprocess.TimeoutExpired:
            output.write('\nCheck exceeded 90 seconds.\n')
            code = 124
        except OSError:
            output.write('\nError: cannot launch the repository check.\n')
            code = 1
    return label, code, diagnostic(logfile.read_text(encoding='utf-8', errors='replace')), logfile


def run(workdir, staged, enabled, urls):
    report = workdir / 'repository-checks'
    report.mkdir(mode=0o700, exist_ok=True)
    # Keep results across stages, but discard downloaded test metadata.
    result_dir = Path(tempfile.mkdtemp(prefix='run-', dir=str(report)))
    with tempfile.TemporaryDirectory(prefix='dnf-', dir=str(workdir)) as temp:
        scratch = Path(temp)
        dirs, installed, unknown = repository_inventory(scratch, staged, enabled)
        if not installed:
            raise ValueError('DNF has no usable configured repositories')
        jobs = []
        for i, repo in enumerate(installed, 1):
            private = scratch / ('repo-' + str(i))
            private.mkdir()
            jobs.append((repo, dnf_command(repo, dirs, private), result_dir / ('repo-' + repo + '.log')))
        for i, url in enumerate(urls, 1):
            jobs.append((public_url(url), curl_command(url), result_dir / ('rpm-' + str(i) + '.log')))
        print(f'  Checking {len(jobs) + len(unknown)} repository and download source(s)…', flush=True)
        for repo in unknown:
            print(f'    FAIL {repo} — required repository is missing from the DNF configuration', flush=True)
        failed = len(unknown)
        with ThreadPoolExecutor(max_workers=6) as pool:
            for ready in as_completed([pool.submit(probe, job) for job in jobs]):
                label, code, detail, logfile = ready.result()
                if code:
                    failed += 1
                    print(f'    FAIL {label} — {detail} ({logfile.name})', flush=True)
                else:
                    print('    OK   ' + label, flush=True)
    print(f'  Repository checks: {len(jobs) + len(unknown) - failed} passed, {failed} failed. Logs: {result_dir}', flush=True)
    return int(bool(failed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workdir', type=Path)
    parser.add_argument('--staged-repos', type=Path)
    parser.add_argument('--enable', action='append', default=[])
    parser.add_argument('--package-url', action='append', default=[])
    args = parser.parse_args()
    if args.staged_repos and not args.staged_repos.is_dir():
        parser.error('staged repository directory is missing')
    if any(not REPO_ID.fullmatch(repo) for repo in args.enable):
        parser.error('invalid required repository ID')
    if any(not url.startswith('https://') for url in args.package_url):
        parser.error('repository package URLs require HTTPS')
    os.umask(0o077)
    try:
        return run(args.workdir, args.staged_repos, args.enable, args.package_url)
    except (ImportError, OSError, ValueError) as error:
        message = URL.sub(lambda match: public_url(match[0]), str(error))
        print('Repository inventory failed: ' + message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
