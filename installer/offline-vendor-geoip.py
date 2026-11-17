#!/usr/bin/env python3
"""Verified public cache transport for the exact signed vendor GeoIP cron.

No RPM edits, skipped scriptlets, clock changes or network fallback. The vendor
still performs its native conversions. This helper preserves those outputs
before handing the xtables directory to the managed updater. Python3.6+.
"""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import ipaddress
import json
import os
import posixpath
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile

OWNER='MytelPBX offline vendor GeoIP'
EXPECTED_UID=0  # Tests may inject their disposable tree's owner; CLI always requires root.
VENDOR='1d7f584b55f3dcba58e4271b03141fc2cbc424944172da859c3157c04ad3400c'
CONFIG='etc/geoip_key.conf'
CRON='etc/cron.daily/geoip_update.sh'
PROGRAM='usr/local/libexec/mytellpbx/offline-vendor-geoip.py'
MEDIA='usr/local/libexec/mytellpbx/media.py'
STATE='var/lib/mytellpbx-offline-geoip/state.json'
BACKUP='var/backups/mytellpbx/offline-vendor-geoip/xt_geoip-native'
COUNTRY='geoip/countryInfo.txt'
ACTIVE='usr/share/xt_geoip'


def module(path):
    spec=importlib.util.spec_from_file_location('mytel_offline_media',str(path))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def identity(value):
    return (value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid,
            value.st_size,value.st_mtime_ns,value.st_ctime_ns if os.name=='posix' else None)


def read(path,limit=33554432,private=False):
    path=Path(path);before=path.lstat()
    if (path.resolve()!=path.absolute() or not stat.S_ISREG(before.st_mode)
            or not 0<=before.st_size<=limit or (os.name=='posix' and
            (before.st_uid!=EXPECTED_UID or before.st_mode&0o022 or (private and stat.S_IMODE(before.st_mode)!=0o600)))):
        raise ValueError('Unsafe offline GeoIP input')
    fd=os.open(str(path),os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb') as stream:
        if identity(os.fstat(stream.fileno()))!=identity(before):raise ValueError('Input changed')
        data=stream.read(limit+1)
        if len(data)!=before.st_size or identity(os.fstat(stream.fileno()))!=identity(before):raise ValueError('Input changed')
    if identity(path.lstat())!=identity(before):raise ValueError('Input changed')
    return data


def managed(root,relative):
    path=Path(root)
    for part in Path(relative).parts[:-1]:
        path=path/part
        if not path.exists() and not path.is_symlink():path.mkdir(mode=0o755)
        info=path.lstat()
        if not stat.S_ISDIR(info.st_mode) or (os.name=='posix' and (info.st_uid!=EXPECTED_UID or info.st_mode&0o022)):
            raise ValueError('Unsafe managed GeoIP directory')
    return path/Path(relative).name


def write(path,data,previous=None,mode=0o600):
    if path.exists() or path.is_symlink():
        if previous is None or read(path)!=previous:raise ValueError('Owned output collision')
    elif previous is not None:raise ValueError('Owned output disappeared')
    fd,name=tempfile.mkstemp(prefix='.offline-geoip-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        os.chmod(name,mode)
        if previous is None:os.link(name,str(path))
        else:
            if read(path)!=previous:raise ValueError('Owned output changed')
            os.replace(name,str(path))
    finally:
        if os.path.exists(name):os.unlink(name)


def country_info(raw):
    if b'\0' in raw or len(raw)>1048576:raise ValueError('Invalid country metadata')
    countries=set()
    for line in raw.decode('utf-8').splitlines():
        if not line or line.startswith('#'):continue
        fields=line.split('\t')
        if len(fields)<17 or not re.fullmatch('[A-Z]{2}',fields[0]) or not fields[4] or fields[0] in countries:
            raise ValueError('Invalid country metadata')
        countries.add(fields[0])
    if len(countries)<200:raise ValueError('Partial country metadata')
    return countries


def profile(media_root,checksum):
    media_root=Path(media_root)
    if not re.fullmatch('[0-9a-f]{64}',str(checksum)):raise ValueError('Missing media pin')
    raw=read(media_root/'manifest.json')
    if hashlib.sha256(raw).hexdigest()!=checksum:raise ValueError('Changed media manifest')
    value=json.loads(raw.decode('utf-8'))
    if value['schema']!=1 or value['owner']!='MyTellPBX' or value['platform']!='rocky8.10-x86_64':raise ValueError('Wrong media profile')
    paths={'dbip':value['geoip']['path'],'country':COUNTRY}
    if not re.fullmatch(r'20[0-9]{2}-(?:0[1-9]|1[0-2])',value['geoip']['month']):raise ValueError('Invalid cached month')
    result={'root':str(media_root),'manifest_sha256':checksum,'month':value['geoip']['month']}
    for key,name in paths.items():
        if not re.fullmatch('[A-Za-z0-9_.+/-]+',name) or name.startswith('/') or any(p in ('','.','..') for p in name.split('/')):raise ValueError('Invalid asset path')
        record=value['files'][name];data=read(media_root/name,16777216 if key=='dbip' else 1048576)
        if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Changed cached data')
        result[key]={'path':str(media_root/name),'sha256':record['sha256'],'bytes':record['bytes']}
    country_info(read(result['country']['path'],1048576))
    if read(result['dbip']['path'],16777216)[:2]!=b'\x1f\x8b':raise ValueError('Invalid cached DB-IP gzip')
    return result


def asset_for(tool,args):
    if tool=='wget' and len(args)==3 and args[0]=='-q' and args[2]=='-O-' and re.fullmatch(
            r'https://download\.db-ip\.com/free/dbip-country-lite-20[0-9]{2}-(?:0[1-9]|1[0-2])\.csv\.gz',args[1]):return 'dbip'
    if tool=='curl' and args==['-s','http://download.geonames.org/export/dump/countryInfo.txt']:return 'country'
    raise ValueError('Unreviewed vendor transport request refused')


def config_bytes(root,python='/usr/bin/python3'):
    root=Path(root);command=' '.join(shlex.quote(str(x).replace('\\','/')) for x in [python,'-B',root/PROGRAM])
    caller=str(root/CRON).replace('\\','/')
    # Functions exist only inside the exact vendor script's Bash process.
    return ('# MytelPBX owned offline vendor GeoIP bridge v1\n'
            'if [ "${BASH_SOURCE[1]-}" = '+shlex.quote(caller)+' ]; then\n'
            '  '+command+' --check-caller || exit 1\n'
            '  wget() { '+command+' --serve wget -- "$@"; }\n'
            '  curl() { '+command+' --serve curl -- "$@"; }\n'
            'fi\n').encode('utf-8')


def state(root):
    raw=read(Path(root)/STATE,private=True);value=json.loads(raw.decode())
    if value.get('owner')!=OWNER or value.get('schema')!=1 or value.get('phase') not in ('prepared','handoff','finished'):
        raise ValueError('Unknown offline bridge ownership')
    return raw,value


def save(root,value,previous):write(managed(root,STATE),(json.dumps(value,sort_keys=True)+'\n').encode(),previous)


def rpm_payload_guard(media_root):
    value=json.loads(read(Path(media_root)/'manifest.json').decode())
    paths=sorted(name for name in value['files'] if name.endswith('.rpm'))
    if not 1<=len(paths)<=5000:raise ValueError('Selected RPM payload inventory unavailable')
    checksum=hashlib.sha256()
    for start in range(0,len(paths),64):
        batch=paths[start:start+64]
        if any(name.startswith('/') or any(p in ('','.','..') for p in name.split('/')) for name in batch):raise ValueError('Invalid RPM path')
        result=subprocess.run(['/usr/bin/rpm','-qpl','--']+[str(Path(media_root)/name) for name in batch],
                              stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        if result.returncode or len(result.stdout)>64*1024*1024 or len(result.stderr)>1048576:raise ValueError('Cannot inspect selected RPM file lists')
        for line in result.stdout.decode('utf-8').splitlines():
            if '\0' in line or posixpath.normpath('/'+line.lstrip('/'))=='/etc/geoip_key.conf':
                raise ValueError('A selected RPM owns the offline GeoIP configuration')
        checksum.update(result.stdout)
    return {'packages':len(paths),'filelists_sha256':checksum.hexdigest(),'owns_geoip_key_config':False}


def complete_prepare(root,value,media_verified=False):
    sources={PROGRAM:Path(__file__),MEDIA:Path(__file__).with_name('media.py')}
    data={target:read(source) for target,source in sources.items()}
    if (any(hashlib.sha256(data[p]).hexdigest()!=h for p,h in value['helpers'].items())
            or hashlib.sha256(read(Path(__file__).with_name('geoip-update.py'))).hexdigest()!=value['updater_sha256']):
        raise ValueError('Prepared source differs from its owned intent')
    data[CONFIG]=config_bytes(root);missing=[]
    for target,expected in data.items():
        path=root/target
        if path.exists() or path.is_symlink():
            if read(path,private=target==CONFIG)!=expected:raise ValueError('Owned publication collision retained')
        else:missing.append(target)
    if missing:
        if value['phase']!='prepared' or value['served']:raise ValueError('An active bridge publication disappeared')
        active=root/ACTIVE
        if active.is_symlink() or (active.exists() and (not active.is_dir() or any(active.iterdir()))):raise ValueError('Country data changed before preparation completed')
        if not media_verified:
            module(Path(__file__).with_name('media.py')).load(value['profile']['root'],value['profile']['manifest_sha256'],expected_uid=EXPECTED_UID)
            if rpm_payload_guard(value['profile']['root'])!=value['rpm_payloads']:raise ValueError('Selected RPM payload metadata changed')
        for target in missing:write(managed(root,target),data[target],mode=0o600 if target==CONFIG else 0o755 if target==PROGRAM else 0o644)
    return value


def prepare(root,media_root,checksum):
    root=Path(root);config=root/CONFIG
    if (root/STATE).exists():
        raw,value=state(root)
        if value['profile']!=profile(media_root,checksum):raise ValueError('Offline profile changed')
        if value['phase']=='finished' and not config.exists() and not config.is_symlink():return value
        return complete_prepare(root,value)
    if config.exists() or config.is_symlink():raise ValueError('Existing GeoIP configuration retained')
    for name in ['GeoIP.dat','GeoIPv6.dat']:
        temporary=root/'tmp'/name
        if temporary.exists() or temporary.is_symlink():raise ValueError('Existing native conversion temporary retained')
    active=root/ACTIVE
    if active.is_symlink() or (active.exists() and (not active.is_dir() or any(active.iterdir()))):raise ValueError('Existing country data retained')
    media=module(Path(__file__).with_name('media.py'));media.load(media_root,checksum,expected_uid=EXPECTED_UID)
    selected=profile(media_root,checksum)
    payloads=rpm_payload_guard(media_root)
    sources={PROGRAM:Path(__file__),MEDIA:Path(__file__).with_name('media.py')}
    for target,source in sources.items():
        if (root/target).exists() or (root/target).is_symlink():raise ValueError('Existing persistent helper retained')
    value={'owner':OWNER,'schema':1,'phase':'prepared','profile':selected,'original_config':'absent',
           'updater_sha256':hashlib.sha256(read(Path(__file__).with_name('geoip-update.py'))).hexdigest(),
           'served':[],'rpm_payloads':payloads,'helpers':{k:hashlib.sha256(read(v)).hexdigest() for k,v in sources.items()}}
    # Durable intent precedes publication. An interrupted prepare cannot be silently adopted.
    save(root,value,None)
    return complete_prepare(root,value,media_verified=True)


def checked(root,require_vendor=False):
    raw,value=state(root);selected=profile(value['profile']['root'],value['profile']['manifest_sha256'])
    if selected!=value['profile']:raise ValueError('Profile changed')
    if read(Path(root)/CONFIG,private=True)!=config_bytes(root):raise ValueError('Bridge configuration changed')
    for path,checksum in value['helpers'].items():
        if hashlib.sha256(read(Path(root)/path)).hexdigest()!=checksum:raise ValueError('Persistent helper changed')
    if require_vendor and hashlib.sha256(read(Path(root)/CRON,131072)).hexdigest()!=VENDOR:raise ValueError('Unknown vendor cron retained')
    return raw,value


def serve(root,tool,args,output):
    raw,value=checked(root,True);asset=asset_for(tool,args)
    record=value['profile'][asset];data=read(record['path'],16777216)
    if hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Cached data changed')
    output.write(data);output.flush()
    # Record actual cached month, never claim the cron's requested month was downloaded.
    value['served']=sorted(set(value['served']+[asset]));save(root,value,raw)


def samples(path):
    selected={4:{},6:{}};size=0
    with gzip.open(str(path),'rt',encoding='utf-8',newline='') as source:
        for row in csv.reader(source,strict=True):
            size+=sum(map(len,row))
            if size>128*1024*1024 or len(row)!=3 or not re.fullmatch('[A-Z]{2}',row[2]):raise ValueError('Invalid cached ranges')
            start,end=ipaddress.ip_address(row[0]),ipaddress.ip_address(row[1])
            if start.version!=end.version or int(start)>int(end):raise ValueError('Invalid cached range')
            code='US' if row[2]=='ZZ' else row[2]
            if len(selected[start.version])<4:selected[start.version].setdefault(code,str(start))
    if any(len(v)!=4 for v in selected.values()):raise ValueError('Insufficient native lookup controls')
    return [{'family':family,'country':code,'address':address} for family in (4,6) for code,address in selected[family].items()]


def native_lookup(items):
    """Official libGeoIP C API; invoked only in a bounded isolated child.
    https://github.com/maxmind/geoip-api-c/blob/main/libGeoIP/GeoIP.h
    """
    import ctypes
    library=Path('/usr/lib64/libGeoIP.so.1').resolve();read(library,16777216)
    lib=ctypes.CDLL(str(library));lib.GeoIP_open.argtypes=[ctypes.c_char_p,ctypes.c_int];lib.GeoIP_open.restype=ctypes.c_void_p
    lib.GeoIP_delete.argtypes=[ctypes.c_void_p];lib.GeoIP_delete.restype=None
    lib.GeoIP_database_edition.argtypes=[ctypes.c_void_p];lib.GeoIP_database_edition.restype=ctypes.c_ubyte
    for family in (4,6):
        path='/usr/share/GeoIP/'+('GeoIP.dat' if family==4 else 'GeoIPv6.dat')
        before=read(path,67108864);handle=lib.GeoIP_open(path.encode(),0)
        if not handle:raise ValueError('Native country database did not open')
        try:
            if lib.GeoIP_database_edition(handle)!=(1 if family==4 else 12):raise ValueError('Wrong native database edition')
            fn=getattr(lib,'GeoIP_country_code_by_addr'+('' if family==4 else '_v6'));fn.argtypes=[ctypes.c_void_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
            for item in items:
                if item['family']==family and fn(handle,item['address'].encode())!=item['country'].encode():raise ValueError('Native country lookup mismatch')
        finally:lib.GeoIP_delete(handle)
        if read(path,67108864)!=before:raise ValueError('Native database changed')


def legacy(root,controls,lookup=None):
    result={}
    for name in ['GeoIP.dat','GeoIPv6.dat']:
        path=Path(root)/'usr/share/GeoIP'/name;data=read(path,67108864)
        if len(data)<1000:raise ValueError('Missing legacy country database')
        result[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    if lookup is None:
        run=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--lookup'],input=json.dumps(controls).encode(),
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        if run.returncode or run.stdout!=b'lookup-ok\n':raise ValueError('Legacy native lookups failed')
    else:lookup(controls)
    for name,record in result.items():
        if hashlib.sha256(read(Path(root)/'usr/share/GeoIP'/name,67108864)).hexdigest()!=record['sha256']:raise ValueError('Legacy table changed')
    return result


def inventory(path):
    result={};total=0
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or (os.name=='posix' and (info.st_uid!=EXPECTED_UID or info.st_mode&0o022)):raise ValueError('Unsafe native country directory')
    for child in sorted(path.rglob('*')):
        relative=child.relative_to(path).as_posix()
        info=child.lstat()
        if stat.S_ISDIR(info.st_mode) and relative in ('BE','LE'):
            if os.name=='posix' and (info.st_uid!=EXPECTED_UID or info.st_mode&0o022):raise ValueError('Unsafe native country directory')
            continue
        if not re.fullmatch(r'(?:(?:BE|LE)/)?[A-Z0-9]{2}\.iv[46]',relative):raise ValueError('Unknown native country output retained')
        raw=read(child,33554432);total+=len(raw)
        if total>128*1024*1024 or len(result)>=3000 or len(raw)%(8 if relative.endswith('4') else 32):raise ValueError('Invalid packed country output')
        result[relative]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if not result or not any(k.startswith('BE/') for k in result) or not any(k.startswith('LE/') for k in result):raise ValueError('Missing native packed outputs')
    return result


def handoff(root,media_root,checksum,lookup=None):
    root=Path(root);raw,value=state(root)
    if value['profile']!=profile(media_root,checksum):raise ValueError('Offline profile changed')
    if value['phase']=='finished' and not (root/CONFIG).exists() and not (root/CONFIG).is_symlink():return value
    checked(root,value['phase']=='prepared')
    if value['profile']!=profile(media_root,checksum) or value['served']!=['country','dbip']:raise ValueError('Native cache requests were not completed')
    active=root/ACTIVE;backup=managed(root,BACKUP)
    if value['phase']=='prepared':
        value['legacy']=legacy(root,samples(value['profile']['dbip']['path']),lookup)
        for name,record in value['legacy'].items():
            converted=read(root/'tmp'/name,67108864)
            if len(converted)!=record['bytes'] or hashlib.sha256(converted).hexdigest()!=record['sha256']:
                raise ValueError('Native converted table was not activated')
        value['native_conversion_outputs_match']=True
        if backup.exists() or backup.is_symlink():raise ValueError('Existing native backup retained')
        value['packed']=inventory(active);value['phase']='handoff';save(root,value,raw)
    for name,record in value['legacy'].items():
        if hashlib.sha256(read(root/'usr/share/GeoIP'/name,67108864)).hexdigest()!=record['sha256']:raise ValueError('Legacy data changed')
    if backup.exists() or backup.is_symlink():
        if inventory(backup)!=value['packed']:raise ValueError('Native backup changed')
    else:
        if inventory(active)!=value['packed']:raise ValueError('Native outputs changed')
        # Only complete an owned, hash-bound move; never replay the RPM postscript.
        os.rename(str(active),str(backup))
    if active.is_symlink():verify_managed(root,value)
    elif active.exists():
        if not active.is_dir() or any(active.iterdir()):raise ValueError('Unknown active data retained')
    else:active.mkdir(mode=0o755)
    return value


def verify_managed(root,value):
    active=root/ACTIVE
    if not active.is_symlink() or active.resolve().name!='BE' or active.resolve().parent.parent!=root/'usr/share/mytellpbx-geoip/releases':raise ValueError('Managed country pointer unavailable')
    program=root/'usr/local/libexec/mytellpbx/geoip-update.py'
    if hashlib.sha256(read(program)).hexdigest()!=value['updater_sha256']:raise ValueError('Managed updater changed')
    installed=module(program);info=installed.release_info(active.resolve().parent)
    if info['source_sha256']!=value['profile']['dbip']['sha256']:raise ValueError('Managed data source changed')


def finish(root,media_root,checksum):
    root=Path(root);raw,value=state(root)
    if value['profile']!=profile(media_root,checksum):raise ValueError('Offline profile changed')
    if value['phase']=='finished' and not (root/CONFIG).exists() and not (root/CONFIG).is_symlink():return value
    checked(root)
    if value['phase'] not in ('handoff','finished') or inventory(root/BACKUP)!=value['packed']:raise ValueError('Native preservation incomplete')
    for name,record in value['legacy'].items():
        if hashlib.sha256(read(root/'usr/share/GeoIP'/name,67108864)).hexdigest()!=record['sha256']:raise ValueError('Legacy data changed')
    status=json.loads(read(root/'usr/share/mytellpbx-geoip/status.json').decode())
    if (status['owner']!='MyTellPBX GeoIP' or status['status']!='ready' or status['month']!=value['profile']['month']
            or status['source_sha256']!=value['profile']['dbip']['sha256']):raise ValueError('Managed GeoIP is not ready')
    verify_managed(root,value)
    value['phase']='finished';save(root,value,raw)
    if read(root/CONFIG,private=True)!=config_bytes(root):raise ValueError('Owned config changed')
    (root/CONFIG).unlink()  # The original state was absent, never an operator key.
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);phase=p.add_mutually_exclusive_group(required=True)
    for name in ['prepare','handoff','finish','check-caller','lookup']:phase.add_argument('--'+name,action='store_true')
    phase.add_argument('--serve',choices=['wget','curl']);p.add_argument('--media-root',type=Path);p.add_argument('--manifest-sha256');p.add_argument('arguments',nargs=argparse.REMAINDER)
    args=p.parse_args()
    if os.name!='posix' or os.geteuid()!=0:p.error('Linux root required')
    if args.lookup:native_lookup(json.load(sys.stdin));print('lookup-ok');return
    if args.check_caller:checked(Path('/'),True);return
    if args.serve:
        arguments=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
        serve(Path('/'),args.serve,arguments,sys.stdout.buffer);return
    if not args.media_root or not args.manifest_sha256:p.error('Pinned media profile required')
    function=prepare if args.prepare else handoff if args.handoff else finish
    result=function(Path('/'),args.media_root,args.manifest_sha256)
    print(json.dumps({'owner':OWNER,'phase':result['phase'],'cached_month':result['profile']['month'],
                      'downloaded_current_month':False,'native_legacy_verified':bool(result.get('legacy'))}))


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('Offline vendor GeoIP bridge refused; original inputs retained. Inspect the owned phase receipt.')
