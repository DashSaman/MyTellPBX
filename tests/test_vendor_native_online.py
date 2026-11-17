"""Native installer provenance, execution order and failure boundaries."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'installer/vendor-native'
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')
VENDOR_SHA = 'd0793041a422981293d74153f1aa56b29ff9803d18ee3319a53865b5b6132d46'
FLOW = ['check_dialog', 'add_repos', 'settings', 'welcome', 'select_language',
        'sel_astver', 'additional_packages', 'generate_files', 'welcome',
        'centos8_tweaks', 'clean_yum', 'update_os', 'install_packages',
        'post_install', 'set_passwords', 'mytel_addons', 'cleanup', 'bye', 'reboot']


def module(name):
    spec = importlib.util.spec_from_file_location('native_' + name, NATIVE / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class NativeSourceTests(unittest.TestCase):
    def test_bundle_ships_native_engine_and_addons_without_old_core_helpers(self):
        source = (ROOT / 'scripts/build-installer-bundle.sh').read_text(encoding='utf-8')
        for name in ['issabel5-netinstall.sh', 'mytelpbx-netinstall.sh', 'derive-native.py',
                     'brand-native-dialogs.py', 'provenance.json', 'run-offline.sh']:
            self.assertIn('copy_path "installer/vendor-native/' + name + '"', source)
        for name in ['install-mytel-addons.sh', 'native-addons.py', 'install-myteldesk.py',
                     'myteldesk-release.json', 'media.py', 'repair-repository-transport.py']:
            self.assertIn('copy_path "installer/' + name + '"', source)
        for obsolete in ['password-init.php', 'prepare-native-start.py', 'prepare-native-geoip.py',
                         'patch-native-include-order.py', 'prepare-pjsip-websocket.py',
                         'prepare-webrtc-dtls.py', 'geoip-update.py', 'prepare-geoip-module.py',
                         'repair-platform-repositories.py', 'offline-vendor-geoip.py']:
            self.assertNotIn('copy_path "installer/' + obsolete + '"', source)
        self.assertIn("'asterisk_default': '18'", source)
        self.assertIn("'asterisk_choices': ['16', '18', '20']", source)

    def test_owner_reference_is_byte_exact_and_derived_is_reproducible(self):
        vendor = (NATIVE / 'issabel5-netinstall.sh').read_bytes()
        self.assertEqual(hashlib.sha256(vendor).hexdigest(), VENDOR_SHA)
        self.assertEqual(module('derive-native').derive(vendor),
                         (NATIVE / 'mytelpbx-netinstall.sh').read_bytes())

    def test_native_package_and_password_operations_remain_native(self):
        source = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        self.assertIn('/usr/bin/issabel-admin-passwords --init', source)
        self.assertIn('16  off', source)
        self.assertIn('18  on', source)
        self.assertIn('20  off', source)
        self.assertNotIn('--nogpg', source)
        self.assertNotIn('install_amp', source)
        self.assertNotIn('prepare-native-start', source)
        self.assertNotIn('prepare-native-geoip', source)
        self.assertNotIn('geoip-update.py', source)
        self.assertIn('gpgcheck=1', source)
        self.assertIn('https://repo.us.issabel.org/issabel/5/base/\\$basearch/', source)

    def test_optional_license_label_preserves_native_choices_and_defaults(self):
        original = (NATIVE / 'issabel5-netinstall.sh').read_text(encoding='utf-8')
        derived = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        def selection(source):
            return source.split('function additional_packages\n{', 1)[1].split('\nfunction yum_gauge', 1)[0]
        expected = selection(original).replace(
            'Issabel Network Licensed modules(http://issabel.guru)',
            'Optional upstream licensed add-ons').replace('\n    exit\n', '\n    exit 1\n')
        self.assertEqual(selection(derived), expected)
        self.assertIn('1 "Optional upstream licensed add-ons" on', derived)

    def test_unrecognized_vendor_reference_is_refused(self):
        with self.assertRaises(ValueError):
            module('derive-native').derive(b'#!/bin/bash\necho unexpected\n')


class NativeDialogTests(unittest.TestCase):
    def test_core_tools_change_only_declared_display_spans(self):
        branding = module('brand-native-dialogs')
        for tool in ['language', 'passwords']:
            filename, checksum, replacements = branding.TOOLS[tool]
            with self.subTest(tool=tool):
                source = (ROOT / 'tests/fixtures/vendor-native' / filename).read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), checksum)
                result = branding.transform(tool, source)
                self.assertNotEqual(source, result)
                self.assertEqual(branding.transform(tool, result), result)
                recovered = result
                for before, after, count in reversed(replacements):
                    self.assertEqual(recovered.count(after), count)
                    recovered = recovered.replace(after, before)
                self.assertEqual(recovered, source)
                self.assertIn(b'MytelPBX', result)
                self.assertIn(b'Mytel.one', result)

    def test_unknown_or_partly_branded_program_is_refused(self):
        branding = module('brand-native-dialogs')
        for tool, (filename, _checksum, replacements) in branding.TOOLS.items():
            source = (ROOT / 'tests/fixtures/vendor-native' / filename).read_bytes()
            changed_sources = [source + b'\n# drift\n']
            if replacements:
                changed_sources.append(source.replace(replacements[0][0], replacements[0][1]))
            for changed in changed_sources:
                with self.subTest(tool=tool):
                    with self.assertRaises(ValueError):
                        branding.transform(tool, changed)

    def test_optional_completion_is_truthful_and_has_no_donation_or_fake_erasure(self):
        branding = module('brand-native-dialogs')
        source = (ROOT / 'tests/fixtures/vendor-native/issabel-patreon').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), branding.TOOLS['completion'][1])
        result = branding.transform('completion', source)
        self.assertEqual(branding.transform('completion', result), result)
        self.assertIn(b'core/password wizard completed', result)
        self.assertIn(b'add-ons will run NEXT', result)
        self.assertNotIn(b'patreon.com', result)
        self.assertNotIn(b'Erasing', result)
        self.assertNotIn(b'fake_delete', result)

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX ownership and permissions')
    def test_completion_replacement_preserves_original_backup_and_is_idempotent(self):
        branding = module('brand-native-dialogs')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'usr/bin/issabel-patreon'
            path.parent.mkdir(parents=True)
            original = (ROOT / 'tests/fixtures/vendor-native/issabel-patreon').read_bytes()
            path.write_bytes(original)
            path.chmod(0o755)
            backups = root / 'backups'
            self.assertTrue(branding.apply('completion', root, backups))
            self.assertEqual(path.read_bytes(), branding.COMPLETION_HELPER)
            self.assertFalse(branding.apply('completion', root, backups))
            recorded = list(backups.iterdir())
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0].read_bytes(), original)
            self.assertEqual(recorded[0].stat().st_mode & 0o777, 0o600)


@unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
class NativeFlowTests(unittest.TestCase):
    def fixture(self, fail=''):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        events = base / 'events'
        source = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        definitions, footer = source.split('\n# MYTEL_NATIVE_FLOW\n', 1)
        body = definitions + '\nEVENTS=' + shlex.quote(events.as_posix()) + '\n'
        for name in set(FLOW):
            body += name + '(){ printf "%s\\n" ' + shlex.quote(name) + ' >> "$EVENTS"; '
            body += ('return 27;' if name == fail else ':;') + ' }\n'
        body += footer
        script = base / 'run.sh'
        script.write_text(body, encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
        return result, events.read_text().splitlines() if events.exists() else []

    def test_success_preserves_complete_native_order_with_one_addon_hook(self):
        result, events = self.fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, FLOW)

    def test_any_failed_native_stage_stops_before_later_stage_or_reboot(self):
        for failed in ['settings', 'update_os', 'install_packages', 'post_install',
                       'set_passwords', 'mytel_addons']:
            with self.subTest(failed=failed):
                result, events = self.fixture(failed)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(events, FLOW[:FLOW.index(failed) + 1])
                self.assertIn(b'MytelPBX', result.stderr)


@unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
class NativeBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.work = self.base / 'work'
        self.work.mkdir()
        self.prefix = 'mytelpbx-bundle-7.7.0'

    def run_function(self, action, checksum=None, local=None):
        body = 'source ' + shlex.quote((ROOT / 'install-mytellpbx.sh').as_posix()) + '\n'
        body += 'MYTEL_NATIVE_WORK=' + shlex.quote(self.work.as_posix()) + '\n'
        body += 'MYTEL_PYTHON=' + shlex.quote(os.sys.executable.replace('\\', '/')) + '\n'
        if checksum:
            body += 'MYTELLPBX_BUNDLE_SHA256=' + checksum + '\n'
        if local:
            body += 'MYTELL_BUNDLE_FILE=' + shlex.quote(local.as_posix()) + '\n'
        body += action + '\n'
        runner = self.base / 'run.sh'
        runner.write_text(body, encoding='utf-8')
        return subprocess.run([BASH, '--noprofile', '--norc', str(runner)],
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=20)

    def archive(self, members, path=None):
        path = path or self.work / 'bundle.tgz'
        with tarfile.open(path, 'w:gz') as archive:
            for name, value in members:
                member = tarfile.TarInfo(name)
                if value is None:
                    member.type = tarfile.SYMTYPE
                    member.linkname = '/etc/issabel.conf'
                    archive.addfile(member)
                else:
                    member.size = len(value)
                    archive.addfile(member, io.BytesIO(value))
        return path

    def test_valid_bundle_extracts_exact_native_reference_without_running_it(self):
        files = {'manifest.json': b'{}\n'}
        for name in ['issabel5-netinstall.sh', 'mytelpbx-netinstall.sh', 'derive-native.py']:
            files['installer/vendor-native/' + name] = (NATIVE / name).read_bytes()
        files['SHA256SUMS'] = ''.join(hashlib.sha256(data).hexdigest() + '  ./' + name + '\n'
                                      for name, data in files.items()).encode()
        self.archive([(self.prefix + '/' + name, value) for name, value in files.items()])
        result = self.run_function('extract_bundle')
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.work / 'payload' / self.prefix
        self.assertEqual((output / 'installer/vendor-native/issabel5-netinstall.sh').read_bytes(),
                         (NATIVE / 'issabel5-netinstall.sh').read_bytes())
        self.assertFalse((self.work / 'netinstall.log').exists())

    def test_local_bundle_still_requires_release_hash(self):
        local = self.base / 'untrusted.tgz'
        local.write_bytes(b'not the pinned release')
        result = self.run_function('download_bundle', checksum='a' * 64, local=local)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'checksum', result.stderr)
        self.assertFalse((self.work / 'payload').exists())

    def test_non_https_download_is_refused(self):
        result = self.run_function('MYTELLPBX_BUNDLE_URL=http://invalid.test/bundle.tgz\ndownload_bundle')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'HTTPS', result.stderr)
        self.assertFalse((self.work / 'bundle.tgz').exists())

    def test_unsafe_archive_headers_are_all_rejected_before_any_output(self):
        for members in [
            [(self.prefix + '/linked', None)],
            [(self.prefix + '/../escape', b'x')],
            [('wrong-release/file', b'x')],
            [(self.prefix + '/same', b'a'), (self.prefix + '/same', b'b')],
            [(self.prefix + '/file', b'a'), (self.prefix + '/file/child', b'b')],
        ]:
            with self.subTest(members=members):
                self.archive(members)
                result = self.run_function('extract_bundle')
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.work / 'payload').exists())

    def test_real_native_gauge_package_failure_is_not_hidden_by_dialog_or_echo(self):
        source = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        definitions = source.split('\n# MYTEL_NATIVE_FLOW\n', 1)[0]
        runner = self.base / 'gauge.sh'
        runner.write_text(definitions + '\nMYTEL_NATIVE_WORK=' + shlex.quote(self.work.as_posix())
                          + '\nBACKTITLE=Fixture\ndialog(){ cat >/dev/null; }\n'
                          + 'rpm(){ return 1; }\nyum(){ return 34; }\n'
                          + 'yum_gauge "required-package" Fixture install\n', encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(runner)],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('required-package: ERROR', (self.work / 'netinstall_errors.txt').read_text())


if __name__ == '__main__':
    unittest.main()
