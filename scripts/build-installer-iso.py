"""Build a private MytelPBX installation ISO from a pinned pure Rocky image."""
import argparse
import configparser
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ROCKY_SHA='231d21db029e900b305d8e23ff7a61d06bb4e873cb170bd4a85f4e6dd896748f'
ROCKY_BYTES=3368943616
OLD_LABEL='Rocky-8-10-x86_64-dvd'
PRODUCT_FILES=('.buildstamp','etc/anaconda/product.d/mytelpbx.conf',
               'usr/share/anaconda/pixmaps/mytelpbx.css','usr/share/anaconda/pixmaps/mytelpbx-wordmark.svg')
ISO_ASSETS=('media-firstboot.py','mytelpbx-firstboot.service','issabel-firstboot-media.conf')


def firstboot_module(repo):
    spec=importlib.util.spec_from_file_location('trusted_media_firstboot',repo/'installer/iso/media-firstboot.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as f:
        while True:
            raw=f.read(1024*1024)
            if not raw:break
            h.update(raw)
    return h.hexdigest()


def output_path(value,root=Path('/root/iso')):
    root=Path(root).resolve();p=Path(value)
    if not p.is_absolute()or p.parent.resolve()!=root or p.is_symlink()or p.suffix!='.iso':raise ValueError('Output must be a new ISO directly under /root/iso')
    if any(x.is_symlink()for x in(p.parent,)+tuple(p.parent.parents)):raise ValueError('Linked output directory')
    return p


def publish(source,target):
    # The temporary output is on the same filesystem; an existing asset is never replaced.
    os.link(str(source),str(target));os.unlink(str(source))


def render(text,values):
    def replace(match):
        key=match.group(1)
        if key not in values:raise ValueError('Unknown product template token')
        return values[key]
    return re.sub(r'@([A-Z_]+)@',replace,text)


def boot_config(text,old_label,new_label,version):
    if old_label not in text:raise ValueError('Unexpected boot label')
    text=text.replace(old_label,new_label)
    text=text.replace('Rocky Linux 8.10','MytelPBX '+version).replace('Rocky Linux system','MytelPBX system')
    if 'Issabel'in text:raise ValueError('Wrong base boot configuration')
    result=[]
    for line in text.splitlines():
        if line.lstrip().startswith('menu title '):line='menu title MytelPBX '+version+' - https://mytel.one'
        if line.lstrip().startswith('menuentry ')and'MytelPBX'in line:
            line=line.replace("' --class"," - https://mytel.one' --class",1)
        if 'inst.stage2='in line and not re.search(r'(?:^|\s)(?:inst\.rescue|rescue)(?:\s|$)',line):
            if 'inst.ks='in line:raise ValueError('Unexpected existing kickstart')
            line+=' inst.ks=hd:LABEL='+new_label+':/ks/mytelpbx.ks'
        result.append(line)
    return '\n'.join(result)+'\n'


def command(args,cwd=None,payload=None):
    options={'cwd':str(cwd)if cwd else None,'stdout':subprocess.PIPE,'stderr':subprocess.PIPE}
    if payload is None:options['stdin']=subprocess.DEVNULL
    else:options['input']=payload
    r=subprocess.run([str(a)for a in args],**options)
    if r.returncode:raise RuntimeError('Build tool failed: '+Path(str(args[0])).name)
    return r.stdout


def extract(iso,name,target):
    command(['xorriso','-osirrox','on','-indev',iso,'-extract','/'+name,target])


def product_image(repo,stage,stamp,version):
    cfg=configparser.ConfigParser(interpolation=None);cfg.read(str(stamp),encoding='utf-8')
    values={'VERSION':version,'BASE_PRODUCT':cfg.get('Main','Product'),'BASE_UUID':cfg.get('Main','UUID'),'BASE_LORAX':cfg.get('Compose','Lorax')}
    if any(not v or '\n'in v or '\r'in v for v in values.values()):raise ValueError('Invalid base buildstamp')
    if values['BASE_PRODUCT']!='Rocky Linux':raise ValueError('Non-Rocky installer runtime')
    if cfg.get('Main','Version')!='8.10'or values['BASE_UUID']!='202606221745.x86_64'or values['BASE_LORAX']!='28.14.71-1':raise ValueError('Unexpected pinned installer buildstamp')
    tree=stage/'product';tree.mkdir()
    for name in PRODUCT_FILES:
        source=repo/'installer/iso/product'/name
        if source.is_symlink()or not source.is_file():raise ValueError('Missing product asset')
        target=tree/name;target.parent.mkdir(parents=True,exist_ok=True)
        text=render(source.read_text(encoding='utf-8'),values)
        if name=='.buildstamp':
            custom=configparser.ConfigParser(interpolation=None);custom.read_string(text)
            for section in custom.sections():
                if not cfg.has_section(section):cfg.add_section(section)
                for key,value in custom.items(section):cfg.set(section,key,value)
            rendered=io.StringIO();cfg.write(rendered);text=rendered.getvalue()
        target.write_text(text,encoding='utf-8');target.chmod(0o644)
        os.utime(str(target),(0,0))
    for p in(tree,)+tuple(p for p in tree.rglob('*')if p.is_dir()):p.chmod(0o755);os.utime(str(p),(0,0))
    names=['.']+[p.relative_to(tree).as_posix()for p in sorted(tree.rglob('*'))]
    raw=command(['cpio','--null','-o','--format=newc','--reproducible','--owner=0:0'],tree,('\0'.join(names)+'\0').encode())
    image=stage/'product.img'
    with image.open('wb')as out:
        with gzip.GzipFile(filename='',mode='wb',fileobj=out,mtime=0)as z:z.write(raw)
    return image


def efi_image(image,stage,new_label,version):
    # Handle config files in the FAT image, not only the visible ISO copy (USB UEFI).
    listing=command(['mdir','-i',image,'-b','-/','::']).decode('utf-8')
    paths=[s.strip()for s in listing.splitlines()if s.strip().lower().endswith('/grub.cfg')]
    for i,name in enumerate(paths):
        if not name.startswith('::/')or '..'in name:raise ValueError('Unexpected EFI path')
        target=stage/('efi-grub-'+str(i)+'.cfg');command(['mcopy','-i',image,name,target])
        text=target.read_text(encoding='utf-8')
        if OLD_LABEL not in text:raise ValueError('Unexpected embedded EFI boot label')
        target.write_text(boot_config(text,OLD_LABEL,new_label,version),encoding='utf-8')
        command(['mcopy','-o','-i',image,target,name])
    return len(paths)


def boot_splash(repo,stage):
    source=repo/'installer/iso/boot-splash.svg'
    if source.is_symlink()or not source.is_file():raise ValueError('Missing owned BIOS splash')
    output=stage/'splash.png'
    command(['rsvg-convert','--format','png','--width','640','--height','480','--output',output,source])
    raw=output.read_bytes()
    if len(raw)<33 or raw[:16]!=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'or struct.unpack('>II',raw[16:24])!=(640,480):raise ValueError('BIOS splash must be a 640 by 480 PNG')
    return output


def plan(args):
    repo=Path(args.repo).resolve();source=Path(args.source_iso)
    if source.is_symlink()or not source.is_file()or source.stat().st_size!=ROCKY_BYTES or digest(source)!=ROCKY_SHA:raise ValueError('Pinned Rocky ISO changed')
    out=output_path(args.output)
    if any(p.exists()or p.is_symlink()for p in(out,out.with_suffix('.iso.json'),out.with_suffix('.iso.sha256'))):raise FileExistsError('Output already exists')
    version=(repo/'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',version):raise ValueError('Invalid release version')
    label='MytelPBX-'+version+'-x86_64'
    if len(label)>32:raise ValueError('ISO label too long')
    media=firstboot_module(repo);depot=Path(args.depot).resolve();manifest=media.read_depot(depot,args.manifest_sha256)
    bootstrap=(depot/manifest['bootstrap']).read_bytes()
    if re.findall(rb'(?m)^MYTELLPBX_VERSION="([0-9.]+)"\r?$',bootstrap)!=[version.encode()]:raise ValueError('Bootstrap/ISO version mismatch')
    stamp=Path(args.base_buildstamp)
    if stamp.is_symlink()or not stamp.is_file():raise ValueError('Native installer buildstamp required')
    return repo,source,out,version,label,depot,manifest,stamp


def build(args):
    if os.name!='posix'or os.geteuid()!=0:raise ValueError('Build on the root Linux lab host')
    repo,source,out,version,label,depot,manifest,stamp=plan(args)
    for tool in('xorriso','cpio','mdir','mcopy','implantisomd5','checkisomd5','rsvg-convert'):
        if not shutil.which(tool):raise ValueError('Required tool missing: '+tool)
    # Reuse the product media reader's full repository/platform policy before emitting media.
    common=command([sys.executable,'-B',repo/'installer/media.py','--root',depot,'--manifest-sha256',args.manifest_sha256,
                    '--bundle-sha256',manifest['files'][manifest['bundle']]['sha256'],'--plan'])
    if json.loads(common)['manifest_sha256']!=args.manifest_sha256:raise ValueError('Product media validation mismatch')
    with tempfile.TemporaryDirectory(prefix='.mytel-iso-',dir=str(out.parent))as directory:
        stage=Path(directory);tree=stage/'add';tree.mkdir();media=tree/'mytelpbx';media.mkdir()
        for name in ISO_ASSETS:
            source_asset=repo/'installer/iso'/name
            if source_asset.is_symlink()or not source_asset.is_file():raise ValueError('Missing firstboot asset')
            shutil.copyfile(str(source_asset),str(media/name));(media/name).chmod(0o644)
        (media/'mytelpbx-media.json').write_text(json.dumps({'root':'/var/lib/mytelpbx-media','manifest_sha256':args.manifest_sha256})+'\n',encoding='utf-8')
        ks=tree/'ks/mytelpbx.ks';ks.parent.mkdir();shutil.copyfile(str(repo/'installer/iso/mytelpbx.ks'),str(ks))
        bios=stage/'isolinux.cfg';grub=stage/'grub.cfg';efi=stage/'efiboot.img';info=stage/'treeinfo'
        for name,path in [('isolinux/isolinux.cfg',bios),('EFI/BOOT/grub.cfg',grub),('images/efiboot.img',efi),('.treeinfo',info)]:extract(source,name,path)
        for p in(bios,grub):p.write_text(boot_config(p.read_text(encoding='utf-8'),OLD_LABEL,label,version),encoding='utf-8')
        embedded=efi_image(efi,stage,label,version)
        image=product_image(repo,stage,stamp,version)
        splash=boot_splash(repo,stage)
        cfg=configparser.ConfigParser(interpolation=None);cfg.read(str(info),encoding='utf-8')
        if cfg.get('release','name')!='Rocky Linux'or cfg.get('release','version')!='8.10':raise ValueError('Wrong OS install tree')
        cfg.set('checksums','images/product.img','sha256:'+digest(image));cfg.set('checksums','images/efiboot.img','sha256:'+digest(efi))
        with info.open('w',encoding='utf-8')as f:cfg.write(f)
        receipt={'schema':1,'product':'MytelPBX','version':version,'source_iso_sha256':ROCKY_SHA,'media_manifest_sha256':args.manifest_sha256,
                 'embedded_efi_configs':embedded,'os':'Rocky Linux 8.10','source_payloads':len(manifest['files']),'offline_profile':True,'boot_acceptance':False,
                 'base_buildstamp_sha256':digest(stamp),'product_image_sha256':digest(image),'bios_splash_sha256':digest(splash),'bios_splash_pixels':[640,480],
                 'source_files':{name:digest(repo/name)for name in ['scripts/build-installer-iso.py','installer/iso/mytelpbx.ks','installer/iso/boot-splash.svg']+
                                 ['installer/iso/'+name for name in ISO_ASSETS]+['installer/iso/product/'+name for name in PRODUCT_FILES]}}
        (media/'iso-inputs.json').write_text(json.dumps(receipt,sort_keys=True)+'\n',encoding='utf-8')
        temporary=stage/'built.iso'
        command(['xorriso','-indev',source,'-outdev',temporary,'-volid',label,
                 '-map',media,'/mytelpbx','-map',tree/'ks','/ks','-map',depot,'/mytelpbx/depot','-map',bios,'/isolinux/isolinux.cfg','-map',grub,'/EFI/BOOT/grub.cfg',
                 '-map',splash,'/isolinux/splash.png','-map',efi,'/images/efiboot.img',
                 '-map',image,'/images/product.img','-map',info,'/.treeinfo','-boot_image','any','replay'])
        command(['implantisomd5','--force',temporary]);command(['checkisomd5',temporary])
        # Verify actual ISO payload bytes before publishing a single immutable output.
        actual=stage/'verify-depot';extract(temporary,'mytelpbx/depot',actual)
        firstboot_module(repo).read_depot(actual,args.manifest_sha256)
        actual_splash=stage/'verify-splash.png';extract(temporary,'isolinux/splash.png',actual_splash)
        if digest(actual_splash)!=digest(splash):raise ValueError('ISO BIOS splash differs from validated render')
        for name in('isolinux/isolinux.cfg','EFI/BOOT/grub.cfg'):
            p=stage/('check-'+name.replace('/','-'));extract(temporary,name,p)
            text=p.read_text(encoding='utf-8')
            if OLD_LABEL in text or 'Issabel'in text or 'https://mytel.one'not in text and name.startswith('isolinux'):raise ValueError('Boot branding verification failed')
        if digest(source)!=ROCKY_SHA:raise ValueError('Source ISO changed')
        final_sha=digest(temporary);final_bytes=temporary.stat().st_size;publish(temporary,out)
        receipt.update(iso_sha256=final_sha,iso_bytes=final_bytes)
        with out.with_suffix('.iso.json').open('x',encoding='utf-8')as f:json.dump(receipt,f,indent=2);f.write('\n')
        with out.with_suffix('.iso.sha256').open('x',encoding='ascii')as f:f.write(final_sha+'  '+out.name+'\n')
    print(json.dumps(receipt,sort_keys=True));return 0


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--source-iso',required=True)
    p.add_argument('--depot',required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--base-buildstamp',required=True);p.add_argument('--output',required=True);p.add_argument('--build',action='store_true')
    a=p.parse_args()
    if a.build:return build(a)
    _,_,out,version,label,_,manifest,_=plan(a)
    print(json.dumps({'plan_only':True,'version':version,'label':label,'output':str(out),'payloads':len(manifest['files']),'media_manifest_sha256':a.manifest_sha256}));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:raise SystemExit('MytelPBX ISO refused: '+type(e).__name__+'; source media retained')
