#!/usr/bin/env python3
"""Prepare the separate native Asterisk DTLS PEM after vendor CLI initialization.

Called only by the owned fresh/resume installer, serialized by its installer
lock. It does not change PBX/Apache configuration, copy HTTPS private keys,
reload services, query a database or open a network connection. Existing valid,
service-readable combined PEMs are preserved. Nonempty invalid/custom material
is never replaced. --check reads and validates via OpenSSL stdin without writes.
Python3.6 compatible; CLI Linux/root only. SPDX-License-Identifier: GPL-2.0-only
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

RELATIVE='etc/asterisk/keys/asterisk.pem'
MAXIMUM=1024*1024
TIMEOUT=30

def digest(value):
    return hashlib.sha256(value).hexdigest()

def run_command(arguments, data=None):
    try:
        options={'stdin':subprocess.DEVNULL} if data is None else {'input':data}
        result=subprocess.run(arguments,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              timeout=TIMEOUT,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'},**options)
    except (OSError,subprocess.TimeoutExpired) as error:
        raise ValueError('DTLS command unavailable or timed out') from error
    if result.returncode or len(result.stdout)>MAXIMUM:
        raise ValueError('DTLS certificate command failed; material retained')
    return result.stdout

def validate_material(value,openssl='/usr/bin/openssl'):
    if not isinstance(value,bytes) or not 0<len(value)<=MAXIMUM:
        raise ValueError('Missing or oversized native DTLS material')
    if b'-----BEGIN ENCRYPTED PRIVATE KEY-----' in value or re.search(rb'^Proc-Type:\s*4,ENCRYPTED\s*$',value,re.M):
        raise ValueError('Encrypted DTLS material is not usable noninteractively')
    keys=re.findall(rb'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',value)
    if len(keys)!=1 or b'-----BEGIN CERTIFICATE-----' not in value:
        raise ValueError('A combined certificate and one plaintext private key are required')
    dates=run_command([openssl,'x509','-noout','-startdate','-enddate'],value)
    try:
        fields=dict(line.split('=',1)for line in dates.decode('ascii').splitlines())
        start=datetime.datetime.strptime(fields['notBefore'],'%b %d %H:%M:%S %Y GMT')
        end=datetime.datetime.strptime(fields['notAfter'],'%b %d %H:%M:%S %Y GMT')
        if not start<=datetime.datetime.utcnow()<end:raise ValueError('Certificate is not currently valid')
    except (KeyError,UnicodeError,ValueError) as error:
        raise ValueError('DTLS certificate validity failed') from error
    public_cert=run_command([openssl,'x509','-noout','-pubkey'],value)
    public_key=run_command([openssl,'pkey','-passin','pass:','-pubout'],value)
    if public_cert.replace(b'\r\n',b'\n')!=public_key.replace(b'\r\n',b'\n'):
        raise ValueError('DTLS certificate and private key do not match')
    certificate=run_command([openssl,'x509','-outform','DER'],value)
    if not certificate:raise ValueError('Native DTLS fingerprint is empty')
    return digest(certificate)

def generate_material(openssl,private_directory):
    with tempfile.TemporaryDirectory(prefix='.generate-',dir=str(private_directory)) as temporary:
        key,cert=Path(temporary)/'key.pem',Path(temporary)/'cert.pem'
        run_command([openssl,'req','-x509','-newkey','rsa:2048','-nodes','-sha256','-days','3650',
                     '-subj','/O=MyTellPBX/CN=MyTellPBX WebRTC',
                     '-addext','keyUsage=digitalSignature,keyEncipherment',
                     '-addext','extendedKeyUsage=serverAuth,clientAuth',
                     '-keyout',str(key),'-out',str(cert)])
        value=cert.read_bytes()+key.read_bytes()
        validate_material(value,openssl)
        return value

def identity(info):
    return (info.st_dev,info.st_ino,info.st_uid,info.st_gid,info.st_mode,
            info.st_size,info.st_mtime_ns,info.st_nlink)

def metadata(info,value):
    return dict(dev=info.st_dev,ino=info.st_ino,uid=info.st_uid,gid=info.st_gid,
                mode=stat.S_IMODE(info.st_mode),bytes=info.st_size,mtime_ns=info.st_mtime_ns,
                nlink=info.st_nlink,sha256=digest(value))

def readable(info,uid,gid,directory=False):
    bit=0o100 if directory else 0o400
    return bool(info.st_mode&(bit if info.st_uid==uid else bit>>3 if info.st_gid==gid else bit>>6))

class NativeTarget:
    def __init__(self,root,uid,gid,create=False):
        self.root=Path(root).absolute();self.uid=uid;self.gid=gid;self.fd=None
        if os.name!='posix' or self.root.resolve()!=self.root or self.root.is_symlink():
            raise ValueError('Native Linux directory root required')
        try:
            self.fd=self.walk(create)
            self.parent_identity=identity(os.fstat(self.fd))[:2]
        except OSError as error:
            self.close();raise ValueError('Native DTLS path refused') from error
        except Exception:
            self.close();raise
    def walk(self,create=False):
        fd=os.open(str(self.root),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            nodes=list(Path(RELATIVE).parent.parts)
            for index,part in enumerate(nodes):
                try:new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                except FileNotFoundError:
                    if not create:raise ValueError('Native DTLS parent is absent')
                    os.mkdir(part,0o755,dir_fd=fd)
                    new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                    if index==len(nodes)-1:
                        os.fchown(new,self.uid,self.gid);os.fchmod(new,0o751)
                os.close(fd);fd=new;info=os.fstat(fd)
                if info.st_uid not in (0,self.uid,os.geteuid()) or info.st_mode&0o002:
                    raise ValueError('Unsafe native DTLS parent ownership or permissions')
                if info.st_mode&0o020 and info.st_gid!=self.gid:
                    raise ValueError('Unrelated writable native DTLS group refused')
                if not readable(info,self.uid,self.gid,True):
                    raise ValueError('Native DTLS directory is not accessible to Asterisk')
            result=fd;fd=None;return result
        finally:
            if fd is not None:os.close(fd)
    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None
    def current(self):
        try:fd=os.open('asterisk.pem',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=self.fd)
        except FileNotFoundError:return None
        except OSError as error:raise ValueError('Native DTLS file path refused') from error
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size>MAXIMUM or before.st_uid not in (0,self.uid,os.geteuid()) or before.st_mode&0o002:
                raise ValueError('Unsafe or unsupported native DTLS file')
            if before.st_mode&0o020 and before.st_gid!=self.gid:
                raise ValueError('Unrelated writable DTLS file group refused')
            with os.fdopen(fd,'rb',closefd=False)as stream:value=stream.read(MAXIMUM+1)
            if len(value)>MAXIMUM or identity(before)!=identity(os.fstat(fd)):
                raise ValueError('Native DTLS file changed during read')
            return before,value
        finally:os.close(fd)
    def verify(self,before):
        other=self.walk()
        try:
            if identity(os.fstat(other))[:2]!=self.parent_identity:
                raise ValueError('Native DTLS parent was replaced')
        finally:os.close(other)
        current=self.current()
        if before is None:
            if current is not None:raise ValueError('A native DTLS file appeared; retained')
        elif current is None or identity(current[0])!=identity(before[0]) or current[1]!=before[1]:
            raise ValueError('Native DTLS preimage changed; retained')
    def staged(self,value,uid,gid,mode):
        name='.mytell-dtls-'+os.urandom(12).hex()
        fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.fd)
        try:
            with os.fdopen(fd,'wb',closefd=False)as out:
                out.write(value);out.flush();os.fsync(fd)
            os.fchown(fd,uid,gid);os.fchmod(fd,mode);info=os.fstat(fd)
            if info.st_size!=len(value):raise ValueError('DTLS staged file was not fully written')
            return name,identity(info)[:2]
        except Exception:
            os.unlink(name,dir_fd=self.fd);raise
        finally:os.close(fd)
    def owns(self,owned,value):
        current=self.current()
        return current is not None and identity(current[0])[:2]==owned and current[1]==value
    def unlink_stage(self,name):
        try:os.unlink(name,dir_fd=self.fd)
        except FileNotFoundError:pass

def private_backup_root(root,backup):
    root=Path(root).absolute();backup=Path(backup).absolute()
    try:parts=backup.relative_to(root).parts
    except ValueError:raise ValueError('DTLS backup must remain inside the selected root')
    if not parts:raise ValueError('A separate private DTLS backup path is required')
    current=root
    for index,part in enumerate(parts):
        current=current/part
        if not current.exists() and not current.is_symlink():current.mkdir(mode=0o700)
        info=current.lstat()
        if not stat.S_ISDIR(info.st_mode) or current.is_symlink() or info.st_uid!=os.geteuid() or info.st_mode&0o022:
            raise ValueError('Unsafe private DTLS backup directory')
        if index==len(parts)-1 and stat.S_IMODE(info.st_mode)!=0o700:
            raise ValueError('DTLS backup root must be private0700')
    return backup

def backup_empty(backup,before):
    directory=Path(tempfile.mkdtemp(prefix='empty-',dir=str(backup)))
    for name,value in [('original.pem',before[1]),('receipt.json',(json.dumps(dict(schema=1,owner='MyTellPBX',path='/'+RELATIVE,before=metadata(*before)),sort_keys=True,indent=2)+'\n').encode('utf-8'))]:
        fd=os.open(str(directory/name),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb')as stream:stream.write(value);stream.flush();os.fsync(stream.fileno())
    return directory

def restore_context(paths):
    run_command(['/usr/sbin/restorecon','--']+[str(path)for path in paths])

def prepare(root,backup_root,uid,gid,check=False,openssl='/usr/bin/openssl',relabel=restore_context):
    if type(uid)is not int or type(gid)is not int or uid<0 or gid<0:
        raise ValueError('Explicit native Asterisk identity required')
    target=NativeTarget(root,uid,gid,create=False) if check else NativeTarget(root,uid,gid,create=True)
    path=Path(root).absolute()/RELATIVE
    try:
        before=target.current()
        if before is not None and before[1]:
            if not readable(before[0],uid,gid):raise ValueError('Native DTLS private key is unreadable to Asterisk')
            fingerprint=validate_material(before[1],openssl);target.verify(before)
            return dict(status='valid'if check else'preserved',fingerprint_sha256=fingerprint)
        if check:raise ValueError('Native DTLS certificate is absent or empty')
        if before is not None:
            info=before[0]
            if info.st_size!=0 or info.st_uid!=uid or info.st_gid!=gid or stat.S_IMODE(info.st_mode)!=0o664 or info.st_nlink!=1:
                raise ValueError('Unknown empty DTLS material retained')
        backup=private_backup_root(Path(root),backup_root)
        value=generate_material(openssl,backup);fingerprint=validate_material(value,openssl)
        target.verify(before)
        if before is not None:backup_empty(backup,before)
        name,owned=target.staged(value,uid,gid,0o600)
        try:
            target.verify(before)
            if before is None:
                os.link(name,'asterisk.pem',src_dir_fd=target.fd,dst_dir_fd=target.fd,follow_symlinks=False)
                target.unlink_stage(name)
            else:os.replace(name,'asterisk.pem',src_dir_fd=target.fd,dst_dir_fd=target.fd)
            os.fsync(target.fd)
            current=target.current()
            if current is None or identity(current[0])[:2]!=owned or current[1]!=value:
                raise ValueError('Published native DTLS material differs')
            target.verify(current)
            relabel([path])
            target.verify(current)
            if not target.owns(owned,value):raise ValueError('Native DTLS material changed after labeling')
        except Exception:
            # Never remove or replace an operator's subsequently replaced file.
            if target.owns(owned,value):
                if before is None:os.unlink('asterisk.pem',dir_fd=target.fd)
                else:
                    rollback,_identity=target.staged(before[1],before[0].st_uid,before[0].st_gid,stat.S_IMODE(before[0].st_mode))
                    os.replace(rollback,'asterisk.pem',src_dir_fd=target.fd,dst_dir_fd=target.fd)
                    os.utime('asterisk.pem',ns=(before[0].st_atime_ns,before[0].st_mtime_ns),dir_fd=target.fd,follow_symlinks=False)
                os.fsync(target.fd)
            raise
        finally:target.unlink_stage(name)
        return dict(status='created'if before is None else'repaired-empty',fingerprint_sha256=fingerprint)
    finally:target.close()

def service_identity():
    import pwd,grp
    user=pwd.getpwnam('asterisk');group=grp.getgrnam('asterisk')
    if user.pw_uid<=0 or group.gr_gid<=0 or user.pw_gid!=group.gr_gid:
        raise ValueError('Native Asterisk service identity is unavailable')
    return user.pw_uid,group.gr_gid

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default='/')
    parser.add_argument('--backup-root',default='/var/lib/mytelpbx-installer/webrtc-dtls')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    if os.name!='posix' or not hasattr(os,'geteuid') or os.geteuid()!=0:parser.error('Native DTLS preparation requires Linux root')
    try:
        uid,gid=service_identity()
        result=prepare(args.root,args.backup_root,uid,gid,check=args.check)
        print('MyTellPBX WebRTC DTLS: '+result['status']+'; SHA256 '+result['fingerprint_sha256'])
        return 0
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):
        print('MyTellPBX DTLS refused; existing material and private backups retained.',file=sys.stderr)
        return 1
if __name__=='__main__':raise SystemExit(main())
