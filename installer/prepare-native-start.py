#!/usr/bin/env python3
"""Interlock owned fresh initialization before RPMs can start native services.

Only systemd metadata and daemon-reload are used. The real installer source,
native templates and repaired install_amp precede the config-prepared receipt;
that receipt is not a claim of daemon health or completed framework setup.
Python 3.6 compatible. SPDX-License-Identifier: GPL-2.0-only
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

PROFILE = {'amp_sha': '799ba95ba7c068a9f14d535ddec68d988d33af01a85ecee3b83d9f1921d4fd22',
 'config_links': {'cel.conf': '/var/www/html/admin/modules/cdr/etc/cel.conf',
                  'cel_odbc.conf': '/var/www/html/admin/modules/cdr/etc/cel_odbc.conf',
                  'confbridge.conf': '/var/www/html/admin/modules/conferences/etc/confbridge.conf',
                  'extensions.conf': '/var/www/html/admin/modules/core/etc/extensions.conf',
                  'features.conf': '/var/www/html/admin/modules/core/etc/features.conf',
                  'func_odbc.conf': '/var/www/html/admin/modules/core/etc/func_odbc.conf',
                  'http.conf': '/var/www/html/admin/modules/core/etc/http.conf',
                  'iax.conf': '/var/www/html/admin/modules/core/etc/iax.conf',
                  'logger.conf': '/var/www/html/admin/modules/logfiles/etc/logger.conf',
                  'pjsip.conf': '/var/www/html/admin/modules/core/etc/pjsip.conf',
                  'res_odbc.conf': '/var/www/html/admin/modules/core/etc/res_odbc.conf',
                  'rtp.conf': '/var/www/html/admin/modules/core/etc/rtp.conf',
                  'sip.conf': '/var/www/html/admin/modules/core/etc/sip.conf',
                  'sip_notify.conf': '/var/www/html/admin/modules/core/etc/sip_notify.conf',
                  'udptl.conf': '/var/www/html/admin/modules/core/etc/udptl.conf'},
 'service_sha': 'dba4f4107b1a23f736f793600ee81134f638a94ebb10bc991658eaa72dd8ee53',
 'templates': {'cbmysql.conf': 'cd4f9ea4dee91932093bccd5aa080a730852e8d6c8f964937fd44caf56c1dad1',
               'cdr_mysql.conf': '0323f38e0c22df48abe348266dfac984d9b50d41e653dd735a52d51603003e7a',
               'dnsmgr.conf': '0e2455c089a48cf2f6bbfb7989582f9f116f662938bfc801d553393b9bf03d0f',
               'enum.conf': 'aa95334cf06e9d09cde25437351f5579fc8eaed27de80d5f6a242424da030efd',
               'indications.conf': '709d5ae34cd9242d0ec5a2e18bf27291bef6c8f05297473d0cdba7289f97b2f1',
               'issabelpbx_module_admin.conf': '67fd2222626686d5f6174aac8ccb4ffa1c56bf4b26ca5c32bc5ed43281c8a81a',
               'manager.conf': '04f2f8ff4aa9d55a2125cca04dc7e41a8d5ca5c1890067d14660fc61688ef98e',
               'manager_general_additional.conf': '2d2041149758f5bd4dd7460277aa087af3ce4c8f234b22da00dbd7291eb8dfc1',
               'meetme.conf': '63fc59b09110d9d3f28c356577d0fc5e6dab4a0f78bbe7fe753d1211396849bf',
               'modem.conf': '65b4cec2ac1df10c54bcbf78c51b75245678b9cbeb594463d9bea2fed76ca23b',
               'modules.conf': '012ccd122255f3376e7827861d3a44f4f5b7f86ef6f0e6890c931aeba7f670b4',
               'modules_additional.conf': '6b182ecaeab904aee714d5a4e11267918830e0522ba9faa1a00af8568c05aaf7',
               'musiconhold.conf': '517e6d3373f3e5dd0da0e42a1f0deb39cc6f25c5351ace06a36ad51d1d406f84',
               'phone.conf': 'd738fffa094424b56a4fefbb743674fcc718317eedc4a9f322cf5c92b6aa0047',
               'phpagi.conf': 'e87e580d51f3b9c9b9068b4a8418ec9d5227d0de3dd13a094ddad02a1144169d',
               'privacy.conf': 'e3def1330c5e5b4db6de4b1b21851a54bc23fce96f160df95d3e6d6bf866cbf7',
               'queues.conf': 'b38ec8f8c45c62322da14b47c79ea818357ea1ff48652c40d387f397cf020410',
               'res_mysql.conf': '729cd42cf199d2ae4c546dbf65bd6d346acae2763b2ff9607c338ebb1b6b4fe6',
               'res_parking.conf': 'b9e3f3a127755f3cb8644331254bfd4be323ce3ed6bb00635dd5abe6afac8678',
               'res_parking_additional.conf': '60fb776fdf23ee5ad2d70b2d01bde253c121e30f0478f36acc7f17c17a65c93b'},
 'units': {'amportal-reload.service': 'efb0ce163bfc2912c415c6726a11043c398364927fd32652c5db3aed96399b56',
           'asterisk.service': 'abe0a418748d0742e7e10d719ec99eac5f4b0ef239a2af10e7ebff07eb3d9136',
           'issabel-firstboot.service': '6915cde879fc4eacdfb4162f615171927b11b5ea8a62519c1473077fa099d50c'}}
STATE = '/var/lib/mytelpbx-installer'
TEMPLATES = '/usr/src/issabelPBX/framework/amp_conf/astetc'
AMP = '/usr/src/issabelPBX/framework/install_amp'
PROBE = '--property=Id,LoadState,ActiveState,SubState,MainPID,NRestarts,ControlGroup,DropInPaths,FragmentPath'
CONDITIONS = {
    'asterisk.service': STATE + '/config-prepared.json',
    'issabel-firstboot.service': '!' + STATE + '/source.json',
    'amportal-reload.service': STATE + '/stages/framework.done',
}
ISO_CONDITION = (b'[Unit]\n# The verified MytelPBX media workflow owns first initialization and resume.\n'
                 b'# This is the real persistent depot, not a fabricated framework completion.\n'
                 b'ConditionPathExists=!/var/lib/mytelpbx-media/manifest.json\n')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


class Context:
    def __init__(self, root=Path('/'), version='', bundle='', uid=0,
                 ast_uid=None, ast_gid=None, run=None):
        self.root = Path(root).absolute()
        self.version, self.bundle, self.uid = version, bundle, uid
        self.ast_uid, self.ast_gid = ast_uid, ast_gid
        self.run = run or subprocess.run

    def path(self, absolute):
        return self.root / absolute.lstrip('/')

    def directory(self, path, create=False, private=False):
        path = Path(path)
        relative = path.relative_to(self.root)
        current = self.root
        for part in relative.parts:
            current = current / part
            if not current.exists() and not current.is_symlink() and create:
                current.mkdir(mode=0o700 if current == path and private else 0o755)
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError('Native directory is not a real directory')
            if os.name == 'posix':
                owners = (self.uid,) if private else (self.uid, self.ast_uid)
                if info.st_uid not in owners or info.st_mode & 0o002:
                    raise ValueError('Untrusted native directory retained')
                if current == path and private and stat.S_IMODE(info.st_mode) != 0o700:
                    raise ValueError('Installer state must remain private')
        return path

    def read(self, path, private=False):
        path = Path(path)
        self.directory(path.parent, private=private)
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError('Nonregular native file retained')
        fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > 2097152:
                raise ValueError('Unknown native file type/size retained')
            if os.name == 'posix' and (before.st_uid not in (self.uid, None if private else self.ast_uid)
                                       or before.st_mode & 0o002
                                       or (private and stat.S_IMODE(before.st_mode) != 0o600)):
                raise ValueError('Unsafe native file metadata retained')
            raw = b''
            while len(raw) <= 2097152:
                chunk = os.read(fd, 65536)
                if not chunk: break
                raw += chunk
            after = os.fstat(fd); leaf = path.lstat()
            if len(raw) != before.st_size or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or (
                    after.st_dev, after.st_ino) != (leaf.st_dev, leaf.st_ino):
                raise ValueError('Native file changed during validation')
            return raw
        finally:
            os.close(fd)

    def publish(self, path, raw, mode=0o600, ast=False):
        path = Path(path); parent = self.directory(path.parent)
        identity = parent.stat()
        fd, name = tempfile.mkstemp(prefix='.mytel-native-', dir=str(parent))
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(raw); output.flush(); os.fchmod(output.fileno(), mode)
                if ast and os.name == 'posix': os.fchown(output.fileno(), self.ast_uid, self.ast_gid)
                os.fsync(output.fileno())
            now = parent.lstat()
            if (identity.st_dev, identity.st_ino) != (now.st_dev, now.st_ino):
                raise ValueError('Native publication parent changed')
            # Never replace a leaf that appeared after validation.
            os.link(name, str(path))
            fsync_dir(parent)
        finally:
            if os.path.exists(name): os.unlink(name)


def fsync_dir(path):
    if os.name == 'posix':
        fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)


def exists(path):
    return path.exists() or path.is_symlink()


def foreign_initializers(ctx):
    found = []
    for path in ctx.path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if any(Path(os.fsdecode(arg)).name in ('install_amp', 'issabel-admin-passwords') for arg in args[:3] if arg):
            found.append(int(path.parent.name))
    return found


def source(ctx):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', ctx.version) or not re.fullmatch(r'[a-f0-9]{64}', ctx.bundle):
        raise ValueError('Exact installer source required')
    raw = ctx.read(ctx.path(STATE + '/source.json'), private=True)
    expected = dict(owner='MyTellPBX', schema=1, version=ctx.version, bundle_sha256=ctx.bundle)
    value = json.loads(raw.decode('utf-8'))
    if value != expected or type(value.get('schema')) is not int:
        raise ValueError('Installer source receipt differs')
    return dict(expected, source_sha256=sha(raw), profile_sha256=sha(encoded(PROFILE)))


def record(ctx, name, expected):
    path = ctx.path(STATE + '/' + name)
    if not exists(path): return False
    value = json.loads(ctx.read(path, private=True).decode('utf-8'))
    if value != expected or type(value.get('schema')) is not int:
        raise ValueError('Foreign or changed native-start receipt retained')
    return True


def dropin(unit):
    return ('[Unit]\n# MytelPBX owned fresh initialization; no service command override.\n'
            'ConditionPathExists=' + CONDITIONS[unit] + '\n').encode('ascii')


def dropin_path(ctx, unit):
    return ctx.path('/etc/systemd/system/' + unit + '.d/20-mytel-native-start.conf')


def commands(ctx, args):
    result = ctx.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
                     stdin=subprocess.DEVNULL, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})
    if result.returncode or result.stderr or len(result.stdout) > 65536:
        raise ValueError('Native systemd metadata/reload failed; state retained')
    return result.stdout.decode('ascii')


def dispatch(ctx, required=False):
    for name in ('/etc/init.d/asterisk', '/etc/rc.d/init.d/asterisk',
                 '/usr/libexec/initscripts/legacy-actions/asterisk/start'):
        if exists(ctx.path(name)):
            raise ValueError('Unknown legacy Asterisk dispatch retained')
    path = ctx.path('/usr/sbin/service')
    if required or exists(path):
        if sha(ctx.read(path)) != PROFILE['service_sha']:
            raise ValueError('Unknown native service dispatch retained')


def units(ctx, owned=False, required=False, prepared=False, loaded_required=True):
    if foreign_initializers(ctx):
        raise ValueError('Another native initializer is active; not adopted')
    for unit in CONDITIONS:
        vendor = ctx.path('/usr/lib/systemd/system/' + unit)
        if required or exists(vendor):
            if sha(ctx.read(vendor)) != PROFILE['units'][unit]:
                raise ValueError('Unknown native unit retained')
        directory = ctx.path('/etc/systemd/system/' + unit + '.d')
        if any(exists(ctx.path(base + unit)) for base in ('/etc/systemd/system/', '/run/systemd/system/')):
            raise ValueError('Unknown native unit override retained')
        if exists(directory):
            ctx.directory(directory)
            for path in directory.glob('*.conf'):
                if path == dropin_path(ctx, unit) and owned and ctx.read(path) == dropin(unit): continue
                if unit == 'issabel-firstboot.service' and path.name == '10-mytel-media.conf' and ctx.read(path) == ISO_CONDITION: continue
                raise ValueError('Unknown native drop-in retained')
        text = commands(ctx, ['systemctl', 'show', unit, PROBE])
        lines = text.splitlines()
        values = dict(line.split('=', 1) for line in lines if '=' in line)
        if len(values) != len(lines) or set(values) != set(PROBE[len('--property='):].split(',')) or values['Id'] != unit:
            raise ValueError('Unexpected native unit metadata')
        if values['LoadState'] not in ('loaded', 'not-found') or (required and values['LoadState'] != 'loaded'):
            raise ValueError('Native unit not loaded')
        if values['LoadState'] == 'loaded' and values['FragmentPath'] != str(vendor):
            raise ValueError('Unknown loaded native unit fragment retained')
        if values['NRestarts'] != '0':
            raise ValueError('Recovered native restart is not fresh readiness')
        active = values['ActiveState']
        if active != 'inactive' or values['MainPID'] != '0':
            if not (unit == 'asterisk.service' and prepared and active == 'active'
                    and re.fullmatch(r'[1-9][0-9]*', values['MainPID'])
                    and values['SubState'] == 'running' and values['ControlGroup'] == '/system.slice/asterisk.service'):
                raise ValueError('Unowned or incomplete native service is active')
        if owned and loaded_required and values['LoadState'] == 'loaded':
            loaded = values['DropInPaths'].split()
            if str(dropin_path(ctx, unit)) not in loaded:
                raise ValueError('Native interlock is not loaded')
            allowed = {str(dropin_path(ctx, unit))}
            if unit == 'issabel-firstboot.service': allowed.add(str(directory / '10-mytel-media.conf'))
            if set(loaded) - allowed: raise ValueError('Unknown loaded native drop-in retained')


def hold(ctx):
    identity = source(ctx)
    intent = dict(identity, purpose='native-first-start', phase='held')
    ready = dict(identity, purpose='native-config-prepared')
    owned = record(ctx, 'native-start.json', intent)
    prepared = record(ctx, 'config-prepared.json', ready)
    if prepared and not owned: raise ValueError('Prepared receipt without owned intent')
    dispatch(ctx); units(ctx, owned=owned, prepared=prepared, loaded_required=False)
    if prepared:
        directory, _, needed = validate_configs(ctx)
        if any(not exists(directory / name) for name in needed):
            raise ValueError('Previously prepared native include disappeared')
    if not owned: ctx.publish(ctx.path(STATE + '/native-start.json'), encoded(intent))
    for unit in CONDITIONS:
        path = dropin_path(ctx, unit)
        ctx.directory(path.parent, create=True)
        if not exists(path): ctx.publish(path, dropin(unit), mode=0o644)
        elif ctx.read(path) != dropin(unit): raise ValueError('Native interlock changed')
    commands(ctx, ['systemctl', 'daemon-reload'])
    units(ctx, owned=True, prepared=prepared)
    return ready


def includes(raw):
    if b'\0' in raw: raise ValueError('NUL in native configuration retained')
    names = set()
    for line in raw.splitlines():
        match = re.match(br'^\s*#include\s+([^;]+)', line)
        if not match: continue
        value = match.group(1).strip()
        if len(value) >= 2 and value[:1] == value[-1:] and value[:1] in (b'"', b"'"):
            value = value[1:-1]
        if not re.fullmatch(br'[A-Za-z0-9_][A-Za-z0-9_.-]*\.conf', value):
            raise ValueError('Nonlocal or dynamic required native include retained')
        names.add(value.decode('ascii'))
    return names


def live_read(ctx, path):
    if path.is_symlink():
        expected = PROFILE['config_links'].get(path.name)
        if not expected or os.readlink(str(path)) != expected:
            raise ValueError('Unknown native config link retained')
        return ctx.read(ctx.path(expected))
    return ctx.read(path)


def validate_configs(ctx):
    dispatch(ctx, required=True)
    if sha(ctx.read(ctx.path(AMP))) != PROFILE['amp_sha']:
        raise ValueError('Native include-order repair is required before startup')
    templates = {}
    required = set()
    for name, digest in PROFILE['templates'].items():
        raw = ctx.read(ctx.path(TEMPLATES + '/' + name))
        if sha(raw) != digest: raise ValueError('Unrecognized native template retained')
        templates[name] = raw; required.update(includes(raw))
    directory = ctx.directory(ctx.path('/etc/asterisk'))
    if not exists(directory / 'modules.conf'): raise ValueError('Native modules.conf is missing')
    paths = list(directory.glob('*.conf'))
    if len(paths) > 512: raise ValueError('Native configuration file bound exceeded')
    for path in paths: required.update(includes(live_read(ctx, path)))
    if len(required) > 256: raise ValueError('Native include bound exceeded')
    if ctx.ast_uid is None or ctx.ast_gid is None: raise ValueError('Native service identity required')
    # Validate the full graph before creating any missing leaf. Supplied include
    # defaults (notably res_parking_additional) retain their native content.
    pending = set(required); seen = set()
    while pending:
        name = pending.pop()
        if name in seen: continue
        seen.add(name)
        if len(seen) > 256: raise ValueError('Native include graph bound exceeded')
        path = directory / name
        raw = live_read(ctx, path) if exists(path) else templates.get(name, b'')
        pending.update(includes(raw) - seen)
    return directory, templates, seen


def prepare_configs(ctx):
    identity = source(ctx)
    intent = dict(identity, purpose='native-first-start', phase='held')
    ready = dict(identity, purpose='native-config-prepared')
    if not record(ctx, 'native-start.json', intent): raise ValueError('Owned native hold required')
    prepared = record(ctx, 'config-prepared.json', ready)
    units(ctx, owned=True, required=True, prepared=prepared)
    directory, templates, seen = validate_configs(ctx)
    if prepared and any(not exists(directory / name) for name in seen):
        raise ValueError('Previously prepared native include disappeared; no repair while active')
    units(ctx, owned=True, required=True, prepared=prepared)
    for name in sorted(seen):
        path = directory / name
        if not exists(path): ctx.publish(path, templates.get(name, b''), mode=0o644, ast=True)
        includes(live_read(ctx, path))
    fsync_dir(directory)
    if source(ctx) != identity: raise ValueError('Installer source changed during preparation')
    units(ctx, owned=True, required=True, prepared=prepared)
    if not prepared: ctx.publish(ctx.path(STATE + '/config-prepared.json'), encoded(ready))
    return ready


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--hold', action='store_true')
    operation.add_argument('--prepare-config', action='store_true')
    parser.add_argument('--version', required=True)
    parser.add_argument('--bundle-sha256', required=True)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise ValueError('Native lifecycle CLI requires Linux root')
    ast_uid = ast_gid = None
    import pwd
    try:
        account = pwd.getpwnam('asterisk'); ast_uid, ast_gid = account.pw_uid, account.pw_gid
    except KeyError:
        if args.prepare_config: raise ValueError('Native service identity is absent')
    ctx = Context(version=args.version, bundle=args.bundle_sha256, ast_uid=ast_uid, ast_gid=ast_gid)
    if args.hold: hold(ctx)
    else: prepare_configs(ctx)
    print('Native startup interlock verified' if args.hold else 'Native configuration prepared; readiness remains required')


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError):
        print('Native startup preparation refused; existing state retained', file=sys.stderr)
        sys.exit(1)
