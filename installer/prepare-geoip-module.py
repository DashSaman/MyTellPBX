#!/usr/bin/env python3
"""Prepare the native GeoIP kernel consumer without touching firewall rules.

Only a namespaced modules-load file and public consumer receipt are written.
Unknown managed files are preserved by refusal. Root-owned OS directories are
trusted against concurrent replacement by another root process. Python3.6.
The CLI is root/Linux only; injected roots/commands are for isolated fixtures.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

LOADER = 'etc/modules-load.d/mytellpbx-geoip.conf'
STATUS = 'usr/share/mytellpbx-geoip/module-status.json'
LOADER_BYTES = b'# MyTellPBX managed GeoIP kernel consumer v1\nxt_geoip\n'
SCHEMA = 'mytellpbx-geoip-module/1'
KEYS = {'schema','owner','module','state','running_kernel','target_kernel','loaded','persistent','module_sha256'}


def kernel_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{1,127}', value):
        raise ValueError('Invalid kernel release')
    return value


def run_command(arguments):
    try:
        return subprocess.run(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=15,
                              env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C','LC_ALL':'C'})
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('GeoIP module metadata/load command unavailable or timed out') from error


def trusted(path, directory=False):
    info = path.lstat()
    if path.is_symlink() or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError('Redirected or nonregular managed GeoIP input')
    if os.name == 'posix' and (info.st_uid != os.geteuid() or info.st_mode & 0o022):
        raise ValueError('Unsafe managed GeoIP owner or permissions')
    return info


def managed(root, relative):
    path = root
    for part in Path(relative).parts[:-1]:
        path = path / part
        if path.is_symlink(): raise ValueError('Symlinked managed GeoIP ancestor')
        if not path.exists():
            path.mkdir(mode=0o755); path.chmod(0o755)
        trusted(path, True)
    return path / Path(relative).name


def valid_status(value):
    if not isinstance(value, dict) or set(value) != KEYS:
        return False
    if value['schema'] != SCHEMA or value['owner'] != 'MyTellPBX' or value['module'] != 'xt_geoip':
        return False
    if value['state'] not in ['ready','pending-reboot','unavailable']:
        return False
    try:
        kernel_name(value['running_kernel'])
        if value['target_kernel'] is not None: kernel_name(value['target_kernel'])
    except ValueError: return False
    if type(value['loaded']) is not bool or type(value['persistent']) is not bool:
        return False
    if value['module_sha256'] is not None and (not isinstance(value['module_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', value['module_sha256'])):
        return False
    if value['state'] == 'ready':
        return value['loaded'] and value['persistent'] and value['target_kernel'] == value['running_kernel'] and value['module_sha256'] is not None
    if value['state'] == 'pending-reboot':
        return not value['loaded'] and value['persistent'] and value['target_kernel'] is not None and value['target_kernel'] != value['running_kernel'] and value['module_sha256'] is not None
    return True


def current_bytes(path):
    if path.is_symlink(): raise ValueError('Symlinked managed GeoIP file')
    if not path.exists(): return None
    if trusted(path).st_size > 8192: raise ValueError('Oversized managed GeoIP file')
    return path.read_bytes()


def publish(path, data, previous):
    if previous == data: return
    fd, name = tempfile.mkstemp(prefix='.mytell-geoip-', dir=str(path.parent))
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush()
            if hasattr(os, 'fchmod'): os.fchmod(stream.fileno(), 0o644)
            os.fsync(stream.fileno())
        if not hasattr(os, 'fchmod'): temporary.chmod(0o644)
        if current_bytes(path) != previous: raise ValueError('Managed GeoIP file changed before publication')
        if previous is None:
            os.link(str(temporary), str(path))  # Never clobber a newly appearing owner file.
        else:
            os.replace(str(temporary), str(path))
    finally:
        if temporary.exists(): temporary.unlink()


def loaded(root):
    return any(line.split() and line.split()[0] == 'xt_geoip'
               for line in (root / 'proc/modules').read_text().splitlines())


def module_info(root, kernel, command):
    results = {}
    for field in ['name','vermagic','filename']:
        result = command(['/usr/sbin/modinfo','-k',kernel,'-F',field,'xt_geoip'])
        if len(result.stdout) + len(result.stderr) > 8192:
            raise ValueError('Oversized GeoIP module metadata')
        if result.returncode:
            if field == 'name' and re.fullmatch(rb'modinfo: ERROR: Module (?:alias )?xt_geoip not found\.\s*', result.stderr):
                return None
            raise ValueError('Cannot verify installed GeoIP module metadata')
        results[field] = result.stdout.decode('ascii').strip()
    if results['name'] != 'xt_geoip' or not results['vermagic'].split() or results['vermagic'].split()[0] != kernel:
        raise ValueError('GeoIP module does not match its target kernel')
    filename = results['filename']
    if not filename.startswith(('/lib/modules/','/usr/lib/modules/')):
        raise ValueError('GeoIP module is outside the installed module tree')
    path = (root / filename.lstrip('/')).resolve()
    tree = (root / 'lib/modules').resolve()
    if tree not in path.parents or not re.fullmatch(r'xt_geoip\.ko(?:\.(?:xz|gz|zst))?', path.name):
        raise ValueError('Unexpected installed GeoIP module file')
    if trusted(path).st_size > 32 * 1024 * 1024: raise ValueError('Oversized installed GeoIP module')
    for directory in [tree] + [parent for parent in path.parents if tree in parent.parents]:
        trusted(directory, True)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root, running_kernel, command=run_command):
    root = Path(root).resolve(); running_kernel = kernel_name(running_kernel)
    loader = managed(root, LOADER); status = managed(root, STATUS)
    before_loader, before_status = current_bytes(loader), current_bytes(status)
    if before_loader not in [None, LOADER_BYTES]:
        raise ValueError('Unknown modules-load configuration retained')
    if before_status is not None:
        try: owned = valid_status(json.loads(before_status.decode('utf-8')))
        except (ValueError, UnicodeError): owned = False
        if not owned: raise ValueError('Unknown public GeoIP module receipt retained')
    value = dict(schema=SCHEMA, owner='MyTellPBX', module='xt_geoip', state='unavailable',
                 running_kernel=running_kernel, target_kernel=None, loaded=False,
                 persistent=before_loader is not None, module_sha256=None)
    try:
        checksum = module_info(root, running_kernel, command)
        target = running_kernel
        if checksum is None:
            if loaded(root): raise ValueError('Loaded GeoIP module has no verifiable installed counterpart')
            result = command(['/usr/sbin/grubby','--default-kernel'])
            if result.returncode or len(result.stdout) > 4096: raise ValueError('Cannot verify next boot kernel')
            boot = result.stdout.decode('ascii').strip()
            if not boot.startswith('/boot/vmlinuz-'): raise ValueError('Unknown default kernel image')
            target = kernel_name(boot[len('/boot/vmlinuz-'):])
            if target == running_kernel: raise ValueError('No newer configured kernel with a verified GeoIP module')
            trusted(root / boot.lstrip('/'))
            checksum = module_info(root, target, command)
            if checksum is None: raise ValueError('No verified GeoIP module for the next boot kernel')
        value.update(target_kernel=target, module_sha256=checksum)
        publish(loader, LOADER_BYTES, before_loader)
        value['persistent'] = True
        if target == running_kernel:
            if not loaded(root):
                result = command(['/usr/sbin/modprobe','xt_geoip'])
                if result.returncode: raise ValueError('Matching GeoIP module failed to load')
            if not loaded(root): raise ValueError('GeoIP module load was not observed')
            value.update(state='ready', loaded=True)
        else:
            value['state'] = 'pending-reboot'
    except (ValueError, OSError, UnicodeError):
        publish(status, (json.dumps(value, sort_keys=True) + '\n').encode('utf-8'), before_status)
        raise
    publish(status, (json.dumps(value, sort_keys=True) + '\n').encode('utf-8'), before_status)
    return value


def main():
    if os.name != 'posix' or os.geteuid() != 0:
        raise ValueError('GeoIP kernel preparation requires Linux root')
    result = prepare(Path('/'), os.uname().release)
    print(json.dumps(result, sort_keys=True))
    if result['state'] == 'pending-reboot':
        print('MyTellPBX GeoIP: country data is separate; restart into the verified kernel to enable country matching.', file=sys.stderr)


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError) as error:
        print('GeoIP kernel consumer unavailable: ' + str(error), file=sys.stderr)
        sys.exit(1)
