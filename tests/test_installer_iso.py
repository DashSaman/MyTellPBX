"""Pure ISO/firstboot contracts; never run packages, systemd, SSH or a VM."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import configparser
import gzip
import struct
import xml.etree.ElementTree as ET

REPO=Path(__file__).resolve().parents[1]


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class IsoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b=load(REPO/'scripts/build-installer-iso.py','iso_builder')
        cls.f=load(REPO/'installer/iso/media-firstboot.py','media_firstboot')

    def fixture(self,root):
        files={'bootstrap.sh':b'MYTELLPBX_BUNDLE_SHA256="'+b'0'*64+b'"\n','bundle.tgz':b'bundle','desk.tgz':b'desk','node.xz':b'node','wheels/a.whl':b'wheel','geoip.csv.gz':b'geo','repo/repodata/repomd.xml':b'<repomd/>','repo/key.pub':b'public'}
        files['bootstrap.sh']=files['bootstrap.sh'].replace(b'0'*64,hashlib.sha256(files['bundle.tgz']).hexdigest().encode())
        for name,raw in files.items():
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);p.chmod(0o600)
        d={'schema':1,'owner':'MyTellPBX','platform':'rocky8.10-x86_64','bootstrap':'bootstrap.sh','bundle':'bundle.tgz','desk':'desk.tgz','node':'node.xz','wheels':['wheels/a.whl'],'geoip':{'path':'geoip.csv.gz','month':'2026-11'},'repositories':[{'id':'media','path':'repo','gpgkey':'repo/key.pub'}],
           'files':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}for name,raw in files.items()}}
        raw=(json.dumps(d)+'\n').encode();(root/'manifest.json').write_bytes(raw);(root/'manifest.json').chmod(0o600)
        return d,hashlib.sha256(raw).hexdigest()

    def test_depot_exact_hashes_and_bundle_pin(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);manifest,digest=self.fixture(root)
            actual=self.f.read_depot(root,digest,owner_uid=getattr(os,'getuid',lambda:0)())
            self.assertEqual(actual,manifest)
            (root/'bundle.tgz').write_bytes(b'drift')
            with self.assertRaises(ValueError):self.f.read_depot(root,digest,owner_uid=getattr(os,'getuid',lambda:0)())

    def test_depot_rejects_unknown_file_and_parent_escape(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);manifest,digest=self.fixture(root);(root/'private.env').write_text('not an asset')
            with self.assertRaises(ValueError):self.f.read_depot(root,digest,owner_uid=getattr(os,'getuid',lambda:0)())
        for value in('../secret','/etc/shadow','a/../b','a\\b','a\nb'):
            with self.assertRaises(ValueError):self.f.relative(value)

    def test_partial_failure_reboot_resumes_no_fake_completion(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d)/'depot';root.mkdir();manifest,digest=self.fixture(root);state=Path(d)/'state';calls=[]
            def run(args,env):calls.append((args,env));return 42 if len(calls)==1 else 0
            self.assertEqual(self.f.run_firstboot(root,digest,state,run,owner_uid=getattr(os,'getuid',lambda:0)()),42)
            self.assertFalse((state/'complete.json').exists())
            self.assertEqual(self.f.run_firstboot(root,digest,state,run,owner_uid=getattr(os,'getuid',lambda:0)()),0)
            self.assertEqual(len(calls),2);self.assertEqual(calls[-1][1]['MYTELL_SKIP_UPDATE'],'1')
            self.assertEqual(calls[-1][1]['MYTELL_MEDIA_MANIFEST_SHA256'],digest)
            self.assertEqual(calls[-1][1]['MYTELL_MEDIA_ROOT'],str(root))
            self.assertNotIn('MYTELL_ADMIN_PASS',calls[-1][1])
            self.assertEqual(self.f.run_firstboot(root,digest,state,run,owner_uid=getattr(os,'getuid',lambda:0)()),0)
            self.assertEqual(len(calls),2)

    def test_unknown_state_refuses_before_installer_and_completion_write_is_atomic(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d)/'depot';root.mkdir();_,digest=self.fixture(root);state=Path(d)/'state';state.mkdir(mode=0o700)
            (state/'unrelated').write_text('preserve')
            calls=[]
            with self.assertRaises(ValueError):self.f.run_firstboot(root,digest,state,lambda *a:calls.append(a),owner_uid=getattr(os,'getuid',lambda:0)())
            self.assertEqual(calls,[]);self.assertEqual((state/'unrelated').read_text(),'preserve')
            (state/'unrelated').unlink()
            with patch.object(self.f.json,'dump',side_effect=OSError('offline full disk')):
                with self.assertRaises(OSError):self.f.run_firstboot(root,digest,state,lambda *a:0,owner_uid=getattr(os,'getuid',lambda:0)())
            self.assertFalse((state/'complete.json').exists());self.assertEqual(list(state.iterdir()),[])

    @unittest.skipUnless(os.name=='posix','POSIX symlink ownership boundary')
    def test_depot_symlink_refuses_even_if_content_matches(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d)/'depot';root.mkdir();_,digest=self.fixture(root);outside=Path(d)/'outside';outside.write_bytes((root/'desk.tgz').read_bytes())
            (root/'desk.tgz').unlink();(root/'desk.tgz').symlink_to(outside)
            with self.assertRaises(ValueError):self.f.read_depot(root,digest,owner_uid=os.getuid())

    def test_native_firstboot_interlock_is_real_depot_not_fake_stage(self):
        text=(REPO/'installer/iso/issabel-firstboot-media.conf').read_text()
        self.assertIn('ConditionPathExists=!/var/lib/mytelpbx-media/manifest.json',text)
        self.assertNotIn('/dev/null',text);self.assertNotIn('framework.done',text)
        unit=(REPO/'installer/iso/mytelpbx-firstboot.service').read_text()
        self.assertIn('TimeoutStartSec=infinity',unit);self.assertIn('Restart=no',unit)

    def test_kickstart_only_os_and_staging_no_hidden_wipe_or_credentials(self):
        text=(REPO/'installer/iso/mytelpbx.ks').read_text()
        active=[s.strip()for s in text.splitlines()if s.strip()and not s.lstrip().startswith('#')]
        for word in('clearpart','autopart','rootpw','user --','selinux --disabled','firewall --disabled','install_amp','retrieve_conf'):
            self.assertFalse(any(word in s for s in active),word)
        packages=text.split('%packages',1)[1].split('%end',1)[0]
        self.assertNotIn('issabel',packages);self.assertNotIn('asterisk',packages)
        self.assertIn('--nochroot',text);self.assertIn('/var/lib/mytelpbx-media',text)

    def test_boot_configs_brand_and_synchronise_labels_but_leave_rescue(self):
        raw="menu title Rocky Linux 8.10\nappend initrd=initrd.img inst.stage2=hd:LABEL=Rocky-8-10-x86_64-dvd quiet\nappend inst.stage2=hd:LABEL=Rocky-8-10-x86_64-dvd inst.rescue quiet\n"
        out=self.b.boot_config(raw,'Rocky-8-10-x86_64-dvd','MytelPBX-7.6.2','7.6.2')
        self.assertIn('MytelPBX',out);self.assertIn('Mytel.one',out);self.assertNotIn('https://',out);self.assertNotIn('Rocky-8-10-x86_64-dvd',out)
        lines=out.splitlines();self.assertIn('inst.ks=hd:LABEL=MytelPBX-7.6.2:/ks/mytelpbx.ks',lines[1])
        self.assertNotIn('inst.ks=',lines[2]);self.assertIn('inst.rescue',lines[2])

    def test_syslinux_root_branding_preserves_troubleshooting_submenu_and_boot_options(self):
        # Native Syslinux pattern: root title, then an independently named menu.
        raw=('menu title Rocky Linux 8.10\n'
             'label linux\n  menu label ^Install Rocky Linux 8.10\n'
             '  append initrd=initrd.img inst.stage2=hd:LABEL=Rocky-8-10-x86_64-dvd quiet rd.live.check\n'
             'menu begin ^Troubleshooting\n  menu title Troubleshooting\n'
             'label rescue\n  menu label ^Rescue a Rocky Linux system\n'
             '  append initrd=initrd.img inst.stage2=hd:LABEL=Rocky-8-10-x86_64-dvd inst.rescue quiet\n'
             'menu begin Advanced\n  menu title Advanced diagnostics\nmenu end\nmenu end\n')
        out=self.b.boot_config(raw,'Rocky-8-10-x86_64-dvd','MytelPBX-7.6.2','7.6.2')
        self.assertEqual([line.strip()for line in out.splitlines()if line.strip().startswith('menu title ')],
                         ['menu title MytelPBX 7.6.2 - Mytel.one',
                          'menu title Troubleshooting','menu title Advanced diagnostics'])
        self.assertIn('menu begin ^Troubleshooting\n',out);self.assertIn('menu begin Advanced\n',out)
        actual=[line.strip()for line in out.splitlines()if line.strip().startswith('append ')]
        self.assertEqual(actual,[
            'append initrd=initrd.img inst.stage2=hd:LABEL=MytelPBX-7.6.2 quiet rd.live.check inst.ks=hd:LABEL=MytelPBX-7.6.2:/ks/mytelpbx.ks',
            'append initrd=initrd.img inst.stage2=hd:LABEL=MytelPBX-7.6.2 inst.rescue quiet'])

    def test_output_scope_and_exclusive_publication_preserve_existing(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);source=root/'temporary';source.write_bytes(b'new');out=root/'output.iso';out.write_bytes(b'old')
            with self.assertRaises(FileExistsError):self.b.publish(source,out)
            self.assertEqual(out.read_bytes(),b'old')
            with self.assertRaises(ValueError):self.b.output_path(root/'../outside.iso',root)

    def test_product_templates_only_known_tokens(self):
        self.assertEqual(self.b.render('@VERSION@ @BASE_PRODUCT@',{'VERSION':'7.6.2','BASE_PRODUCT':'Rocky Linux'}),'7.6.2 Rocky Linux')
        with self.assertRaises(ValueError):self.b.render('@UNKNOWN@',{'VERSION':'7.6.2'})

    def test_native_buildstamp_variant_survives_product_overlay(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);stamp=root/'base';stamp.write_text('[Main]\nProduct=Rocky Linux\nVersion=8.10\nVariant=Minimal\nUUID=202606221745.x86_64\n[Compose]\nLorax=28.14.71-1\n',encoding='utf-8')
            stage=root/'stage';stage.mkdir()
            with patch.object(self.b,'command',return_value=b'controlled-cpio'):
                image=self.b.product_image(REPO,stage,stamp,'7.6.2')
            self.assertEqual(gzip.decompress(image.read_bytes()),b'controlled-cpio')
            result=configparser.ConfigParser();result.read(str(stage/'product/.buildstamp'),encoding='utf-8')
            self.assertEqual(result.get('Main','Product'),'MytelPBX');self.assertEqual(result.get('Main','Variant'),'Minimal')
            self.assertEqual(result.get('Main','Version'),'7.6.2')

    def test_bios_splash_uses_owned_screen_sized_svg(self):
        source=REPO/'installer/iso/boot-splash.svg'
        svg=ET.fromstring(source.read_text(encoding='utf-8'))
        self.assertEqual((svg.get('width'),svg.get('height'),svg.get('viewBox')),('640','480','0 0 640 480'))
        self.assertIn('MytelPBX',''.join(svg.itertext()));self.assertIn('Mytel.one',''.join(svg.itertext()));self.assertNotIn('https://',''.join(svg.itertext()))
        self.assertNotIn('Rocky',source.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory()as d:
            stage=Path(d);calls=[]
            def renderer(args,**kwargs):
                calls.append(args)
                Path(args[args.index('--output')+1]).write_bytes(b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+struct.pack('>II',640,480)+b'\x08\x06\x00\x00\x00'+b'\x00'*4)
                return b''
            with patch.object(self.b,'command',side_effect=renderer):
                output=self.b.boot_splash(REPO,stage)
            self.assertEqual(output,stage/'splash.png')
            self.assertEqual(calls[0][0],'rsvg-convert')
            self.assertIn(source,calls[0])

    def test_bios_splash_refuses_square_or_invalid_render(self):
        with tempfile.TemporaryDirectory()as d:
            stage=Path(d)
            for width,height in((300,300),(640,300)):
                def renderer(args,**kwargs):
                    Path(args[args.index('--output')+1]).write_bytes(b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+struct.pack('>II',width,height)+b'\x08\x06\x00\x00\x00'+b'\x00'*4)
                    return b''
                with patch.object(self.b,'command',side_effect=renderer):
                    with self.assertRaises(ValueError):self.b.boot_splash(REPO,stage)
            with patch.object(self.b,'command',return_value=b''):
                (stage/'splash.png').write_bytes(b'not a PNG')
                with self.assertRaises(ValueError):self.b.boot_splash(REPO,stage)


if __name__=='__main__':unittest.main(verbosity=2)
