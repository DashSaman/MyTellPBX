"""Collector contracts: synthetic archives and fake native DNF; never install."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import tarfile
import sys
import types
import gzip
import contextlib
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        script=ROOT/'scripts/collect-installer-media.py'
        self.assertTrue(script.is_file(),'Reproducible offline collector is missing')
        spec=importlib.util.spec_from_file_location('media_collector_fixture',str(script))
        self.c=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.c)

    def test_kernel_and_minimal_prerequisites_are_real_resolver_roots(self):
        roots=self.c.package_roots(['asterisk20','httpd'],['issabel'], '4.18.0-553.134.1.el8_10.x86_64')
        for name in ['@^minimal-environment','policycoreutils','python3.11','python3.11-pip',
                     'kernel-devel-4.18.0-553.134.1.el8_10.x86_64','kernel-headers-4.18.0-553.134.1.el8_10.x86_64']:
            self.assertIn(name,roots)
        self.assertEqual(len(roots),len(set(roots)))
        with self.assertRaises(ValueError):self.c.package_roots([],[],'latest')

    def test_unsigned_missing_key_bad_digest_or_nonzero_rpm_result_fail(self):
        good='Header V4 RSA/SHA256 Signature, key ID 1234abcd: OK\nPayload SHA256 digest: OK\n'
        self.c.require_signature(0,good)
        for rc,text in [(1,good),(0,'digests OK'),(0,good+'NOKEY'),(0,good+'NOT OK'),(0,good+'BAD')]:
            with self.subTest(rc=rc,text=text),self.assertRaises(ValueError):self.c.require_signature(rc,text)

    def test_only_public_key_blocks_and_safe_repository_urls_are_accepted(self):
        public=b'-----BEGIN PGP PUBLIC KEY BLOCK-----\nfixture\n-----END PGP PUBLIC KEY BLOCK-----\n'
        self.c.require_public_key(public)
        for value in [public.replace(b'PUBLIC',b'PRIVATE'),b'not a key',public+b'-----BEGIN PRIVATE KEY-----']:
            with self.assertRaises(ValueError):self.c.require_public_key(value)
        for url in ['https://repo.example/path','file:///fixed/public/key']:self.c.safe_url(url)
        for url in ['http://repo.example','https://u:password@repo.example','ftp://example/file']:
            with self.assertRaises(ValueError):self.c.safe_url(url)

    def test_modulemd_and_comps_are_retained_in_addition_to_rpm_metadata(self):
        calls=[];repo=self.root/'repo';repo.mkdir()
        source=SimpleNamespace(get_metadata_path=lambda kind:'cache' if kind in ['modules','group'] else '',
                               get_metadata_content=lambda kind:'modulemd bytes' if kind=='modules' else '<comps/>')
        proof=self.c.build_metadata('remi-modular',source,repo,self.root,lambda argv:calls.append(argv))
        self.assertEqual(calls[0][0],'createrepo_c')
        self.assertEqual([x[1] for x in calls[1:]],['--mdtype=modules','--mdtype=group'])
        self.assertIn('modules',proof);self.assertIn('group',proof)
        self.assertEqual((self.root/'remi-modular-modules.xml').read_bytes(),b'modulemd bytes')

    def test_empty_module_metadata_is_not_fabricated(self):
        calls=[];repo=self.root/'repo';repo.mkdir()
        source=SimpleNamespace(get_metadata_path=lambda kind:'',get_metadata_content=lambda kind:self.fail('unexpected read'))
        self.assertEqual(self.c.build_metadata('baseos',source,repo,self.root,lambda argv:calls.append(argv)),{})
        self.assertEqual(len(calls),1)

    def test_manifest_inventory_is_exact_and_contains_pinned_assets(self):
        names=['bootstrap/install.sh','payload/pbx.tgz','desk/desk.tgz','runtime/node.tar.xz','wheels/a.whl','geoip/source.gz','repos/local/repodata/repomd.xml','keys/local.asc']
        for name in names:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(name.encode())
        assets=dict(bootstrap=names[0],bundle=names[1],desk=names[2],node=names[3],wheels=[names[4]],
                    geoip=dict(path=names[5],month='2026-11'),repositories=[dict(id='local',path='repos/local',gpgkey='keys/local.asc')])
        manifest=self.c.make_manifest(self.root,assets)
        self.assertEqual(set(manifest['files']),set(names));self.assertEqual(manifest['platform'],'rocky8.10-x86_64')
        self.assertTrue(all(len(r['sha256'])==64 for r in manifest['files'].values()))

    def test_local_solver_proof_rejects_changed_nevras_or_remote_sources(self):
        a=SimpleNamespace(name='php',epoch=0,version='7.4',release='1',arch='x86_64',reponame='remi-modular')
        self.c.compare_closure([a],[a],{'remi-modular'})
        changed=SimpleNamespace(name='php',epoch=0,version='8.0',release='1',arch='x86_64',reponame='remi-modular')
        with self.assertRaises(ValueError):self.c.compare_closure([a],[changed],{'remi-modular'})
        a.reponame='unapproved'
        with self.assertRaises(ValueError):self.c.compare_closure([a],[a],{'remi-modular'})

    def test_existing_output_is_never_overwritten(self):
        output=self.root/'existing';output.mkdir();(output/'owned').write_bytes(b'preserve')
        with self.assertRaises(ValueError):self.c.create_output(output)
        self.assertEqual((output/'owned').read_bytes(),b'preserve')

    def test_local_dvd_rpm_is_copied_without_modifying_source_or_adopting_collision(self):
        source=self.root/'dvd/Packages/kernel-1-1.x86_64.rpm';source.parent.mkdir(parents=True);source.write_bytes(b'signed fixture')
        destination=self.root/'new/Packages';destination.mkdir(parents=True)
        self.assertTrue(hasattr(self.c,'stage_rpm'),'Local DNF repo ignores pkgdir; explicit staging is required')
        copied=self.c.stage_rpm(source,destination,len(b'signed fixture'))
        self.assertEqual(copied,destination/source.name);self.assertEqual(copied.read_bytes(),source.read_bytes())
        self.assertEqual(source.read_bytes(),b'signed fixture')
        self.assertEqual(self.c.stage_rpm(source,destination,len(b'signed fixture')),copied)
        copied.write_bytes(b'collision')
        with self.assertRaises(ValueError):self.c.stage_rpm(source,destination,len(b'signed fixture'))
        self.assertEqual(copied.read_bytes(),b'collision')

    def test_pinned_cached_asset_is_copied_and_wrong_cache_is_fatal(self):
        cache=self.root/'cache';cache.mkdir();(cache/'node.tar.xz').write_bytes(b'node')
        expected=hashlib.sha256(b'node').hexdigest();out=self.root/'out'
        self.c.fetch_asset('https://nodejs.org/node.tar.xz',out,expected,100,cache)
        self.assertEqual(out.read_bytes(),b'node')
        with self.assertRaises(ValueError):self.c.fetch_asset('https://nodejs.org/node.tar.xz',self.root/'other','0'*64,100,cache)
        self.assertFalse((self.root/'other').exists())

    def test_native_dnf_is_configured_in_a_private_empty_root_without_transactions(self):
        events=[]
        class Repo:
            def __init__(self,name):self.id=name;self.baseurl=['https://repo.example/'];self.metalink=self.mirrorlist=''
            def enable(self):events.append(('enable',self.id))
            def disable(self):events.append(('disable',self.id))
            def add_metadata_type_to_download(self,kind):events.append(('metadata',kind))
        class Base:
            def __init__(self):self.conf=SimpleNamespace(substitutions={});self.repos={k:Repo(k) for k in ['baseos','unselected']}
            def read_all_repos(self):events.append('read')
            def fill_sack(self,**kw):events.append(('sack',kw))
            def close(self):events.append('close')
            def do_transaction(self):raise AssertionError('Host transaction forbidden')
        module=lambda base:SimpleNamespace(enable=lambda specs:events.append(('stream',specs)))
        base=self.c.configured_base(self.root/'private',self.root,['baseos'],SimpleNamespace(Base=Base),module)
        self.assertNotEqual(base.conf.installroot,'/');self.assertTrue(base.conf.installroot.startswith(str(self.root)))
        self.assertIn(('sack',{'load_system_repo':False}),events)
        self.assertIn(('stream',['php:remi-7.4']),events);self.assertIn(('disable','unselected'),events)
        self.assertTrue(base.conf.install_weak_deps)

    def test_source_and_local_closures_retain_recommended_feature_packages(self):
        """Model Recommends explicitly; the native online profile enables weak deps."""
        class Repo:
            id='baseos';baseurl=['https://repo.example/'];metalink=mirrorlist=''
            def enable(self):pass
            def add_metadata_type_to_download(self,kind):pass
        def package(name):
            return SimpleNamespace(name=name,epoch=0,version='1',release='1',arch='x86_64',
                                   downloadsize=5,installed=False,reponame='baseos')
        class Base:
            def __init__(self):self.conf=SimpleNamespace(substitutions={});self.repos={'baseos':Repo()}
            def read_all_repos(self):pass
            def fill_sack(self,**kw):pass
            def read_comps(self,**kw):pass
            def install_specs(self,roots):self.roots=roots
            def resolve(self,**kw):
                # Native solver includes a package's Recommends when this policy is true.
                names=self.roots+(['recommended-feature'] if self.conf.install_weak_deps else [])
                self.transaction=SimpleNamespace(install_set=[package(n) for n in names],remove_set=[])
            def close(self):pass
        selected=[]
        for phase in ['source','local']:
            base=self.c.configured_base(self.root/phase,self.root,['baseos'],SimpleNamespace(Base=Base),
                                        lambda value:SimpleNamespace(enable=lambda names:None))
            packages=self.c.resolve(base,['pbx-feature'])
            self.assertEqual({p.name for p in packages},{'pbx-feature','recommended-feature'})
            selected.append(packages)
        self.c.compare_closure(selected[0],selected[1],{'baseos'})
        with self.assertRaises(ValueError):self.c.compare_closure(selected[0],selected[1][:-1],{'baseos'})

    def test_empty_root_resolution_refuses_removals_installed_or_wrong_arch_packages(self):
        package=SimpleNamespace(downloadsize=5,installed=False,arch='x86_64')
        events=[];transaction=SimpleNamespace(install_set=[package],remove_set=[])
        base=SimpleNamespace(transaction=transaction,read_comps=lambda **kw:events.append(kw),
                             install_specs=lambda roots:events.append(roots),resolve=lambda **kw:events.append(kw))
        self.assertEqual(self.c.resolve(base,['httpd']),[package])
        package.installed=True
        with self.assertRaises(ValueError):self.c.resolve(base,['httpd'])
        package.installed=False;package.arch='i686'
        with self.assertRaises(ValueError):self.c.resolve(base,['httpd'])
        package.arch='x86_64';transaction.remove_set=['unexpected']
        with self.assertRaises(ValueError):self.c.resolve(base,['httpd'])

    def test_input_archive_pins_and_real_payload_package_lists_drive_the_plan(self):
        def archive(path,files):
            with tarfile.open(path,'w:gz') as tar:
                for name,data in files.items():
                    member=tarfile.TarInfo(name);member.size=len(data);tar.addfile(member,io.BytesIO(data))
        desk=self.root/'desk.tgz';bundle=self.root/'bundle.tgz';bootstrap=self.root/'install.sh'
        vad=dict(python_version='3.11',architecture='x86_64',packages=[dict(name=n) for n in self.c.WHEELS])
        archive(desk,{'myteldesk-1.1.2/installer/runtime.json':json.dumps(dict(version='v24.22.3',sha256='a'*64)).encode(),
                      'myteldesk-1.1.2/backend/vad/runtime.json':json.dumps(vad).encode()})
        pin=dict(repository='DashSaman/MytelDesk',version='1.1.2',sha256=self.c.digest(desk))
        archive(bundle,{'mytelpbx-bundle-7.6.2/installer/myteldesk-release.json':json.dumps(pin).encode(),
                        'mytelpbx-bundle-7.6.2/installer/packages/rocky8-stage1.txt':b'httpd\nasterisk20\n',
                        'mytelpbx-bundle-7.6.2/installer/packages/rocky8-stage2-asterisk20.txt':b'issabel\n'})
        bootstrap.write_text('MYTELLPBX_VERSION="7.6.2"\nMYTELLPBX_BUNDLE_SHA256="'+self.c.digest(bundle)+'"\n')
        value=self.c.inputs(bootstrap,bundle,desk,'4.18.0-553.134.1.el8_10.x86_64')
        self.assertIn('issabel',value['roots']);self.assertEqual(value['desk']['version'],'1.1.2')
        bundle.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.c.inputs(bootstrap,bundle,desk,'4.18.0-553.134.1.el8_10.x86_64')

    def test_complete_collector_wires_fake_solver_signatures_metadata_assets_and_manifest(self):
        """Synthetic native clients only; this is not a real signature/closure proof."""
        c=self.c;output=self.root/'depot';calls=[];bases=[]
        metadata={'modules':b'---\ndocument: modulemd\nfixture: true\n','group':b'<comps/>\n'}
        public=b'-----BEGIN PGP PUBLIC KEY BLOCK-----\nsynthetic fixture\n-----END PGP PUBLIC KEY BLOCK-----\n'
        payloads={'node-v24.22.3-linux-x64.tar.xz':b'node archive','dbip-country-lite-2026-11.csv.gz':gzip.compress(b'country fixture')}
        wheels=[]
        for name in sorted(c.WHEELS):
            filename=name.replace('-','_')+'-1.0.whl';data=('wheel '+name).encode();payloads[filename]=data
            wheels.append(dict(name=name,filename=filename,url='https://files.pythonhosted.org/packages/f/'+filename,
                               sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
        for name in ['bootstrap','bundle','desk']:(self.root/name).write_bytes(('public '+name).encode())
        release=dict(version='7.6.2',bootstrap_sha256=c.digest(self.root/'bootstrap'),bundle_sha256=c.digest(self.root/'bundle'),
                     desk=dict(version='1.1.2',sha256=c.digest(self.root/'desk')),roots=['httpd','php'],
                     node=dict(version='v24.22.3',sha256=hashlib.sha256(payloads['node-v24.22.3-linux-x64.tar.xz']).hexdigest()),
                     vad=dict(packages=wheels))
        class Repo:
            def __init__(self,name,local):
                self.id=name;self.original_dvd=not local and name=='baseos';self.local=local;self._pkgdir=''
                origin=output/'repos'/name if local else dvd if self.original_dvd else None
                self.baseurl=[origin.as_uri()] if origin is not None else ['https://repo.example/'+name]
                self.mirrorlist=self.metalink='';self.gpgkey=['https://keys.example/'+name+'.asc']
                self.local=local
            @property
            def pkgdir(self):
                # Match actual DNF4: setting pkgdir has no effect for file:// repos.
                return str(output/'repos'/self.id) if self.local else str(dvd) if self.original_dvd else self._pkgdir
            @pkgdir.setter
            def pkgdir(self,value):self._pkgdir=value
            def enable(self):pass
            def disable(self):pass
            def add_metadata_type_to_download(self,kind):pass
            def get_metadata_path(self,kind):return 'present' if kind in metadata else ''
            def get_metadata_content(self,kind):
                return (output/'repos'/self.id/'repodata'/('fixture-'+kind)).read_bytes() if self.local else metadata[kind]
        class Package:
            epoch=0;version='1';release='1';arch='x86_64';downloadsize=len(b'synthetic RPM fixture');installed=False
            def __init__(self,name,repo):self.name=name;self.repo=repo;self.reponame=repo.id
            def localPkg(self):return str(Path(self.repo.pkgdir)/('Packages' if self.repo.local or self.repo.original_dvd else '')/(self.name+'-1-1.x86_64.rpm'))
        class Base:
            def __init__(self):
                self.conf=SimpleNamespace(substitutions={});self.local=bool(bases);bases.append(self)
                self.repos={name:Repo(name,self.local) for name in ['baseos','remi-modular']}
            def read_all_repos(self):pass
            def fill_sack(self,**kw):self.sack_args=kw
            def read_comps(self,**kw):pass
            def install_specs(self,roots):self.roots=roots
            def resolve(self,**kw):
                self.transaction=SimpleNamespace(install_set=[Package('httpd',self.repos['baseos']),Package('php',self.repos['remi-modular'])],remove_set=[])
            def download_packages(self,packages):
                calls.append('download')
                for package in packages:
                    if not package.repo.original_dvd:Path(package.localPkg()).write_bytes(b'synthetic RPM fixture')
            def close(self):calls.append('close')
            def do_transaction(self):raise AssertionError('A host transaction must never run')
        dnf=types.ModuleType('dnf');dnf.Base=Base
        module=types.ModuleType('dnf.module.module_base');module.ModuleBase=lambda base:SimpleNamespace(enable=lambda names:calls.append(tuple(names)))
        class Response(io.BytesIO):
            def __init__(self,url):super().__init__(public if url.startswith('https://keys.example/') else payloads[url.rsplit('/',1)[-1]]);self.url=url
            def geturl(self):return self.url
        def command(argv,**kwargs):
            calls.append(argv)
            if argv[0]=='createrepo_c':
                folder=Path(argv[-1])/'repodata';folder.mkdir();(folder/'repomd.xml').write_bytes(b'<repomd/>')
            elif argv[0]=='modifyrepo_c':
                kind=argv[1].split('=',1)[1];shutil_source=Path(argv[2]).read_bytes();(Path(argv[-1])/('fixture-'+kind)).write_bytes(shutil_source)
            data=b'Header V4 RSA/SHA256 Signature, key ID 1234abcd: OK\n' if '--checksig' in argv else b''
            return SimpleNamespace(returncode=0,stdout=data,stderr=b'')
        args=SimpleNamespace(output=output,reposdir=self.root,repo=['baseos','remi-modular'],
                             bootstrap=self.root/'bootstrap',bundle=self.root/'bundle',desk_archive=self.root/'desk',
                             kernel_release='4.18.0-553.134.1.el8_10.x86_64',cache_dir=None,geoip_month='2026-11',geoip_sha256=None)
        dvd=self.root/'originalDVD';(dvd/'Packages').mkdir(parents=True)
        original=dvd/'Packages/httpd-1-1.x86_64.rpm';original.write_bytes(b'synthetic RPM fixture')
        with mock.patch.dict(sys.modules,{'dnf':dnf,'dnf.module':types.ModuleType('dnf.module'),'dnf.module.module_base':module}), \
             mock.patch.object(c,'urlopen',side_effect=lambda url,**kw:Response(url)),mock.patch.object(c.subprocess,'run',side_effect=command), \
             contextlib.redirect_stdout(io.StringIO()):
            try:c.collect(args,release)
            except ValueError as error:self.fail('Valid local-media source was refused: '+str(error))
        manifest=json.loads((output/'manifest.json').read_text());proof=json.loads((output/'collector-proof.json').read_text())
        self.assertEqual(len(manifest['wheels']),6);self.assertEqual(len(proof['packages']),2)
        self.assertTrue(proof['local_only_resolve']);self.assertTrue(all(p['signature_verified'] for p in proof['packages']))
        self.assertEqual(len(bases),2);self.assertTrue(all(b.sack_args=={'load_system_repo':False} for b in bases))
        self.assertEqual(calls.count('close'),2)
        self.assertEqual(original.read_bytes(),b'synthetic RPM fixture')
        self.assertEqual((output/'repos/baseos/Packages'/original.name).read_bytes(),original.read_bytes())
        self.assertTrue(all('do_transaction' not in str(call) for call in calls))


if __name__=='__main__':unittest.main()
