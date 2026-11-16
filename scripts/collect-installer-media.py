#!/usr/bin/env python3
"""Collect a signed, solver-verified ISO depot on a disposable Rocky8.10 lab.

Default is an inert input plan. Execute with platform-python (DNF4 bindings).
Only a new output directory and its private sibling work directory are written.
No RPM transaction, service action, live database or existing output is changed.
"""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tarfile
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

MAX_RPMS = 5000
MAX_RPM_BYTES = 16 * 1024 ** 3
WHEELS = {'flatbuffers', 'numpy', 'onnxruntime', 'packaging', 'protobuf', 'webrtcvad-wheels'}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def regular(path, limit=MAX_RPM_BYTES):
    path = Path(path)
    if path.resolve() != path.absolute() or path.is_symlink(): raise ValueError('Input links refused')
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit
            or (os.name == 'posix' and (info.st_uid != os.geteuid() or info.st_mode & 0o022))):
        raise ValueError('Expected a bounded root-owned public input')
    return path


def safe_url(url):
    value = urlsplit(str(url))
    if (value.scheme not in ('https', 'file') or value.username or value.password or value.fragment
            or any(c.isspace() for c in str(url)) or (value.scheme == 'https' and not value.hostname)
            or (value.scheme == 'file' and (value.netloc or not value.path.startswith('/')))):
        raise ValueError('Only public HTTPS or local-file repository sources are supported')
    return value


def require_public_key(data):
    if (not 32 <= len(data) <= 2 * 1024 * 1024 or b'PRIVATE' in data
            or b'-----BEGIN PGP PUBLIC KEY BLOCK-----' not in data
            or b'-----END PGP PUBLIC KEY BLOCK-----' not in data):
        raise ValueError('Repository key is not an armored public key')


def require_signature(returncode, text):
    if (returncode or re.search(r'\b(?:NOKEY|NOT OK|BAD|NOTTRUSTED)\b', text, re.I)
            or not re.search(r'(?im)^\s*(?:Header )?V[34] [^\n]*Signature, key ID [0-9a-f]+: OK\s*$', text)):
        raise ValueError('RPM digital signature did not verify; unsigned RPMs are refused')


def stage_rpm(source, directory, expected_size):
    """DNF file:// repositories keep localPkg on the original read-only media."""
    source = regular(Path(source)); directory = Path(directory)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]*\.rpm', source.name):
        raise ValueError('Unsafe RPM filename')
    before = source.lstat()
    if before.st_size != expected_size: raise ValueError('RPM differs from repository size')
    destination = directory / source.name
    if destination.is_symlink(): raise ValueError('RPM destination link refused')
    same = source == destination.absolute()
    exists = destination.exists()
    if exists: regular(destination)
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mode, info.st_uid,
                info.st_gid, info.st_mtime_ns, info.st_ctime_ns if os.name == 'posix' else None)
    checksum = hashlib.sha256(); count = 0; output = None
    fd = os.open(str(source), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        with os.fdopen(fd, 'rb') as stream:
            if identity(os.fstat(stream.fileno())) != identity(before): raise ValueError('RPM source changed before copy')
            if not same and not exists: output = destination.open('xb')
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                count += len(block); checksum.update(block)
                if output is not None and output.write(block) != len(block): raise ValueError('Short RPM output write')
            if (count != expected_size or identity(os.fstat(stream.fileno())) != identity(before)
                    or identity(source.lstat()) != identity(before)):
                raise ValueError('RPM source changed during copy')
    finally:
        if output is not None: output.close()
    if digest(destination) != checksum.hexdigest(): raise ValueError('RPM destination collision or copy mismatch')
    return destination


def package_roots(stage1, stage2, kernel):
    if not re.fullmatch(r'4\.18\.0-[A-Za-z0-9_.]+\.x86_64', kernel):
        raise ValueError('Exact installed Rocky8.10 kernel release required')
    values = list(stage1) + list(stage2) + ['@^minimal-environment', 'policycoreutils', 'tar', 'xz', 'python3.11', 'python3.11-pip']
    values += [name + '-' + kernel for name in ['kernel', 'kernel-core', 'kernel-modules', 'kernel-devel', 'kernel-headers']]
    if any(not re.fullmatch(r'@\^[a-z0-9_-]+|[A-Za-z0-9_.+:-]+', p) for p in values):
        raise ValueError('Invalid package root')
    return sorted(set(values))


def archive_member(path, name):
    with tarfile.open(str(path), 'r:gz') as archive:
        found = [x for x in archive.getmembers() if x.name == name]
        if len(found) != 1 or not found[0].isfile() or not 0 < found[0].size <= 1024 * 1024:
            raise ValueError('Missing or ambiguous release metadata')
        return archive.extractfile(found[0]).read()


def inputs(bootstrap, bundle, desk, kernel):
    bootstrap, bundle, desk = regular(bootstrap, 256 * 1024), regular(bundle), regular(desk)
    text = bootstrap.read_text(encoding='utf-8')
    def setting(name, pattern):
        found = re.findall(r'^' + name + r'="(' + pattern + r')"$', text, re.M)
        if len(found) != 1: raise ValueError('Bootstrap release identity missing')
        return found[0]
    version = setting('MYTELLPBX_VERSION', r'[0-9]+\.[0-9]+\.[0-9]+')
    expected = setting('MYTELLPBX_BUNDLE_SHA256', r'[0-9a-f]{64}')
    if digest(bundle) != expected: raise ValueError('Bundle differs from bootstrap checksum')
    prefix = 'mytelpbx-bundle-' + version + '/'
    pin = json.loads(archive_member(bundle, prefix + 'installer/myteldesk-release.json').decode('utf-8'))
    if (pin.get('repository') != 'DashSaman/MytelDesk' or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', str(pin.get('version')))
            or not re.fullmatch(r'[0-9a-f]{64}', str(pin.get('sha256'))) or digest(desk) != pin['sha256']):
        raise ValueError('Desk archive differs from the bundled release pin')
    desk_prefix = 'myteldesk-' + pin['version'] + '/'
    node = json.loads(archive_member(desk, desk_prefix + 'installer/runtime.json').decode('utf-8'))
    vad = json.loads(archive_member(desk, desk_prefix + 'backend/vad/runtime.json').decode('utf-8'))
    if (not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', str(node.get('version')))
            or not re.fullmatch(r'[0-9a-f]{64}', str(node.get('sha256')))
            or vad.get('python_version') != '3.11' or vad.get('architecture') != 'x86_64'
            or {p.get('name') for p in vad.get('packages', [])} != WHEELS):
        raise ValueError('Unsupported pinned Node/VAD closure')
    lists = []
    for name in ['rocky8-stage1.txt', 'rocky8-stage2-asterisk20.txt']:
        lists.append([s.strip() for s in archive_member(bundle, prefix + 'installer/packages/' + name).decode('ascii').splitlines() if s.strip() and not s.startswith('#')])
    return dict(version=version, bootstrap_sha256=digest(bootstrap), bundle_sha256=expected, desk=pin, node=node, vad=vad,
                roots=package_roots(lists[0], lists[1], kernel))


def create_output(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path.absolute() or path.exists() or path.is_symlink():
        raise ValueError('A new canonical absolute output directory is required')
    path.mkdir(mode=0o755)
    return path


def fetch_asset(url, destination, expected, limit, cache=None):
    safe_url(url); destination = Path(destination)
    if expected is not None and not re.fullmatch(r'[0-9a-f]{64}', expected): raise ValueError('Invalid asset pin')
    name = urlsplit(url).path.rsplit('/', 1)[-1]
    source = Path(cache) / name if cache is not None else None
    if source is not None and (source.exists() or source.is_symlink()):
        regular(source, limit)
        if expected is None or digest(source) != expected: raise ValueError('Cached asset needs its exact checksum')
        shutil.copyfile(str(source), str(destination))
    else:
        started = time.monotonic(); count = 0
        with urlopen(url, timeout=45) as response, destination.open('xb') as out:
            if safe_url(response.geturl()).scheme != 'https': raise ValueError('Insecure asset redirect')
            while True:
                block = response.read(1024 * 1024)
                if not block: break
                count += len(block)
                if count > limit or time.monotonic() - started > 900: raise ValueError('Asset download limit exceeded')
                out.write(block)
    if not 0 < destination.stat().st_size <= limit or (expected is not None and digest(destination) != expected):
        raise ValueError('Downloaded asset checksum or size mismatch')
    destination.chmod(0o644)


def configured_base(work, reposdir, repo_ids, dnf_module=None, module_factory=None):
    if dnf_module is None:
        import dnf as dnf_module
    if module_factory is None:
        from dnf.module.module_base import ModuleBase
        module_factory = ModuleBase
    base = dnf_module.Base()
    for field in ['root', 'cache', 'persist', 'logs']: (work / field).mkdir(parents=True, exist_ok=True)
    base.conf.installroot = str(work / 'root')
    base.conf.cachedir = str(work / 'cache'); base.conf.persistdir = str(work / 'persist'); base.conf.logdir = str(work / 'logs')
    base.conf.reposdir = [str(reposdir)]; base.conf.substitutions['releasever'] = '8'
    base.conf.substitutions['basearch'] = 'x86_64'; base.conf.module_platform_id = 'platform:el8'
    # Match the supported native online DNF policy, including Recommends/features.
    base.conf.install_weak_deps = True; base.conf.gpgcheck = True; base.conf.localpkg_gpgcheck = True
    base.conf.timeout = 30; base.conf.retries = 2
    try:
        base.read_all_repos()
        if set(repo_ids) - set(base.repos): raise ValueError('Explicit source repository is absent')
        for repo in base.repos.values():
            if repo.id not in repo_ids: repo.disable(); continue
            for url in list(repo.baseurl) + [v for v in [repo.metalink, repo.mirrorlist] if v]: safe_url(url)
            repo.enable(); repo.gpgcheck = True; repo.sslverify = True; repo.skip_if_unavailable = False
            repo.add_metadata_type_to_download('modules'); repo.add_metadata_type_to_download('group')
        base.fill_sack(load_system_repo=False)
        module_factory(base).enable(['php:remi-7.4'])
        return base
    except BaseException:
        base.close(); raise


def resolve(base, roots):
    base.read_comps(arch_filter=True)
    base.install_specs(roots); base.resolve(allow_erasing=False)
    packages = list(base.transaction.install_set)
    if (not 1 <= len(packages) <= MAX_RPMS or list(base.transaction.remove_set)
            or sum(int(p.downloadsize) for p in packages) > MAX_RPM_BYTES
            or any(p.installed or p.arch not in ('x86_64', 'noarch') for p in packages)):
        raise ValueError('Resolver returned an unsupported transaction')
    return packages


def nevra(package):
    return '{}-{}:{}-{}.{}'.format(package.name, package.epoch, package.version, package.release, package.arch)


def compare_closure(original, local, repo_ids):
    if ({nevra(p) for p in original} != {nevra(p) for p in local}
            or any(p.reponame not in repo_ids for p in local)):
        raise ValueError('Local-only solver does not reproduce the complete selected closure')


def build_metadata(repo_id, source, destination, work, run):
    run(['createrepo_c', '--no-database', str(destination)])
    proof = {}
    for kind in ['modules', 'group']:
        if not source.get_metadata_path(kind): continue
        data = source.get_metadata_content(kind)
        data = data.encode('utf-8') if isinstance(data, str) else bytes(data)
        if not 0 < len(data) <= 128 * 1024 * 1024: raise ValueError('Original repository metadata exceeds limits')
        path = work / (repo_id + '-' + kind + '.xml'); path.write_bytes(data)
        run(['modifyrepo_c', '--mdtype=' + kind, str(path), str(destination / 'repodata')])
        proof[kind] = hashlib.sha256(data).hexdigest()
    return proof


def make_manifest(root, assets):
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink(): raise ValueError('Output symlink refused')
        if path.is_file(): files[path.relative_to(root).as_posix()] = dict(bytes=path.stat().st_size, sha256=digest(path))
        elif not path.is_dir(): raise ValueError('Output special file refused')
    value = dict(schema=1, owner='MyTellPBX', platform='rocky8.10-x86_64', files=files)
    value.update(assets)
    return value


def collect(args, release):
    import dnf
    output = create_output(args.output)
    work = create_output(output.parent / ('.' + output.name + '-collector')); work.chmod(0o700)
    logging.getLogger('dnf').addHandler(logging.NullHandler()); logging.getLogger('dnf').propagate = False
    phase = 'initialization'; source = local = None
    def status(outcome):
        (work / 'status.json').write_text(json.dumps(dict(schema=1, phase=phase, outcome=outcome)) + '\n')
    def run(argv):
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
        with (work / 'commands.log').open('ab') as log:
            log.write((Path(argv[0]).name + '\n').encode()); log.write(result.stdout); log.write(result.stderr)
        if result.returncode: raise ValueError('Native collection tool failed: ' + Path(argv[0]).name)
        return result
    try:
        phase = 'resolve'; status('running'); print('MytelPBX media: resolving the empty-root package closure', flush=True)
        source = configured_base(work / 'source', args.reposdir, args.repo, dnf_module=dnf)
        packages = resolve(source, release['roots'])
        for repo_id in args.repo:
            directory = output / 'repos' / repo_id / 'Packages'; directory.mkdir(parents=True)
            source.repos[repo_id].pkgdir = str(directory)
        phase = 'download-packages'; status('running')
        print('MytelPBX media: downloading {} resolved RPMs'.format(len(packages)), flush=True)
        source.download_packages(packages)
        phase = 'verify-signatures'; status('running')
        keydir = output / 'keys'; keydir.mkdir(); rpmdb = work / 'rpmdb'; rpmdb.mkdir()
        run(['rpm', '--dbpath', str(rpmdb), '--initdb'])
        repositories = []; metadata = {}; rpm_proof = []
        for repo_id in args.repo:
            repo = source.repos[repo_id]; key_parts = []
            if not list(repo.gpgkey): raise ValueError('Source repository has no public signing key')
            for index, url in enumerate(repo.gpgkey):
                parsed = safe_url(url); target = keydir / (repo_id + '-' + str(index) + '.asc')
                if parsed.scheme == 'file':
                    origin = Path(parsed.path).resolve()
                    origin.relative_to(Path('/etc/pki/rpm-gpg'))
                    shutil.copyfile(str(regular(origin, 2 * 1024 * 1024)), str(target))
                else: fetch_asset(url, target, None, 2 * 1024 * 1024)
                data = target.read_bytes(); require_public_key(data); key_parts.append(data.rstrip() + b'\n')
                run(['rpmkeys', '--dbpath', str(rpmdb), '--import', str(target)])
            keyring = keydir / (repo_id + '.asc'); keyring.write_bytes(b'\n'.join(key_parts))
            repositories.append(dict(id=repo_id, path='repos/' + repo_id, gpgkey='keys/' + repo_id + '.asc'))
        for package in packages:
            if package.reponame not in args.repo: raise ValueError('Package escaped the explicit repository set')
            path = stage_rpm(Path(package.localPkg()), output / 'repos' / package.reponame / 'Packages', int(package.downloadsize))
            result = run(['rpmkeys', '--dbpath', str(rpmdb), '--checksig', '--verbose', str(path)])
            require_signature(result.returncode, result.stdout.decode('utf-8', 'replace') + result.stderr.decode('utf-8', 'replace'))
            rpm_proof.append(dict(nevra=nevra(package), repository=package.reponame, sha256=digest(path), signature_verified=True))
        phase = 'metadata'; status('running')
        for repo_id in args.repo:
            metadata[repo_id] = build_metadata(repo_id, source.repos[repo_id], output / 'repos' / repo_id, work, run)
        config = work / 'local-repos'; config.mkdir()
        lines = []
        for repo in repositories:
            lines += ['[' + repo['id'] + ']', 'name=MytelPBX local closure',
                      'baseurl=' + (output / repo['path']).as_uri(), 'enabled=1', 'gpgcheck=1',
                      'gpgkey=' + (output / repo['gpgkey']).as_uri(), 'skip_if_unavailable=0', '']
        (config / 'local.repo').write_text('\n'.join(lines))
        phase = 'local-only-resolve'; status('running')
        local = configured_base(work / 'local', config, args.repo, dnf_module=dnf)
        compare_closure(packages, resolve(local, release['roots']), set(args.repo))
        for repo_id in args.repo:
            for kind, expected in metadata[repo_id].items():
                content = local.repos[repo_id].get_metadata_content(kind)
                content = content.encode('utf-8') if isinstance(content, str) else bytes(content)
                if hashlib.sha256(content).hexdigest() != expected: raise ValueError('Local modular/group metadata changed')
        phase = 'pinned-assets'; status('running')
        assets = dict(bootstrap='bootstrap/install-mytellpbx.sh', bundle='payload/mytelpbx-bundle-' + release['version'] + '.tgz',
                      desk='desk/myteldesk-' + release['desk']['version'] + '.tar.gz',
                      node='runtime/node-' + release['node']['version'] + '-linux-x64.tar.xz', wheels=[], repositories=repositories)
        for name in ['bootstrap', 'payload', 'desk', 'runtime', 'wheels', 'geoip']: (output / name).mkdir()
        for key, path in [('bootstrap', args.bootstrap), ('bundle', args.bundle), ('desk', args.desk_archive)]:
            shutil.copyfile(str(path), str(output / assets[key]))
            expected = release['desk']['sha256'] if key == 'desk' else release[key + '_sha256']
            if digest(output / assets[key]) != expected: raise ValueError('Release input changed during collection')
        node_url = 'https://nodejs.org/dist/' + release['node']['version'] + '/' + Path(assets['node']).name
        fetch_asset(node_url, output / assets['node'], release['node']['sha256'], 512 * 1024 * 1024, args.cache_dir)
        for wheel in release['vad']['packages']:
            if (not re.fullmatch(r'[A-Za-z0-9_.+-]+\.whl', wheel['filename'])
                    or urlsplit(wheel['url']).hostname != 'files.pythonhosted.org'):
                raise ValueError('Unsupported wheel source')
            name = 'wheels/' + wheel['filename']; assets['wheels'].append(name)
            fetch_asset(wheel['url'], output / name, wheel['sha256'], wheel['bytes'], args.cache_dir)
            if (output / name).stat().st_size != wheel['bytes']: raise ValueError('Pinned wheel size mismatch')
        name = 'geoip/dbip-country-lite-' + args.geoip_month + '.csv.gz'
        fetch_asset('https://download.db-ip.com/free/' + Path(name).name, output / name, args.geoip_sha256,
                    16 * 1024 * 1024, args.cache_dir if args.geoip_sha256 else None)
        if (output / name).read_bytes()[:2] != b'\x1f\x8b': raise ValueError('GeoIP source is not gzip')
        assets['geoip'] = dict(path=name, month=args.geoip_month)
        proof = dict(schema=1, platform='rocky8.10-x86_64', kernel_release=args.kernel_release,
                     roots=release['roots'], packages=sorted(rpm_proof, key=lambda x:x['nevra']), metadata=metadata,
                     local_only_resolve=True, php_stream='remi-7.4')
        (output / 'collector-proof.json').write_text(json.dumps(proof, sort_keys=True, indent=2) + '\n')
        for path in output.rglob('*'):
            if not path.is_symlink(): path.chmod(0o755 if path.is_dir() else 0o644)
        manifest = make_manifest(output, assets)
        (output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        (output / 'manifest.json').chmod(0o644)
        phase = 'complete'; status('complete')
        print(json.dumps(dict(schema=1, output=str(output), packages=len(packages), files=len(manifest['files']),
                              manifest_sha256=digest(output / 'manifest.json'), local_only_resolve=True)))
    except BaseException:
        status('failed-unproven'); raise
    finally:
        if local is not None: local.close()
        if source is not None: source.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bootstrap', type=Path, required=True); p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--desk-archive', type=Path, required=True); p.add_argument('--kernel-release', required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--repo', action='append', required=True)
    p.add_argument('--reposdir', type=Path, default=Path('/etc/yum.repos.d'))
    p.add_argument('--cache-dir', type=Path); p.add_argument('--geoip-month', required=True); p.add_argument('--geoip-sha256')
    p.add_argument('--execute', action='store_true'); p.add_argument('--lab-machine-id'); p.add_argument('--confirm-disposable-lab', action='store_true')
    args = p.parse_args()
    if (len(set(args.repo)) != len(args.repo) or any(not re.fullmatch('[A-Za-z0-9_-]+', r) for r in args.repo)
            or not re.fullmatch(r'20[0-9]{2}-(?:0[1-9]|1[0-2])', args.geoip_month)
            or (args.geoip_sha256 is not None and not re.fullmatch('[0-9a-f]{64}', args.geoip_sha256))):
        p.error('Explicit unique repository IDs and a valid data month required')
    release = inputs(args.bootstrap, args.bundle, args.desk_archive, args.kernel_release)
    if not args.execute:
        print(json.dumps(dict(schema=1, action='plan-only', roots=release['roots'], repositories=args.repo,
                              package_transaction=False, php_stream='remi-7.4', output=str(args.output))))
        return
    if (os.name != 'posix' or os.geteuid() != 0 or not args.confirm_disposable_lab
            or args.lab_machine_id != Path('/etc/machine-id').read_text().strip()
            or 'Rocky Linux release 8.10' not in Path('/etc/redhat-release').read_text()
            or os.uname().machine != 'x86_64'):
        raise ValueError('Execution requires the explicitly identified disposable Rocky8.10 x86_64 lab')
    for tool in ['rpm', 'rpmkeys', 'createrepo_c', 'modifyrepo_c']:
        if shutil.which(tool) is None: raise ValueError('Required lab build tool unavailable: ' + tool)
    collect(args, release)


if __name__ == '__main__':
    try: main()
    except Exception as error:
        raise SystemExit('MytelPBX media collection failed: ' + type(error).__name__ + '; retain the private sibling collector diagnostics')
