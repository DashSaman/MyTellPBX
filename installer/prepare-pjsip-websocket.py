#!/usr/bin/env python3
"""Prepare the native PJSIP WebSocket default during an owned fresh bootstrap.

Call prepare/activate immediately around the installer's existing retrieve_conf.
This is not an existing-PBX updater. No network calls, passwords, configuration
overrides, channel destruction, module-unload command or restart are provided.
Python 3.6 compatible. SPDX-License-Identifier: GPL-2.0-only

Native row contract: Issabel sipsettings/install.php (public seed) and
sipsettings/functions.inc.php SIP_NORMAL handling. Asterisk 16.30.0, 18.20.0,
20.12.0 channels/chan_sip.c release the SIP WebSocket callback on a changed
websocket_enabled=no reload; res_pjsip_transport_websocket.c has no reload hook.
https://github.com/asterisk/asterisk/tree/20.12.0
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
import time

ADAPTER = Path(__file__).with_name('pjsip-websocket-native.php')
MODULE = 'res_pjsip_transport_websocket.so'
ROW = ['websocket_enabled', 'no', '0', '0']
SCHEMA = [['keyword', 'varchar(50)', 'NO', '', 'PRI', ''],
          ['data', 'varchar(255)', 'NO', '', '', ''],
          ['seq', 'tinyint(1)', 'NO', '1', 'PRI', ''],
          ['type', 'tinyint(1)', 'NO', '0', 'PRI', '']]
# Native retrieve_conf creates these exact module-owned links. Unknown links,
# alternate targets and another link beneath a known target remain refused.
CONFIG_LINKS = dict((name + '.conf', '/var/www/html/admin/modules/core/etc/' + name + '.conf')
                    for name in ['func_odbc', 'pjsip', 'rtp', 'extensions', 'features',
                                 'http', 'iax', 'res_odbc', 'sip', 'sip_notify', 'udptl'])
CONFIG_LINKS.update({'cel.conf': '/var/www/html/admin/modules/cdr/etc/cel.conf',
                     'cel_odbc.conf': '/var/www/html/admin/modules/cdr/etc/cel_odbc.conf',
                     'confbridge.conf': '/var/www/html/admin/modules/conferences/etc/confbridge.conf',
                     'logger.conf': '/var/www/html/admin/modules/logfiles/etc/logger.conf'})


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False,
                                    separators=(',', ':'), sort_keys=True).encode('utf-8')).hexdigest()


def factory_rows():
    # Public sipsettings/install.php seed, including its two default RTP rows.
    codecs = [('ulaw', '1'), ('alaw', '2'), ('slin', ''), ('g726', ''),
              ('gsm', '3'), ('g729', '5'), ('ilbc', ''), ('g723', ''),
              ('g726aal2', ''), ('adpcm', ''), ('lpc10', ''), ('speex', ''),
              ('g722', ''), ('opus', '4')]
    return sorted([[key, value, str(index), '1']
                   for index, (key, value) in enumerate(codecs)] +
                  [['callevents', 'yes', '0', '0'],
                   ['rtpstart', '10000', '0', '0'], ['rtpend', '20000', '1', '0']])


def plan_rows(rows):
    if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != 4
                                       or any(not isinstance(v, str) for v in row) for row in rows):
        raise ValueError('Unknown native row shape retained')
    if any(row[0].lower() == 'websocket_enabled' for row in rows):
        return None  # An explicit native choice, including No, is not our default.
    if sorted(rows) != factory_rows():
        raise ValueError('Nonfactory SIP settings retained')
    return sorted(rows + [ROW[:]])


def private_file(path, mode=0o600):
    path = Path(path).absolute()
    if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Symlinked/nonregular installer state refused')
    metadata = path.stat()
    if os.name == 'posix' and (metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != mode):
        raise ValueError('Unsafe installer state ownership/permissions')
    return path


def write_private(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink(): private_file(path)
    fd, name = tempfile.mkstemp(prefix='.websocket-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(value, output, sort_keys=True); output.write('\n')
            output.flush(); os.fsync(output.fileno())
        os.chmod(name, 0o600)
        os.replace(name, str(path))
        if os.name == 'posix':
            directory = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
    finally:
        if os.path.exists(name): os.unlink(name)


def install_source(state, version, bundle):
    state = Path(state).absolute()
    if state.resolve() != state or not state.is_dir():
        raise ValueError('Private fresh-installer state required')
    if os.name == 'posix' and (state.stat().st_uid != os.geteuid() or stat.S_IMODE(state.stat().st_mode) != 0o700):
        raise ValueError('Unsafe installer directory')
    raw = private_file(state / 'source.json').read_bytes()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) or not re.fullmatch(r'[a-f0-9]{64}', bundle):
        raise ValueError('Exact installer source required')
    expected = dict(owner='MyTellPBX', schema=1, version=version, bundle_sha256=bundle)
    value = json.loads(raw.decode('utf-8'))
    if value != expected or type(value.get('schema')) is not int:
        raise ValueError('Installer source receipt differs')
    return hashlib.sha256(raw).hexdigest()


def run_command(argv, payload=None, timeout=30):
    result = subprocess.run(argv, input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=timeout,
                            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})
    if result.returncode:
        # Native bootstrap errors can include connection details. Never print them.
        raise ValueError('Native WebSocket bootstrap command failed; state retained')
    if len(result.stdout) > 1048576:
        raise ValueError('Unexpectedly large native bootstrap response')
    return result.stdout


def native_call(action, payload, run):
    result = run(['/usr/bin/php', str(ADAPTER), action], json.dumps(payload), timeout=30)
    value = json.loads(result)
    if not isinstance(value, dict): raise ValueError('Invalid native bootstrap result')
    return value


def idle(text):
    channels = re.findall(r'^([0-9]+) active channels?\s*$', text, re.M)
    calls = re.findall(r'^([0-9]+) active calls?\s*$', text, re.M)
    if channels != ['0'] or calls != ['0']:
        raise ValueError('Native zero calls/channels could not be established')


def pid_identity(root):
    path = Path(root) / 'run/asterisk/asterisk.pid'
    pid = path.read_text().strip()
    if not re.fullmatch('[1-9][0-9]*', pid): raise ValueError('Unknown Asterisk PID')
    proc = Path(root) / 'proc' / pid
    if (proc / 'comm').read_text().strip() != 'asterisk': raise ValueError('PID is not Asterisk')
    fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    start = fields[19]
    if not start.isdigit(): raise ValueError('Unknown Asterisk start identity')
    return dict(pid=pid, start=start)


def module_status(text):
    lines = [line for line in text.splitlines() if line.startswith(MODULE + ' ')]
    if len(lines) != 1: raise ValueError('PJSIP WebSocket module status is unavailable')
    match = re.search(r'\s[0-9]+\s+(Not Running|Running)\s+\S+\s*$', lines[0])
    if not match: raise ValueError('PJSIP WebSocket module status is unknown')
    return match.group(1)


def validate_snapshot(value):
    if set(value) != {'rows', 'columns', 'primary', 'engine', 'counts', 'transaction', 'autocommit'}:
        raise ValueError('Unknown native snapshot')
    if value['columns'] != SCHEMA or value['primary'] != ['keyword', 'seq', 'type'] or value['engine'] != 'InnoDB':
        raise ValueError('Unknown native SIP schema retained')
    if value['counts'] != {'devices': 0, 'users': 0, 'trunks': 0} or any(type(v) is not int for v in value['counts'].values()):
        raise ValueError('Existing native devices/users/trunks retained')
    if type(value['transaction']) is not int or value['transaction'] != 0 or value['autocommit'] is not True:
        raise ValueError('Native transaction ownership is unavailable')
    plan_rows(value['rows'])  # Validate shape, including when the operator chose a value.


def config_input(root, path):
    if path.is_symlink():
        target = os.readlink(str(path))
        if CONFIG_LINKS.get(path.name) != target:
            raise ValueError('Unknown native configuration link retained')
        path = Path(root) / target.lstrip('/')
        if path.resolve() != path.absolute():
            raise ValueError('Redirected native configuration target retained')
    if not path.is_file() or not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > 2097152:
        raise ValueError('Unknown native configuration file retained')
    return path


def overrides(root, generated=False):
    directory = Path(root) / 'etc/asterisk'
    seen = []
    for path in sorted(directory.glob('*.conf')):
        source = config_input(root, path)
        for line in source.read_text(errors='strict').splitlines():
            if re.match(r'^\s*websocket_enabled\s*(?:=>|=)', line, re.I):
                seen.append((path.name, line))
            if re.match(r'^\s*noload\s*(?:=>|=)\s*res_pjsip_transport_websocket(?:\.so)?\s*(?:;.*)?$', line, re.I):
                return True
    if generated:
        return len(seen) != 1 or seen[0][0] != 'sip_general_additional.conf' or re.fullmatch(
            r'\s*websocket_enabled\s*(?:=>|=)\s*no\s*(?:;.*)?', seen[0][1], re.I) is None
    return bool(seen)


def platform(root, run):
    text = (Path(root) / 'etc/os-release').read_text()
    values = dict(re.findall(r'^([A-Z_]+)="?([^"\n]+)"?$', text, re.M))
    if values.get('ID') != 'rocky' or not re.fullmatch(r'8(?:\.[0-9]+)?', values.get('VERSION_ID', '')):
        raise ValueError('Only the owned Rocky Linux 8 bootstrap is supported')
    version = run(['/usr/sbin/asterisk', '-rx', 'core show version'])
    if not re.match(r'^Asterisk (?:16|18|20)\.[0-9]+(?:\.[0-9]+)?\b', version):
        raise ValueError('Unsupported native Asterisk version')
    idle(run(['/usr/sbin/asterisk', '-rx', 'core show channels count']))
    return pid_identity(root)


def execute(phase, root, state, version, bundle, run=run_command, native=native_call, sleep=time.sleep):
    state = Path(state).absolute()
    source = install_source(state, version, bundle)
    machine = (Path(root) / 'etc/machine-id').read_text().strip()
    if not re.fullmatch('[0-9a-f]{32}', machine): raise ValueError('Unknown machine identity')
    journal_path = state / 'pjsip-websocket.json'
    journal = None
    if journal_path.exists() or journal_path.is_symlink():
        journal = json.loads(private_file(journal_path).read_text())
        if (not isinstance(journal, dict) or journal.get('owner') != 'MyTellPBX' or type(journal.get('schema')) is not int
                or journal.get('schema') != 1 or journal.get('source_sha256') != source or journal.get('machine_id') != machine
                or journal.get('phase') not in ['prepared', 'ready', 'skipped']):
            raise ValueError('Unknown WebSocket bootstrap receipt retained')
        if journal['phase'] in ['ready', 'skipped']:
            return 'completed; not reapplied' if journal['phase'] == 'ready' else 'skipped'
    completed = state / 'stages/framework.done'
    if completed.exists() or completed.is_symlink():
        raise ValueError('Completed framework is not a fresh WebSocket bootstrap')
    identity = platform(root, run)
    snapshot = native('snapshot', {}, run)
    validate_snapshot(snapshot)
    if journal is None:
        if phase != 'prepare': raise ValueError('Fresh prepare intent is required')
        after = plan_rows(snapshot['rows'])
        if after is None or overrides(root):
            journal = dict(owner='MyTellPBX', schema=1, source_sha256=source, machine_id=machine, phase='skipped')
            write_private(journal_path, journal)
            return 'skipped'
        journal = dict(owner='MyTellPBX', schema=1, source_sha256=source, machine_id=machine,
                       phase='prepared', before=snapshot, after_rows=after, identity=identity)
        write_private(journal_path, journal)  # Durable private preimage BEFORE the one native write.
    if journal.get('identity') != identity or journal.get('after_rows') != sorted(factory_rows() + [ROW]):
        raise ValueError('Owned bootstrap identity/preimage changed')
    validate_snapshot(journal['before'])
    if journal['before']['rows'] != factory_rows(): raise ValueError('Unknown bootstrap preimage')
    current = sorted(snapshot['rows'])
    if phase == 'prepare':
        if current == factory_rows():
            if overrides(root): raise ValueError('Native choice changed after bootstrap intent')
            result = native('insert', {'before_rows_sha256': digest(factory_rows())}, run)
            validate_snapshot(result)
            if sorted(result['rows']) != journal['after_rows']:
                raise ValueError('Native WebSocket write outcome is unknown; intent retained')
        elif current != journal['after_rows']:
            raise ValueError('Native settings changed after bootstrap intent')
        if pid_identity(root) != identity: raise ValueError('Asterisk process changed during preparation')
        return 'prepared'
    if phase != 'activate' or current != journal['after_rows'] or overrides(root, generated=True):
        raise ValueError('Native generated WebSocket setting is not the owned No value')
    run(['/usr/sbin/asterisk', '-rx', 'sip reload'])
    # sip reload is asynchronous. Retry only this previously nonrunning module,
    # with a finite four-attempt budget; no global reload/unload/restart fallback.
    for delay in [0.5, 1.0, 2.0, 3.0]:
        sleep(delay)
        if pid_identity(root) != identity: raise ValueError('Asterisk process changed during activation')
        idle(run(['/usr/sbin/asterisk', '-rx', 'core show channels count']))
        status = module_status(run(['/usr/sbin/asterisk', '-rx', 'module show like ' + MODULE]))
        if status == 'Running': break
        try: run(['/usr/sbin/asterisk', '-rx', 'module load ' + MODULE])
        except ValueError: pass  # A still-occupied subprotocol may decline during the queued SIP reload.
    if module_status(run(['/usr/sbin/asterisk', '-rx', 'module show like ' + MODULE])) != 'Running':
        raise ValueError('PJSIP WebSocket module did not become Running; prepared state retained')
    final = native('snapshot', {}, run)
    validate_snapshot(final)
    if sorted(final['rows']) != journal['after_rows'] or pid_identity(root) != identity:
        raise ValueError('Native bootstrap preservation could not be confirmed')
    idle(run(['/usr/sbin/asterisk', '-rx', 'core show channels count']))
    journal['phase'] = 'ready'
    write_private(journal_path, journal)
    return 'ready'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'activate'])
    parser.add_argument('--state-dir', type=Path, default=Path('/var/lib/mytelpbx-installer'))
    parser.add_argument('--version', required=True)
    parser.add_argument('--bundle-sha256', required=True)
    args = parser.parse_args()
    if not hasattr(os, 'geteuid') or os.geteuid() != 0: parser.error('root required')
    print('MyTellPBX PJSIP WebSocket bootstrap: ' + execute(args.phase, Path('/'), args.state_dir,
                                                           args.version, args.bundle_sha256))


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        print('MyTellPBX WebSocket bootstrap refused; native state and private intent retained.', file=sys.stderr)
        sys.exit(1)
