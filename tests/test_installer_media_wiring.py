"""Run real Bash offline wiring with fake DNF/helpers; never provision a host."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


class MediaWiringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.events = self.base / 'events'
        self.bundle = self.base / 'bundle'
        for name in ['dnf-progress.py', 'geoip-update.py', 'prepare-geoip-module.py', 'install-myteldesk.py']:
            file = self.bundle / 'installer' / name; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('# inert fixture\n')
        repo = self.bundle / 'installer/repos/mytelpbx-base.repo.in'; repo.parent.mkdir(); repo.write_text('# inert repository fixture\n')
        self.defs = self.base / 'definitions.sh'
        self.defs.write_text((ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8').rsplit('\nmain "$@"', 1)[0], encoding='utf-8')

    def run_fixture(self, action, offline=True, extra='', failure=0):
        body = 'source ' + shlex.quote(self.defs.as_posix()) + '\n'
        for name, path in [('LOG', self.base/'log'), ('EVENTS',self.events),('BUNDLE_DIR',self.bundle),
                           ('STATE_DIR',self.base/'state'),('WORK_DIR',self.base/'work'),('WEB_ROOT',self.base/'web')]:
            body += name + '=' + shlex.quote(path.as_posix()) + '\n'
        body += 'MEDIA_ROOT=' + shlex.quote((self.base/'media').as_posix() if offline else '') + '\n'
        body += 'MEDIA_MANIFEST_SHA256=' + ('a'*64 if offline else '') + '\n'
        body += 'MEDIA_REPOS_DIR=' + shlex.quote((self.base/'local-repos').as_posix()) + '\n'
        body += 'MEDIA_GEOIP_SOURCE=' + shlex.quote((self.base/'country.gz').as_posix()) + '\n'
        body += 'MEDIA_GEOIP_SHA256=' + 'b'*64 + '\nMEDIA_GEOIP_MONTH=2026-11\n'
        body += 'FAIL_DNF=' + str(failure) + '\n'
        body += '''
event(){ printf '%s' "$1" >>"$EVENTS"; shift; printf '\\t%s' "$@" >>"$EVENTS"; printf '\\n' >>"$EVENTS"; }
step(){ :; }
say(){ :; }
stage_done(){ return 1; }
mark_stage(){ event COMPLETE "$@"; }
repair_platform_catalog(){ event REPAIR "$@"; }
dnf(){ event DNF "$@"; return "$FAIL_DNF"; }
curl(){ event NETWORK "$@"; return 28; }
cp(){ event COPY "$@"; }
chmod(){ :; }
grep(){ return 0; }
run_logged(){ "$@"; }
PY_BIN=fixture_python
fixture_python(){
 case "$*" in
  *dnf-progress.py*--check-log*) return 0;;
  *dnf-progress.py*) cat;;
  *geoip-update.py*) event GEOIP "$@";;
  *prepare-geoip-module.py*) event CONSUMER "$@";;
  *install-myteldesk.py*) event DESK "$@";;
  *repair-repository-transport.py*) event REPAIR_HELPER "$@";;
  *) return 99;;
 esac
}
'''
        body += extra + '\n' + action + '\n'
        file=self.base/'run.sh'; file.write_text(body, encoding='utf-8')
        result=subprocess.run([BASH,'--noprofile','--norc',str(file)],stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8',errors='replace',timeout=30)
        events=[line.rstrip('\t').split('\t') for line in self.events.read_text().splitlines()] if self.events.exists() else []
        return result,events

    def test_offline_repo_stage_never_downloads_remi_or_repairs_vendor_repos(self):
        result, events=self.run_fixture('stage_repos')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(any(e[0] in ['REPAIR','REPAIR_HELPER','COPY','NETWORK'] for e in events),events)
        dnf=[e for e in events if e[0]=='DNF']
        self.assertTrue(dnf)
        for event in dnf:
            self.assertTrue(any('reposdir=' in a for a in event),event)
            self.assertIn('--setopt=gpgcheck=1',event)
            self.assertFalse(any('https:' in a for a in event),event)

    def test_every_package_dnf_call_uses_local_repos_and_propagates_failure(self):
        result, events=self.run_fixture('run_dnf_logged packages -y install asterisk20',failure=23)
        self.assertEqual(result.returncode,23,result.stderr)
        dnf=next(e for e in events if e[0]=='DNF')
        self.assertTrue(any('reposdir=' in a for a in dnf)); self.assertIn('--setopt=localpkg_gpgcheck=1',dnf)

    def test_explicit_remote_package_is_refused_in_offline_mode(self):
        result,events=self.run_fixture('run_dnf_logged packages -y install https://remote/package.rpm')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(e[0]=='DNF' for e in events))

    def test_online_dnf_arguments_are_unchanged(self):
        result, events=self.run_fixture('run_dnf_logged packages -y install httpd',offline=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(next(e for e in events if e[0]=='DNF'),['DNF','-y','install','httpd'])

    def test_desk_and_geoip_get_only_the_bound_local_profile(self):
        result,events=self.run_fixture('stage_geoip; stage_myteldesk')
        self.assertEqual(result.returncode,0,result.stderr)
        geo=next(e for e in events if e[0]=='GEOIP');desk=next(e for e in events if e[0]=='DESK')
        self.assertIn('--offline-source',geo);self.assertIn('--offline-source-sha256',geo)
        self.assertIn('--offline-source-month',geo);self.assertIn('2026-11',geo)
        self.assertIn('--media-root',desk);self.assertIn('--media-manifest-sha256',desk)

    def test_offline_python_rpms_are_installed_before_desk_through_local_dnf(self):
        result,events=self.run_fixture('stage_myteldesk')
        self.assertEqual(result.returncode,0,result.stderr)
        packages=next((e for e in events if e[0]=='DNF' and 'python3.11' in e),None)
        self.assertIsNotNone(packages,'A depot file is not an installed Python3.11 runtime')
        self.assertIn('python3.11-pip',packages);self.assertTrue(any('reposdir=' in x for x in packages))
        self.assertLess(events.index(packages),next(i for i,e in enumerate(events) if e[0]=='DESK'))

    def test_missing_offline_python_closure_stops_before_desk(self):
        result,events=self.run_fixture('stage_myteldesk',failure=31)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(e[0]=='DESK' for e in events))

    def test_offline_main_validates_before_credentials_and_suppresses_both_repairs(self):
        stubs='''
preflight(){ :; }; acquire_lock(){ :; }; write_install_source(){ :; }; initialize_workspace(){ :; }
verify_bundle(){ event VERIFIED; }
initialize_media(){ event MEDIA; SKIP_UPDATE=1; }
ensure_credentials(){ event CREDENTIALS; }
stage_repos(){ event REPOS; }
stage_packages1(){ :; }; stage_tls(){ :; }; stage_packages2(){ :; }; stage_cli_status(){ :; }
stage_post_base(){ :; }; stage_framework_init(){ :; }; stage_mytel_layer(){ :; }
stage_webrtc_dtls(){ :; }; stage_geoip(){ :; }; stage_myteldesk(){ :; }; stage_selfcheck(){ :; }; finish(){ :; }
'''
        result,events=self.run_fixture('main',extra=stubs)
        self.assertEqual(result.returncode,0,result.stderr)
        names=[e[0] for e in events]
        self.assertIn('MEDIA',names);self.assertLess(names.index('MEDIA'),names.index('CREDENTIALS'))
        self.assertNotIn('REPAIR',names)
        self.assertFalse(any(e[0]=='DNF' and 'update' in e for e in events),events)
        self.assertIn(['COMPLETE','update'],events)

    def test_media_bundle_is_a_required_payload(self):
        source=(ROOT/'scripts/build-installer-bundle.sh').read_text()
        self.assertIn('copy_path "installer/media.py"',source)

    def initializer_fixture(self, fail=False):
        root=self.base/'media';root.mkdir();(root/'pbx.tgz').write_bytes(b'fixture')
        (self.base/'work').mkdir();(self.base/'state').mkdir()
        helper='''from pathlib import Path
class Media:
 def __init__(self,root):
  self.root=Path(root)
  self.manifest={'geoip':{'path':'country.gz','month':'2026-11'},'files':{'country.gz':{'sha256':'b'*64}}}
 def asset(self,name): return self.root/'pbx.tgz'
 def repo_text(self): return '[local]\\nbaseurl=file:///fixed/local\\ngpgcheck=1\\n'
def load(root,sha,bundle_sha256=None):
 assert sha=='a'*64 and bundle_sha256=='c'*64
 return Media(root)
'''
        if fail: helper=helper.replace('return Media(root)', "raise ValueError('fixture invalid media')")
        (self.bundle/'installer/media.py').write_text(helper)
        native_mkdir = 'mkdir(){ if [ "$1" = -m ]; then shift 2; command mkdir -p "$@"; else command mkdir "$@"; fi; }\n' if os.name == 'nt' else ''
        return (native_mkdir+'PY_BIN='+shlex.quote(sys.executable.replace('\\','/'))+'\ncheck_workspace(){ :; }\n'
                +'MYTELLPBX_BUNDLE_SHA256='+ 'c'*64+'\nMYTELL_BUNDLE_FILE='+shlex.quote((root/'pbx.tgz').as_posix())+'\n')

    def test_real_initializer_passes_pins_creates_private_catalog_and_skips_update(self):
        extra=self.initializer_fixture()
        result,events=self.run_fixture('initialize_media; event PROFILE "$SKIP_UPDATE" "$MEDIA_GEOIP_MONTH" "$MEDIA_GEOIP_SHA256"',extra=extra)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(['PROFILE','1','2026-11','b'*64],events)
        config=(self.base/'work/media-repos/mytelpbx-offline.repo').read_text()
        self.assertIn('baseurl=file:',config);self.assertIn('gpgcheck=1',config)
        self.assertEqual(json.loads((self.base/'state/media-source.json').read_text())['manifest_sha256'],'a'*64)

    def test_invalid_media_stops_before_any_package_or_credential_work(self):
        result,events=self.run_fixture('initialize_media; event CREDENTIALS; run_dnf_logged packages install httpd',extra=self.initializer_fixture(fail=True))
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(e[0] in ['DNF','NETWORK','CREDENTIALS'] for e in events),events)

    def test_incomplete_offline_profile_fails_before_network_preflight(self):
        result,events=self.run_fixture('check_network_prerequisites',extra="MEDIA_MANIFEST_SHA256=''\n")
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(e[0]=='NETWORK' for e in events))


if __name__=='__main__': unittest.main()
