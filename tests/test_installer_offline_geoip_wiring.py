"""Execute real Bash media ordering using disposable files and fake clients."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


@unittest.skipUnless(BASH, 'Real Bash orchestration required')
class OfflineGeoipWiringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.events = self.base / 'events'
        self.bundle = self.base / 'bundle'
        for name in ['offline-vendor-geoip.py', 'prepare-native-geoip.py', 'geoip-update.py', 'prepare-geoip-module.py']:
            path = self.bundle / 'installer' / name
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'# inert fixture\n')
        packages = self.bundle / 'installer/packages'; packages.mkdir()
        (packages / 'rocky8-stage2-asterisk20.txt').write_bytes(b'asterisk20\nGeoIP\n')
        self.definitions = self.base / 'definitions.sh'
        self.definitions.write_text((ROOT / 'install-mytellpbx.sh').read_text(encoding='utf-8').rsplit('\nmain "$@"', 1)[0], encoding='utf-8')
        with self.definitions.open("a", encoding="utf-8") as fixture: fixture.write("\nensure_local_hostname_resolution(){ :; }\n")

    def exercise(self, offline=True, fail='', resume=False, action='main'):
        q = shlex.quote
        script = 'source ' + q(self.definitions.as_posix()) + '\n'
        for key, value in {'LOG':self.base/'log', 'STATE_DIR':self.base/'state',
                           'WORK_DIR':self.base/'work', 'BUNDLE_DIR':self.bundle,
                           'EVENTS':self.events, 'MEDIA_ROOT':self.base/'media' if offline else '',
                           'MEDIA_MANIFEST_SHA256':'a'*64 if offline else '',
                           'MEDIA_GEOIP_SOURCE':self.base/'country.gz', 'MEDIA_GEOIP_SHA256':'b'*64,
                           'MEDIA_GEOIP_MONTH':'2026-11', 'FAIL_PHASE':fail,
                           'RESUME':'1' if resume else '0'}.items():
            script += key + '=' + q(str(value).replace('\\', '/')) + '\n'
        script += '''
event(){ printf '%s' "$1" >>"$EVENTS"; shift; printf '\\t%s' "$@" >>"$EVENTS"; printf '\\n' >>"$EVENTS"; }
preflight(){ :; }; acquire_lock(){ :; }; write_install_source(){ :; }; initialize_workspace(){ :; }
verify_bundle(){ :; }; initialize_media(){ :; }; ensure_credentials(){ :; }; repair_platform_catalog(){ :; }
step(){ :; }; say(){ :; }
stage_repos(){ :; }; stage_native_platform(){ :; }; stage_update(){ :; }; stage_packages1(){ :; }; stage_tls(){ :; }
stage_cli_status(){ :; }; stage_post_base(){ :; }; stage_framework_init(){ :; }; stage_mytel_layer(){ :; }
stage_webrtc_dtls(){ :; }; stage_myteldesk(){ event DESK; }; stage_selfcheck(){ :; }; finish(){ event DONE; }
stage_done(){ [ "$RESUME" = 1 ] && { [ "$1" = packages2 ] || [ "$1" = geoip ]; }; }
mark_stage(){ event MARK "$1"; }
install_with_retry(){ event DNF "$@"; [ "$FAIL_PHASE" != packages ] || die 'fixture package transaction failed'; }
run_logged(){ "$@"; }
PY_BIN=fixture_python
fixture_python(){
 case "$*" in
  *prepare-native-geoip.py*) event NATIVE "$@"; [ "$FAIL_PHASE" != "$3" ];;
  *offline-vendor-geoip.py*) event BRIDGE "$@"; [ "$FAIL_PHASE" != "$3" ];;
  *geoip-update.py*) event UPDATER "$@"; [ "$FAIL_PHASE" != managed ];;
  *prepare-geoip-module.py*) event CONSUMER "$@"; [ "$FAIL_PHASE" != consumer ];;
  *) event FORBIDDEN "$@"; return 99;;
 esac
}
'''
        path = self.base / 'run.sh'; path.write_text(script + action + '\n', encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(path)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                encoding='utf-8', errors='replace', timeout=30)
        events = [row.rstrip('\t').split('\t') for row in self.events.read_text().splitlines()] if self.events.exists() else []
        self.assertFalse(any(row[0] == 'FORBIDDEN' for row in events), events)
        return result, events

    def test_offline_phases_surround_actual_package_and_managed_stages(self):
        result, events = self.exercise(); self.assertEqual(result.returncode, 0, result.stderr)
        order = [row[3] if row[0] == 'BRIDGE' else row[0] for row in events]
        for before, after in [('--prepare','DNF'), ('DNF','--handoff'), ('--handoff','UPDATER'),
                              ('UPDATER','CONSUMER'), ('CONSUMER','--finish'), ('--finish','DESK')]:
            self.assertIn(before, order); self.assertIn(after, order)
            self.assertLess(order.index(before), order.index(after), order)

    def test_all_three_calls_use_only_the_exact_verified_media_profile(self):
        result, events = self.exercise(); self.assertEqual(result.returncode, 0, result.stderr)
        calls = [row for row in events if row[0] == 'BRIDGE']
        expected = [['BRIDGE','-B',(self.bundle/'installer/offline-vendor-geoip.py').as_posix(), phase,
                     '--media-root',(self.base/'media').as_posix(),'--manifest-sha256','a'*64]
                    for phase in ['--prepare','--handoff','--finish']]
        self.assertEqual(calls, expected)

    def test_marker_resume_still_revalidates_all_phases(self):
        result, events = self.exercise(resume=True); self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([row[3] for row in events if row[0] == 'BRIDGE'], ['--prepare','--handoff','--finish'])
        self.assertFalse(any(row[0] in ['DNF','UPDATER'] for row in events))
        self.assertLess(next(i for i,row in enumerate(events) if row[0]=='CONSUMER'),
                        next(i for i,row in enumerate(events) if row[0]=='BRIDGE' and row[3]=='--finish'))

    def test_prepare_failure_stops_before_any_stage_two_transaction(self):
        result, events = self.exercise(fail='--prepare'); self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(row[0] in ['DNF','UPDATER','DESK','DONE'] for row in events))

    def test_package_failure_stops_before_handoff(self):
        result, events = self.exercise(fail='packages'); self.assertNotEqual(result.returncode, 0)
        self.assertEqual([row[3] for row in events if row[0]=='BRIDGE'], ['--prepare'])

    def test_handoff_failure_stops_before_managed_update(self):
        result, events = self.exercise(fail='--handoff'); self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(row[0] in ['UPDATER','CONSUMER','DESK','DONE'] for row in events))

    def test_managed_or_consumer_failure_cannot_finish_bridge(self):
        for failure in ['managed','consumer']:
            with self.subTest(failure=failure):
                if self.events.exists(): self.events.unlink()
                result, events = self.exercise(fail=failure); self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(row[0]=='BRIDGE' and row[3]=='--finish' for row in events))
                self.assertFalse(any(row[0] in ['DESK','DONE'] for row in events))

    def test_finish_failure_stops_before_desk_and_success_output(self):
        result, events = self.exercise(fail='--finish'); self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(row[0] in ['DESK','DONE'] for row in events))

    def test_online_path_has_no_bridge_calls_or_offline_updater_arguments(self):
        result, events = self.exercise(offline=False); self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(row[0]=='BRIDGE' for row in events))
        updater = next(row for row in events if row[0]=='UPDATER')
        self.assertFalse(any('offline' in value or 'media-root' in value for value in updater))

    def test_bridge_is_a_required_exact_bundle_payload(self):
        source = (ROOT/'scripts/build-installer-bundle.sh').read_text()
        self.assertIn('copy_path "installer/offline-vendor-geoip.py"', source)


if __name__ == '__main__': unittest.main()
