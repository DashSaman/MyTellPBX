"""Verified media firstboot handoff; does not adopt an initialized PBX."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile


def relative(value):
    if not isinstance(value,str)or not value or '\\'in value or any(ord(c)<32 for c in value):raise ValueError('Invalid media path')
    path=PurePosixPath(value)
    if path.is_absolute()or '..'in path.parts or str(path)!=value:raise ValueError('Invalid media path')
    return value


def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as stream:
        while True:
            raw=stream.read(1024*1024)
            if not raw:break
            h.update(raw)
    return h.hexdigest()


def checked_path(root,name,owner_uid):
    path=root/relative(name)
    for item in(path,)+tuple(path.parents):
        if item.is_symlink():raise ValueError('Linked media path')
        st=item.lstat()
        if os.name=='posix'and(st.st_uid!=owner_uid or st.st_mode&0o022):raise ValueError('Untrusted media path owner/mode')
        if item==root:break
    st=path.lstat()
    if not stat.S_ISREG(st.st_mode)or st.st_nlink!=1:raise ValueError('Nonregular media asset')
    if os.name=='posix'and(st.st_uid!=owner_uid or st.st_mode&0o022):raise ValueError('Untrusted media owner/mode')
    return path


def read_depot(root,manifest_sha,owner_uid=0):
    root=Path(root)
    if not re.fullmatch('[0-9a-f]{64}',manifest_sha or''):raise ValueError('Manifest digest required')
    if not root.is_absolute()or root.is_symlink()or not root.is_dir():raise ValueError('Media root invalid')
    if os.name=='posix'and(root.stat().st_uid!=owner_uid or root.stat().st_mode&0o022):raise ValueError('Untrusted media root')
    manifest=checked_path(root,'manifest.json',owner_uid)
    if manifest.stat().st_size>4*1024*1024 or sha_file(manifest)!=manifest_sha:raise ValueError('Manifest changed')
    d=json.loads(manifest.read_text(encoding='utf-8'))
    if d.get('schema')!=1 or type(d['schema'])is not int or d.get('owner')!='MyTellPBX'or d.get('platform')!='rocky8.10-x86_64':raise ValueError('Media profile invalid')
    files=d.get('files')
    if not isinstance(files,dict)or not files or len(files)>30000:raise ValueError('Media files invalid')
    for name,meta in files.items():
        p=checked_path(root,name,owner_uid)
        if not isinstance(meta,dict)or set(meta)!={'sha256','bytes'}or type(meta['bytes'])is not int or meta['bytes']<=0 or not re.fullmatch('[0-9a-f]{64}',meta['sha256']or''):raise ValueError('Asset metadata invalid')
        before=p.stat()
        if before.st_size!=meta['bytes']or sha_file(p)!=meta['sha256']:raise ValueError('Media asset changed')
        after=p.stat()
        if(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Media asset changed while reading')
    actual=set()
    for p in root.rglob('*'):
        if p.is_symlink():raise ValueError('Linked media input')
        if p.is_file():actual.add(p.relative_to(root).as_posix())
        elif not p.is_dir():raise ValueError('Special media input')
    if actual!=set(files)|{'manifest.json'}:raise ValueError('Unlisted media input')
    for key in('bootstrap','bundle','desk','node'):
        if relative(d.get(key))not in files:raise ValueError('Required media input missing')
    if not isinstance(d.get('wheels'),list)or not d['wheels']or len(set(d['wheels']))!=len(d['wheels'])or any(relative(p)not in files for p in d['wheels']):raise ValueError('Wheel set missing')
    if relative(d.get('geoip',{}).get('path'))not in files or not re.fullmatch(r'20[0-9]{2}-(0[1-9]|1[0-2])',d['geoip'].get('month','')):raise ValueError('GeoIP input missing')
    if not isinstance(d.get('repositories'),list)or not d['repositories']:raise ValueError('Repositories missing')
    ids=[]
    for repo in d['repositories']:
        if set(repo)!={'id','path','gpgkey'}or not re.fullmatch('[A-Za-z0-9_-]+',repo['id']):raise ValueError('Repository invalid')
        base=relative(repo['path']);key=relative(repo['gpgkey'])
        if key not in files or base+'/repodata/repomd.xml'not in files:raise ValueError('Repository metadata/key missing')
        ids.append(repo['id'])
    if len(set(ids))!=len(ids):raise ValueError('Duplicate repository')
    bootstrap=(root/d['bootstrap']).read_bytes()
    literal=('MYTELLPBX_BUNDLE_SHA256="'+files[d['bundle']]['sha256']+'"').encode()
    if bootstrap.count(literal)!=1:raise ValueError('Bootstrap bundle pin mismatch')
    return d


def run_firstboot(root,manifest_sha,state,runner,owner_uid=0):
    d=read_depot(root,manifest_sha,owner_uid);root=Path(root);state=Path(state)
    expected={'schema':1,'owner':'MytelPBX','manifest_sha256':manifest_sha,'bootstrap_sha256':d['files'][d['bootstrap']]['sha256'],'bundle_sha256':d['files'][d['bundle']]['sha256']}
    done=state/'complete.json'
    if state.is_symlink():raise ValueError('Linked firstboot state')
    if state.exists():
        if not state.is_dir()or(os.name=='posix'and(state.stat().st_uid!=owner_uid or state.stat().st_mode&0o077)):raise ValueError('Firstboot state owner/mode invalid')
        if any(p.name!='complete.json'for p in state.iterdir()):raise ValueError('Unknown firstboot state retained')
    if done.exists()or done.is_symlink():
        checked_path(state,'complete.json',owner_uid)
        if json.loads(done.read_text(encoding='utf-8'))!=expected:raise ValueError('Different firstboot completion retained')
        return 0
    env={'HOME':'/root','PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
         'MYTELL_MEDIA_ROOT':str(root),'MYTELL_MEDIA_MANIFEST_SHA256':manifest_sha,'MYTELL_BUNDLE_FILE':str(root/d['bundle']),'MYTELL_SKIP_UPDATE':'1','MYTELL_REBOOT':'0'}
    result=runner(['/bin/bash',str(root/d['bootstrap'])],env)
    if type(result)is not int or not 0<=result<=255:raise ValueError('Unknown installer outcome')
    if result:return result
    if state.is_symlink():raise ValueError('Linked firstboot state')
    state.mkdir(mode=0o700,parents=True,exist_ok=True)
    if os.name=='posix'and(state.stat().st_uid!=owner_uid or state.stat().st_mode&0o077):raise ValueError('Firstboot state owner/mode invalid')
    fd,name=tempfile.mkstemp(prefix='.complete-',dir=str(state));temporary=Path(name)
    try:
        with os.fdopen(fd,'w',encoding='utf-8')as f:
            os.chmod(str(temporary),0o600);json.dump(expected,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
        os.link(str(temporary),str(done))
    finally:temporary.unlink()
    return 0


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify',action='store_true');p.add_argument('--config',default='/etc/mytelpbx-media.json');a=p.parse_args()
    if os.name!='posix'or os.geteuid()!=0:raise ValueError('Root Linux required')
    cfg=Path(a.config);checked_path(cfg.parent,cfg.name,0);d=json.loads(cfg.read_text(encoding='utf-8'))
    if set(d)!={'root','manifest_sha256'}or d['root']!='/var/lib/mytelpbx-media':raise ValueError('Unknown media configuration')
    if a.verify:
        assets=read_depot(d['root'],d['manifest_sha256']);print('MytelPBX verified media: '+str(len(assets['files']))+' files');return 0
    import fcntl
    lock=os.open('/run/mytelpbx-media-firstboot.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def execute(args,env):
        print('MytelPBX first boot — https://mytel.one',flush=True)
        return subprocess.call(args,env=env,close_fds=True)
    return run_firstboot(d['root'],d['manifest_sha256'],'/var/lib/mytelpbx-media-state',execute)


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:raise SystemExit('MytelPBX media firstboot refused: '+type(e).__name__+'; existing state retained')
