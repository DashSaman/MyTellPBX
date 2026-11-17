#!/usr/bin/env python3
"""Mytel presentation and pinned Desk addons AFTER a successful native Issabel.

No native initializer, password reset, SIP/dialplan, firewall, network or global
TLS changes. Python 3.6+ standard library. Both official netinstall and ISO call
the same hook; supplemental offline inputs use the existing sealed media format.
"""
import argparse
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
NATIVE_GEOIP_STATUS_SHA256 = 'de1fb7c39ec9b67859d4346e90c90a8fb440d32ea16dcb1437c1024fd8bfa34a'
BRAND_KEYS = {
    'BRAND_ALT_JS': 'assets/mytel/sub.js?v=25',
    'BRAND_CSS_CUSTOM': 'assets/mytel/skin.css?v=28',
    'BRAND_TITLE': 'MytelPBX',
    'BRAND_ISSABELPBX_ALT_FOOT': 'MytelPBX',
    'BRAND_ISSABELPBX_ALT_LEFT': 'MytelPBX',
    'BRAND_IMAGE_FAVICON': 'images/mytel-favicon.png',
    'BRAND_IMAGE_ISSABELPBX_FOOT': 'images/mytel-foot.png',
    'BRAND_IMAGE_TANGO_LEFT': 'images/mytel-emblem-48.png',
    'BRAND_IMAGE_ISSABELPBX_LINK_FOOT': 'https://mytel.one',
    'BRAND_IMAGE_ISSABELPBX_LINK_LEFT': 'https://mytel.one',
}
# All other prerequisites are supplied by the native Issabel base. The sealed
# supplemental repository may contain a broader archive; never let it replace
# native PBX/PHP/database/kernel packages while provisioning Desk's interpreter.
SUPPLEMENTAL_PACKAGES = ('python3.11', 'python3.11-libs', 'python3.11-pip',
                         'python3.11-pip-wheel', 'python3.11-setuptools',
                         'python3.11-setuptools-wheel', 'mpdecimal')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.resolve() != path.absolute():
        raise ValueError('Missing, nonregular or symlinked input: ' + str(path))
    return path


def private_directory(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute private state directory required')
    for parent in reversed([path] + list(path.parents)):
        if parent.is_symlink():
            raise ValueError('Symlinked state directory refused')
        if parent.exists():
            info = parent.stat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError('Private state ancestor is writable or not root owned')
        else:
            parent.mkdir(mode=0o700)
    path.chmod(0o700)


def native_credentials(issabel, amportal):
    """Read data only: never source/evaluate the vendor configuration files."""
    def values(path):
        result = {}
        for line in regular(path).read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith(('#', ';')) or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            if key in result:
                raise ValueError('Duplicate native configuration key: ' + key)
            result[key] = value
        return result
    issabel_values, amp = values(issabel), values(amportal)
    password = issabel_values.get('mysqlrootpwd')
    if not password:
        raise ValueError('Native password wizard has not completed; mysqlrootpwd missing')
    # The vendor framework owns this identity and its credentials. The addon
    # uses the native root password only for existing brand settings rows.
    if amp.get('AMPDBNAME', 'asterisk') != 'asterisk':
        raise ValueError('Unexpected native framework database; reviewed integration required')
    return {'user': 'root', 'password': password}


def asterisk_major(output, requested=None):
    match = re.search(r'\bAsterisk\s+(16|18|20)(?:\.|\s)', output)
    if not match:
        raise ValueError('A running native Asterisk 16, 18 or 20 is required')
    actual = match.group(1)
    if requested and str(requested) != actual:
        raise ValueError('Native Asterisk version differs from the selected version')
    return actual


def run(argv, capture=False, data=None):
    result = subprocess.run(argv, input=data, stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None, timeout=300)
    if result.returncode:
        # Never echo captured database diagnostics: they may contain credentials.
        raise ValueError('Native addon command failed: ' + Path(argv[0]).name)
    return result.stdout if capture else b''


def brand_database(credentials, action, rows=None):
    """Pass secrets on stdin only. Export old brand rows before any mutation."""
    code = r'''
$v=json_decode(stream_get_contents(STDIN),true);
try {
 $db=new PDO('mysql:host=localhost;dbname=asterisk',$v['user'],$v['password']);
 $db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
 $keys=array_keys($v['keys']); $where=implode(',',array_fill(0,count($keys),'?'));
 $q=$db->prepare('SELECT * FROM issabelpbx_settings WHERE keyword IN ('.$where.')');
 $q->execute($keys); $old=$q->fetchAll(PDO::FETCH_ASSOC);
 if($v['action']==='snapshot'){echo json_encode($old);exit(0);}
 $db->beginTransaction();
 if($v['action']==='restore'){
  $q=$db->prepare('DELETE FROM issabelpbx_settings WHERE keyword IN ('.$where.')');$q->execute($keys);
  foreach($v['rows'] as $row){
   foreach(array_keys($row) as $column){if(!preg_match('/^[a-z_]+$/i',$column))throw new Exception('column');}
   $q=$db->prepare('INSERT INTO issabelpbx_settings (`'.implode('`,`',array_keys($row)).'`) VALUES ('.implode(',',array_fill(0,count($row),'?')).')');
   $q->execute(array_values($row));
  }
 }else{
  foreach($v['keys'] as $key=>$value){
   $q=$db->prepare('SELECT COUNT(*) FROM issabelpbx_settings WHERE keyword=?');$q->execute(array($key));
   if($q->fetchColumn()){$q=$db->prepare('UPDATE issabelpbx_settings SET value=? WHERE keyword=?');$q->execute(array($value,$key));}
   else{$q=$db->prepare("INSERT INTO issabelpbx_settings (keyword,value,name,level,description,type,options,defaultval) VALUES (?,?,?,1,'','text','','')");$q->execute(array($key,$value,$key));}
  }
  $q=$db->prepare('SELECT keyword,value,type FROM issabelpbx_settings WHERE keyword IN ('.$where.')');$q->execute($keys);
  $seen=array();foreach($q as $row){if(!$row['type']||$v['keys'][$row['keyword']]!==$row['value'])throw new Exception('verify');$seen[]=$row['keyword'];}
  if(count($seen)!==count($keys))throw new Exception('count');
 }
 $db->commit();
}catch(Exception $e){if(isset($db)&&$db->inTransaction())$db->rollBack();fwrite(STDERR,"Native brand database operation failed\n");exit(1);}
'''
    payload = dict(credentials, action=action, keys=BRAND_KEYS, rows=rows)
    result = run(['php', '-r', code], capture=True, data=json.dumps(payload).encode('utf-8'))
    return json.loads(result.decode('utf-8')) if action == 'snapshot' else None


def replace_brand_config(text):
    lines = text.splitlines()
    for key, value in BRAND_KEYS.items():
        matches = [i for i, line in enumerate(lines) if line.startswith(key + '=')]
        if len(matches) > 1:
            raise ValueError('Duplicate brand config key: ' + key)
        if matches:
            lines[matches[0]] = key + '=' + value
        else:
            lines.append(key + '=' + value)
    return '\n'.join(lines) + '\n'


def copy_assets(source, destination):
    if not source.is_dir() or source.is_symlink():
        raise ValueError('Missing addon assets: ' + str(source))
    for path in source.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlinked addon asset refused')
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(path), str(target))


def snapshot_settings(settings, backup):
    # Connection.backup was introduced after Python 3.6. A read transaction and
    # iterdump keep this hook compatible with Rocky's platform-python as well.
    with closing(sqlite3.connect(str(settings))) as source:
        source.execute('BEGIN')
        rows = list(source.execute('SELECT key,value FROM settings WHERE key=?', ('theme',)))
        (backup / 'settings.sql').write_text('\n'.join(source.iterdump()) + '\n', encoding='utf-8')
    return rows


def restore_settings(settings, rows):
    # Own only the theme. Native language selection may change independently,
    # including while another addon stage fails; never restore that choice.
    if any(key != 'theme' for key, value in rows):
        raise ValueError('Rollback settings contain a key not owned by this addon')
    with closing(sqlite3.connect(str(settings))) as database, database:
        database.execute('DELETE FROM settings WHERE key=?', ('theme',))
        database.executemany('INSERT INTO settings (key,value) VALUES (?,?)', rows)


def activate_theme(settings):
    # Preserve the language chosen by the original native language wizard.
    with closing(sqlite3.connect(str(settings))) as database, database:
        database.execute('DELETE FROM settings WHERE key=?', ('theme',))
        database.execute('INSERT INTO settings (key,value) VALUES (?,?)', ('theme', 'mytel'))
        if database.execute('SELECT value FROM settings WHERE key=?', ('theme',)).fetchall() != [('mytel',)]:
            raise ValueError('Native theme activation verification failed')


def optional_asternic_plan(bundle, web):
    module = web / 'admin/modules/asternic_cdr'
    if module.exists() or module.is_symlink():
        return load('native_asternic', bundle / 'admin-fixes/patch-asternic-direction.py').plan(module)
    print('Optional Asternic absent: no module installed or changed.', flush=True)
    return {}


def prepare_files(bundle, root, staging):
    """Build the full UI plan in private staging before touching the vendor tree."""
    web = root / 'var/www/html'
    staged_web = staging / 'var/www/html'
    # Patch planners validate exact vendor anchors in these bounded inputs.
    for relative in ('admin/views', 'admin/modules/dashboard', 'admin/modules/sipsettings', 'admin/assets/js',
                     'modules/calendar'):
        source = web / relative
        if not source.is_dir() or source.resolve() != source.absolute():
            raise ValueError('Required native addon input missing: ' + relative)
        for path in source.rglob('*'):
            if path.is_symlink():
                raise ValueError('Symlinked native addon input refused')
        shutil.copytree(str(source), str(staged_web / relative))
    for relative in ('admin/libraries',):
        source = web / relative
        if source.is_dir():
            for path in source.rglob('*'):
                if path.is_symlink():
                    raise ValueError('Symlinked native addon input refused')
            shutil.copytree(str(source), str(staged_web / relative))
    shutil.copyfile(str(regular(web / 'admin/functions.inc.php')), str(staged_web / 'admin/functions.inc.php'))
    copy_assets(bundle / 'theme', staged_web / 'themes/mytel')
    copy_assets(bundle / 'installer/payload/admin/assets/mytel', staged_web / 'admin/assets/mytel')
    copy_assets(bundle / 'theme/images/admin', staged_web / 'admin/images')
    lang = staged_web / 'lang/fa.lang'
    lang.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(regular(bundle / 'installer/payload/lang/fa.lang')), str(lang))
    changes = {}
    theme = load('native_theme', bundle / 'admin-theme/patch-admin-theme.py')
    changes.update(theme.plan(staged_web / 'admin'))
    # Retain the known Apply fix, without the old global success toast.
    apply = load('native_apply_compat', bundle / 'admin-fixes/fix-apply-config.py')
    for legacy, pairs in apply.PATCHES:
        path = staged_web / 'admin' / legacy.relative_to(apply.BASE)
        text = changes.get(path, path.read_text(encoding='utf-8'))
        for old, new in pairs:
            if new not in text:
                if text.count(old) != 1:
                    raise ValueError('Unsupported native Apply input: ' + str(path.relative_to(staging)))
                text = text.replace(old, new, 1)
        if path.name == 'skin.css' and '#button_reload { display: none; }' not in text:
            text = text.rstrip('\n') + '\n' + apply.SKIN_APPEND
        changes[path] = text
    for path, text in changes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    admin = staged_web / 'admin'
    for name, path in [('apply', bundle / 'admin-fixes/patch-apply-backend.py'),
                       ('submit', bundle / 'admin-fixes/patch-submit.py')]:
        changes.update(load('native_' + name, path).plan(admin))
    changes.update(load('native_calendar', bundle / 'admin-fixes/patch-calendar.py').plan(
        staged_web / 'modules/calendar', staged_web / 'modules/calendar/scenarios/rest/CalendarEvent.class.php'))
    # Use the shared debrand algorithm in staging; its legacy web backups never
    # reach the native host. Only resulting presentation files enter the plan.
    debrand = load('native_debrand', bundle / 'admin-theme/patch-debrand.py')
    footer, sub = admin / 'views/footer_content.php', admin / 'assets/mytel/sub.js'
    debrand.patch_file(footer, debrand.FC_REPLACEMENTS)
    debrand.append_js(sub, debrand.DEBRAND_MARK, debrand.DEBRAND_JS)
    for path, text in changes.items():
        if path != sub:
            path.write_text(text, encoding='utf-8')
    sub.write_text(theme.transform_subtitle(sub.read_text(encoding='utf-8')), encoding='utf-8')
    # Optional exact-version Asternic patch; absence is explicit and harmless.
    external = dict(optional_asternic_plan(bundle, web))
    external[root / 'etc/amportal.conf'] = replace_brand_config(regular(root / 'etc/amportal.conf').read_text(encoding='utf-8'))
    for path, before, after in load('native_login', bundle / 'admin-theme/patch-login-branding.py').plan(root):
        external[path] = after.decode('utf-8')
    geoip = web / 'modules/sec_geoip_key/index.php'
    geoip_source = regular(bundle / 'modules/mytellpbxgeoip/index.php').read_bytes()
    geoip_before = regular(geoip).read_bytes()
    import hashlib
    if geoip_before != geoip_source and hashlib.sha256(geoip_before).hexdigest() != NATIVE_GEOIP_STATUS_SHA256:
        raise ValueError('Unknown GeoIP presentation module; native GeoIP data retained')
    external[geoip] = geoip_source
    result = {}
    # Include new assets and only changed native files, excluding staging backups.
    for path in staged_web.rglob('*'):
        if path.is_file() and not path.name.endswith('.bak-mt'):
            target = root / path.relative_to(staging)
            data = path.read_bytes()
            if not target.exists() or regular(target).read_bytes() != data:
                result[target] = data
    for path, text in external.items():
        data = text if isinstance(text, bytes) else text.encode('utf-8')
        if not path.exists() or regular(path).read_bytes() != data:
            result[path] = data
    # Never copy theme extras over unrelated modules. Only missing files within
    # an already installed module are candidates, as in the previous layer.
    extras = bundle / 'theme/extras'
    if extras.is_dir():
        for source in extras.rglob('*'):
            if source.is_file():
                target = web / 'modules' / source.relative_to(extras)
                if not target.exists() and target.parent.is_dir():
                    result[target] = regular(source).read_bytes()
    return result


def snapshot_files(changes, backup, root):
    records = []
    for path in changes:
        if path.is_symlink() or root not in path.absolute().parents or path.resolve() != path.absolute():
            raise ValueError('Unsafe addon destination: ' + str(path))
        relative = path.relative_to(root)
        exists = path.exists()
        record = {'path': relative.as_posix(), 'existed': exists}
        if exists:
            original = regular(path)
            info = original.stat()
            record.update(uid=info.st_uid, gid=info.st_gid, mode=stat.S_IMODE(info.st_mode))
            target = backup / 'files' / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(str(original), str(target))
        records.append(record)
    (backup / 'files.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    return records


def atomic_write(path, data, uid=None, gid=None):
    missing = []
    ancestor = path.parent
    while not ancestor.exists():
        missing.append(ancestor)
        ancestor = ancestor.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o755)
        os.chmod(str(directory), 0o755)
        os.chown(str(directory), uid or 0, gid or 0)
    old = path.stat() if path.exists() else None
    descriptor, temporary = tempfile.mkstemp(prefix='.mytel-native-', dir=str(path.parent))
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), stat.S_IMODE(old.st_mode) if old else 0o644)
            os.fchown(stream.fileno(), old.st_uid if old else uid or 0, old.st_gid if old else gid or 0)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def rollback_files(records, backup, root):
    for record in reversed(records):
        path = root / record['path']
        if record['existed']:
            original = regular(backup / 'files' / record['path'])
            if (any(type(record.get(key)) is not int or not 0 <= record[key] <= 4294967294 for key in ('uid', 'gid'))
                    or type(record.get('mode')) is not int or not 0 <= record['mode'] <= 0o7777):
                raise ValueError('Original file identity missing or invalid in private rollback record')
            atomic_write(path, original.read_bytes(), record['uid'], record['gid'])
            # copy2 preserves mode/time/xattrs, but its backup inode belongs to
            # root. Restore identity from the ORIGINAL stat record, never from
            # the root-created backup. Chown precedes mode restoration because
            # chown may clear setuid/setgid bits on POSIX systems.
            os.chown(str(path), record['uid'], record['gid'])
            shutil.copystat(str(original), str(path), follow_symlinks=False)
            os.chmod(str(path), record['mode'])
        elif path.exists():
            regular(path).unlink()


def install(bundle, backup_root, requested=None, media=None, public_url=None, check=False):
    root = Path('/')
    print('Mytel addons: checking the existing native services and credentials.', flush=True)
    for item in [bundle] + list(bundle.rglob('*')):
        if item.is_symlink() or item.stat().st_uid != 0 or item.stat().st_mode & 0o022:
            raise ValueError('Addon bundle must be root owned, immutable to other users, without symlinks')
    credentials = native_credentials(root / 'etc/issabel.conf', root / 'etc/amportal.conf')
    major = asterisk_major(run(['/usr/sbin/asterisk', '-rx', 'core show version'], capture=True).decode('utf-8'), requested)
    for service in ('mariadb', 'httpd', 'asterisk'):
        run(['systemctl', 'is-active', '--quiet', service])
    run(['httpd', '-t'])
    desk = load('native_desk', bundle / 'installer/install-myteldesk.py')
    pin = desk.validate_pin(json.loads(regular(bundle / 'installer/myteldesk-release.json').read_text(encoding='utf-8')))
    if pin['version'] != '1.1.2':
        raise ValueError('Reviewed addon integration requires MytelDesk 1.1.2')
    public_url = desk.validate_public_url(public_url)
    private_directory(backup_root)
    backup = Path(tempfile.mkdtemp(prefix='native-' + time.strftime('%Y%m%d-%H%M%S') + '-', dir=str(backup_root)))
    state = {'schema': 1, 'owner': 'MytelNativeAddons', 'asterisk': major, 'desk': pin['version'], 'phase': 'preparing'}
    receipt = backup / 'receipt.json'
    receipt.write_text(json.dumps(state, indent=2), encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='staging-', dir=str(backup)) as work:
        print('Mytel addons: preparing theme, scoped repairs, calendar, optional Asternic and native GeoIP display.', flush=True)
        changes = prepare_files(bundle, root, Path(work))
        for index, (path, data) in enumerate(changes.items()):
            if path.suffix == '.php':
                candidate = Path(work) / ('lint-' + str(index) + '.php')
                candidate.write_bytes(data)
                run(['php', '-l', str(candidate)])
        rows = brand_database(credentials, 'snapshot')
        if check:
            state['phase'] = 'checked-no-native-writes'
            state['changed_files'] = len(changes)
            receipt.write_text(json.dumps(state, indent=2), encoding='utf-8')
            print('Native addon candidates and PHP syntax checked; no installed files or settings changed.', flush=True)
            return
        print('Mytel addons: backing up every changed native file and owned settings before activation.', flush=True)
        (backup / 'brand-rows.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
        records = snapshot_files(changes, backup, root)
        settings = regular(root / 'var/www/db/settings.db')
        settings_before = snapshot_settings(settings, backup)
        (backup / 'settings-before.json').write_text(json.dumps(settings_before), encoding='utf-8')
        # Every original above is secured before the first installed-file write.
        import pwd
        account = pwd.getpwnam('asterisk')
        try:
            print('Mytel addons: activating the validated presentation layer.', flush=True)
            for path, data in changes.items():
                web_asset = root / 'var/www/html' in path.parents
                atomic_write(path, data, account.pw_uid if web_asset else 0, account.pw_gid if web_asset else 0)
            brand_database(credentials, 'apply')
            activate_theme(settings)
            run(['httpd', '-t'])
            run(['systemctl', 'reload', 'httpd'])
        except BaseException:
            rollback_files(records, backup, root)
            brand_database(credentials, 'restore', rows)
            restore_settings(settings, settings_before)
            state['phase'] = 'ui-rolled-back'
            receipt.write_text(json.dumps(state, indent=2), encoding='utf-8')
            raise
    state['phase'] = 'ui-ready-desk-pending'
    receipt.write_text(json.dumps(state, indent=2), encoding='utf-8')
    if media is not None:
        print('Mytel addons: installing only the sealed supplemental Python 3.11 package closure.', flush=True)
        with tempfile.TemporaryDirectory(prefix='repos-', dir=str(backup)) as repository:
            repo = media.repo_text().replace('enabled=1\n', 'enabled=1\nincludepkgs=' + ','.join(SUPPLEMENTAL_PACKAGES) + '\n')
            (Path(repository) / 'mytel-supplemental.repo').write_text(repo, encoding='utf-8')
            command = ['dnf', '--disablerepo=*', '--setopt=reposdir=' + repository,
                       '--setopt=install_weak_deps=False', '--setopt=obsoletes=False']
            command += ['--enablerepo=' + entry['id'] for entry in media.manifest['repositories']]
            run(command + ['-y', 'install', 'python3.11', 'python3.11-pip'])
    # The pinned standalone installer owns Desk's own backups, secrets, rollback,
    # Node and CPU VAD. Its doctor and source-state checks are mandatory.
    cache = Path('/var/lib/mytelpbx-native-addons/myteldesk')
    print('Mytel addons: installing the pinned MytelDesk release and mandatory CPU voice analysis.', flush=True)
    desk.install(pin, cache, public_url, launcher_source=bundle / 'modules/mytellpbxopdesk', media=media)
    state['phase'] = 'complete'
    receipt.write_text(json.dumps(state, indent=2), encoding='utf-8')
    print('Mytel addons complete on native Asterisk ' + major + '; private recovery record: ' + str(backup), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-root', type=Path, default=Path(os.environ.get('MYTEL_BUNDLE_ROOT', str(Path(__file__).resolve().parents[1]))))
    parser.add_argument('--backup-root', type=Path, default=Path('/var/backups/mytellpbx/native-addons'))
    parser.add_argument('--asterisk-version', choices=['16', '18', '20'], default=os.environ.get('ASTVER'))
    parser.add_argument('--media-root', type=Path, default=os.environ.get('MYTEL_MEDIA_ROOT'))
    parser.add_argument('--media-manifest-sha256', default=os.environ.get('MYTEL_MEDIA_MANIFEST_SHA256'))
    parser.add_argument('--public-url', default=os.environ.get('MYTELL_DESK_PUBLIC_URL'))
    parser.add_argument('--check', action='store_true', help='Validate the native base and all UI candidates without changing installed files or settings')
    args = parser.parse_args()
    if not hasattr(os, 'geteuid') or os.geteuid() != 0:
        parser.error('Run as root after the native Issabel installation and password wizard')
    os.umask(0o077)
    try:
        if bool(args.media_root) != bool(args.media_manifest_sha256):
            raise ValueError('Offline media root and manifest checksum are required together')
        media = None
        if args.media_root:
            media = load('native_media', args.bundle_root / 'installer/media.py').load(args.media_root, args.media_manifest_sha256)
        install(args.bundle_root, args.backup_root, args.asterisk_version, media, args.public_url, args.check)
    except ValueError as error:
        print('Mytel addons: ' + str(error), file=sys.stderr)
        print('Native credentials and PBX state retained; no reboot requested.', file=sys.stderr)
        return 1
    except OSError as error:
        print('Mytel addons: operating-system step failed' + (' at ' + str(error.filename) if error.filename else '') + '.', file=sys.stderr)
        print('Native credentials and PBX state retained; review the private recovery receipt. No reboot requested.', file=sys.stderr)
        return 1
    except (sqlite3.Error, subprocess.SubprocessError):
        print('Mytel addons incomplete. Native credentials and PBX state retained. Review the preceding stage and private recovery receipt; no reboot requested.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
