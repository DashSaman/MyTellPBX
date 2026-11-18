"""Native installer provenance, execution order and failure boundaries."""
import hashlib
import importlib.util
import io
import json
import os
from datetime import datetime
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'installer/vendor-native'
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')
OPENSSL = 'C:/Program Files/Git/usr/bin/openssl.exe' if os.name == 'nt' else shutil.which('openssl')
VENDOR_SHA = 'd0793041a422981293d74153f1aa56b29ff9803d18ee3319a53865b5b6132d46'
FLOW = ['check_dialog', 'add_repos', 'settings', 'select_language',
        'sel_astver', 'additional_packages', 'generate_files',
        'centos8_tweaks', 'clean_yum', 'update_os', 'install_packages',
        'post_install', 'set_passwords', 'mytel_addons', 'cleanup',
        'mytel_verify_addons', 'bye', 'reboot']


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
        for name in ['install-mytel-addons.sh', 'native-addons.py', 'native-ownership-hook.py', 'install-myteldesk.py',
                     'myteldesk-release.json', 'media.py', 'repair-repository-transport.py']:
            self.assertIn('copy_path "installer/' + name + '"', source)
        for obsolete in ['password-init.php', 'prepare-native-start.py', 'prepare-native-geoip.py',
                         'patch-native-include-order.py', 'prepare-pjsip-websocket.py',
                         'prepare-webrtc-dtls.py', 'geoip-update.py', 'prepare-geoip-module.py',
                         'repair-platform-repositories.py', 'offline-vendor-geoip.py']:
            self.assertNotIn('copy_path "installer/' + obsolete + '"', source)
        self.assertIn("'asterisk_default': '20'", source)
        self.assertIn("'asterisk_choices': ['20']", source)

    def test_owner_reference_is_byte_exact_and_derived_is_reproducible(self):
        vendor = (NATIVE / 'issabel5-netinstall.sh').read_bytes()
        self.assertEqual(hashlib.sha256(vendor).hexdigest(), VENDOR_SHA)
        self.assertEqual(module('derive-native').derive(vendor),
                         (NATIVE / 'mytelpbx-netinstall.sh').read_bytes())

    def test_native_package_and_password_operations_remain_native(self):
        source = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        self.assertIn('mytel_apply_online_passwords', source)
        self.assertIn('mytel_receive_online_passwords || exit 1\nmytel_native_step check_dialog', source)
        version = source.split('function sel_astver\n{\n', 1)[1].split('\n}', 1)[0]
        self.assertIn('ASTVER=20', version)
        self.assertNotIn('dialog', version)
        self.assertNotIn('Select Asterisk version:', source)
        self.assertNotIn('16  off', source)
        self.assertNotIn('18  on', source)
        self.assertNotIn('--nogpg', source)
        self.assertNotIn('install_amp', source)
        self.assertNotIn('prepare-native-start', source)
        self.assertNotIn('prepare-native-geoip', source)
        self.assertNotIn('geoip-update.py', source)
        self.assertIn('gpgcheck=1', source)
        self.assertIn('https://repo.us.issabel.org/issabel/5/base/\\$basearch/', source)

    def test_online_language_setup_does_not_open_the_native_choice_dialog(self):
        derived = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        stage = derived.split('function select_language()\n{\n', 1)[1].split('\n}', 1)[0]
        self.assertIn('--tool language || return 1', stage)
        self.assertNotIn('/usr/bin/issabel-change-language', stage)

    @unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
    def test_product_version_is_fixed20_even_with_an_inherited_older_value(self):
        definitions = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8').split('\n# MYTEL_NATIVE_FLOW\n')[0]
        for previous in ('16', '18', '20', ''):
            with self.subTest(previous=previous):
                script = definitions + '\ndialog(){ echo UNEXPECTED_VERSION_DIALOG; return 91; }\n'
                script += 'ASTVER=' + shlex.quote(previous) + '\nsel_astver\nprintf "ACTUAL=%s\\n" "$ASTVER"\n'
                result = subprocess.run([BASH, '--noprofile', '--norc', '-s'], input=script.encode(),
                                        capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, b'ACTUAL=20\n')

    def test_online_addons_include_community_block_list_without_licensed_packages(self):
        derived = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        stage = derived.split('function additional_packages\n{', 1)[1].split('\n}', 1)[0]
        self.assertIn('ADDPKGS=issabel-packetbl', stage)
        for fragment in ('issabel-license', 'wanpipe-utils', '--checklist', '--radiolist'):
            self.assertNotIn(fragment, derived)

    def test_unrecognized_vendor_reference_is_refused(self):
        with self.assertRaises(ValueError):
            module('derive-native').derive(b'#!/bin/bash\necho unexpected\n')

    def test_sip_branding_occurs_after_packages_not_in_early_language_bootstrap(self):
        source = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        language = source.split('function select_language()\n{\n', 1)[1].split('\n}', 1)[0]
        passwords = source.split('function set_passwords()\n{\n', 1)[1].split('\n}', 1)[0]
        self.assertNotIn('--tool sip', language)
        self.assertIn('--tool sip || return 1', passwords)
        self.assertLess(passwords.index('--tool sip'), passwords.index('mytel_apply_online_passwords'))

    def test_offline_post_brands_sip_before_native_firstboot(self):
        spec = importlib.util.spec_from_file_location('sip_iso_builder', ROOT / 'scripts/remaster-vendor-iso.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        result = builder.kickstart((ROOT / 'tests/fixtures/vendor-iso/issabel.ks').read_text())
        post = result.split('# MYTEL_NATIVE_ADDONS_BEGIN', 1)[1]
        self.assertIn('--tool sip', post)
        self.assertLess(post.index('--tool sip'), post.index('run-offline.sh --verify-media'))
        self.assertNotIn('issabel-admin-passwords --init', post)

    def test_certificate_generator_is_prepared_only_after_packages_before_native_init(self):
        source = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        language = source.split('function select_language()\n{\n', 1)[1].split('\n}', 1)[0]
        passwords = source.split('function set_passwords()\n{\n', 1)[1].split('\n}', 1)[0]
        self.assertNotIn('--tool certificate', language)
        self.assertIn('--tool certificate || return 1', passwords)
        self.assertLess(passwords.index('--tool certificate'), passwords.index('mytel_apply_online_passwords'))
        spec = importlib.util.spec_from_file_location('certificate_iso_builder', ROOT / 'scripts/remaster-vendor-iso.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        post = builder.kickstart((ROOT / 'tests/fixtures/vendor-iso/issabel.ks').read_text()).split('# MYTEL_NATIVE_ADDONS_BEGIN', 1)[1]
        self.assertIn('--tool certificate', post)
        self.assertLess(post.index('--tool certificate'), post.index('run-offline.sh --verify-media'))


class NativeDialogTests(unittest.TestCase):
    def test_core_tools_have_only_declared_hash_bound_changes(self):
        branding = module('brand-native-dialogs')
        for tool in ['language', 'passwords', 'sip', 'certificate']:
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

    @unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
    def test_online_sip_applies_both_native_port_choices_without_a_dialog(self):
        vendor = (ROOT / 'tests/fixtures/vendor-native/issabel-change-sip').read_bytes()
        generated = module('online-sip').derive(vendor).decode()
        # Never source the running system's configuration or call MariaDB.
        generated = generated.replace('source /etc/issabel.conf || exit 1',
                                      'mysqlrootpwd=DemoOnly')
        fixtures = '''asterisk(){ printf 'Asterisk 20.12.0\\n'; }
dialog(){ exit 90; }
mysql(){
    [ "$1" = '--defaults-extra-file=/dev/fd/3' ] || return 91
    grep -qx 'password="DemoOnly"' <&3 || return 92
    printf '%s\\n' "$*" >> "$EVENTS"
    if [[ $* == *bindport* && ${FAIL_SQL:-} == 1 ]]; then return 37; fi
}
amportal(){ printf 'apply %s\\n' "$*" >> "$EVENTS"; }
'''
        with tempfile.TemporaryDirectory() as work:
            events = Path(work) / 'events'
            for driver, sip_port, pjsip_port in (('pjsip', 5066, 5060), ('sip', 5060, 5066)):
                with self.subTest(driver=driver):
                    events.write_text('')
                    setup = 'EVENTS=' + shlex.quote(events.as_posix()) + '\nMYTEL_ONLINE_SIP_DRIVER=' + driver + '\n'
                    result = subprocess.run([BASH, '--noprofile', '--norc', '-s'],
                                            input=(setup + fixtures + generated).encode(), capture_output=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    log = events.read_text()
                    self.assertIn("sipsettings(keyword,data,seq) VALUES('bindport','" + str(sip_port), log)
                    self.assertIn("pjsipsettings(keyword,data,seq) VALUES('bindport','" + str(pjsip_port), log)
                    self.assertIn('apply a r', log)
                    self.assertNotIn('DemoOnly', log)
            events.write_text('')
            result = subprocess.run([BASH, '--noprofile', '--norc', '-s'],
                                    input=(setup + 'FAIL_SQL=1\n' + fixtures + generated).encode(),
                                    capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 37, result.stderr)
            self.assertNotIn('apply a r', events.read_text())

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX installed path, ownership and atomic replacement')
    def test_certificate_apply_uses_explicit_sbin_path_preserves_original_and_failure_recovery(self):
        branding = module('brand-native-dialogs')
        original = (ROOT / 'tests/fixtures/vendor-native/generate_self_signed.sh').read_bytes()
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); path = root / 'usr/local/sbin/generate_self_signed.sh'
                path.parent.mkdir(parents=True); path.write_bytes(original); path.chmod(0o750)
                decoy = root / 'usr/bin/generate_self_signed.sh'
                decoy.parent.mkdir(parents=True); decoy.write_bytes(b'untouched decoy\n')
                before = path.stat(); backups = root / 'backups'
                if fail:
                    with patch.object(branding.os, 'replace', side_effect=OSError('fixture replace failure')):
                        with self.assertRaises(OSError): branding.apply('certificate', root, backups)
                    self.assertEqual(path.read_bytes(), original)
                else:
                    self.assertTrue(branding.apply('certificate', root, backups))
                    self.assertFalse(branding.apply('certificate', root, backups))
                    self.assertEqual(path.read_bytes(), branding.transform('certificate', original))
                self.assertEqual((path.stat().st_uid, path.stat().st_gid, path.stat().st_mode & 0o777),
                                 (before.st_uid, before.st_gid, 0o750))
                saved = list(backups.iterdir()); self.assertEqual(len(saved), 1)
                self.assertEqual(saved[0].read_bytes(), original)
                self.assertEqual(saved[0].stat().st_mode & 0o777, 0o600)
                self.assertEqual(decoy.read_bytes(), b'untouched decoy\n')
                self.assertFalse(list(path.parent.glob('.mytel-native-display-*')))

    def test_certificate_source_and_provenance_are_exact_without_traversal(self):
        branding = module('brand-native-dialogs')
        self.assertIn('certificate', branding.TOOLS)
        filename, checksum, _replacements = branding.TOOLS['certificate']
        self.assertEqual(filename, 'generate_self_signed.sh')
        original = (ROOT / 'tests/fixtures/vendor-native' / filename).read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), 'e526f5f2792830291858eb5e8c2cd3f3ab2218a2f60651951934d4c26f46502b')
        self.assertEqual(checksum, hashlib.sha256(original).hexdigest())
        provenance = json.loads((NATIVE / 'provenance.json').read_text())
        self.assertEqual(provenance['dialog_sources'][filename]['sha256'], checksum)
        result = branding.transform('certificate', original)
        self.assertIn(b'grep "^extendedKeyUsage = serverAuth" /etc/pki/tls/openssl.cnf', result)
        self.assertIn(b'if [ $? -ne 0 ]; then', result)
        self.assertIn(b'/usr/bin/openssl genrsa 2048', result)
        self.assertIn(b'-x509 -sha256 -days 824 -set_serial $RANDOM -extensions v3_req', result)
        self.assertEqual(result.count(b'/usr/bin/systemctl restart httpd'), 1)
        self.assertNotIn(b'../', filename.encode())

    def test_sip_title_and_logo_use_product_brand_without_accepting_changed_ports(self):
        branding = module('brand-native-dialogs')
        self.assertIn('sip', branding.TOOLS, 'Native firstboot SIP title/logo must be hash-bound and branded')
        source = (ROOT / 'tests/fixtures/vendor-native/issabel-change-sip').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),
                         'ded8e15e75280e36b9ed00c7f9cd8d27530c1099281e7aeaa0039c14a47a7234')
        result = branding.transform('sip', source)
        self.assertIn(b'BACKTITLE="MytelPBX / Mytel.one"', result)
        self.assertIn(b'--backtitle "MytelPBX / Mytel.one" --no-tags', result)
        self.assertIn(br'\nMytelPBX\nMytel.one"', result)
        self.assertNotIn(br'\nIssabel"', result)
        self.assertIn(b'        8 15\n', result)
        with self.assertRaises(ValueError):
            branding.transform('sip', source.replace(b'sipPort="5060"', b'sipPort="5999"', 1))
        provenance = json.loads((NATIVE / 'provenance.json').read_text())
        self.assertEqual(provenance['dialog_sources']['issabel-change-sip']['sha256'], hashlib.sha256(source).hexdigest())

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX ownership and permissions')
    def test_sip_apply_preserves_owner_mode_original_backup_and_repeat_noop(self):
        branding = module('brand-native-dialogs')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'usr/bin/issabel-change-sip'
            path.parent.mkdir(parents=True)
            original = (ROOT / 'tests/fixtures/vendor-native/issabel-change-sip').read_bytes()
            path.write_bytes(original); path.chmod(0o755); before = path.stat()
            backups = root / 'backups'
            self.assertTrue(branding.apply('sip', root, backups))
            self.assertEqual((path.stat().st_uid, path.stat().st_gid, path.stat().st_mode & 0o777),
                             (before.st_uid, before.st_gid, 0o755))
            self.assertFalse(branding.apply('sip', root, backups))
            recorded = list(backups.iterdir()); self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0].read_bytes(), original)
            self.assertEqual(recorded[0].stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX atomic replacement')
    def test_sip_failed_atomic_replace_keeps_original_and_recovery_copy(self):
        branding = module('brand-native-dialogs')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'usr/bin/issabel-change-sip'
            path.parent.mkdir(parents=True)
            original = (ROOT / 'tests/fixtures/vendor-native/issabel-change-sip').read_bytes()
            path.write_bytes(original); path.chmod(0o755)
            backups = root / 'backups'
            with patch.object(branding.os, 'replace', side_effect=OSError('fixture replace failure')):
                with self.assertRaises(OSError): branding.apply('sip', root, backups)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual([item.read_bytes() for item in backups.iterdir()], [original])
            self.assertFalse(list(path.parent.glob('.mytel-native-display-*')))

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


@unittest.skipUnless(BASH and OPENSSL and Path(BASH).is_file() and Path(OPENSSL).is_file(), 'Bash and OpenSSL are required')
class NativeCertificateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.counter = 0
        self.original = (ROOT / 'tests/fixtures/vendor-native/generate_self_signed.sh').read_bytes()

    def openssl(self, *args):
        env = dict(os.environ); env.pop('OPENSSL_CONF', None)
        return subprocess.run([OPENSSL] + list(args), capture_output=True, timeout=30, env=env)

    def run_generator(self, source, hostname='mytelpbx.local', addresses=None, existing=False):
        self.counter += 1; root = self.base / str(self.counter); root.mkdir()
        config = root / 'openssl.cnf'; key = root / 'localhost.key'; cert = root / 'localhost.crt'
        config.write_text('[req]\ndistinguished_name=dn\n[dn]\nC=Country\nST=State\nL=City\nO=Organization\nOU=Unit\nCN=Common Name\nemailAddress=Email\n[v3_req]\nkeyUsage = digitalSignature, keyEncipherment\n', encoding='ascii')
        if existing:
            with config.open('a') as stream: stream.write('extendedKeyUsage = serverAuth,clientAuth\n')
            key.write_bytes(b'CUSTOM PRIVATE KEY FIXTURE SENTINEL\n'); key.chmod(0o600)
            cert.write_bytes(b'CUSTOM CERTIFICATE FIXTURE SENTINEL\n')
        trace = root / 'services'
        if addresses is None:
            addresses = '2: eth0 inet 192.168.122.150/24 brd 192.168.122.255 scope global eth0\n3: eth1 inet 10.23.4.5/24 scope global eth1\n'
        setup = 'hostname(){ printf %s ' + shlex.quote(hostname) + '; }\n'
        setup += 'ip(){ [ "$*" = "-o -4 addr show scope global" ] || return 97; printf %s ' + shlex.quote(addresses) + '; }\n'
        setup += 'fixture_systemctl(){ printf "%s\\n" "$*" >> ' + shlex.quote(trace.as_posix()) + '; }\n'
        text = source.decode('utf-8')
        for old, new in [('/etc/pki/tls/openssl.cnf', config), ('/etc/pki/tls/private/localhost.key', key),
                         ('/etc/pki/tls/certs/localhost.crt', cert)]:
            text = text.replace(old, shlex.quote(new.as_posix()))
        text = text.replace('/usr/bin/openssl', shlex.quote(Path(OPENSSL).as_posix()))
        text = text.replace('/usr/bin/systemctl', 'fixture_systemctl')
        script = root / 'generator.sh'; script.write_text('#!/bin/bash\n' + setup + text, encoding='utf-8')
        env = dict(os.environ, LANG='C', LC_ALL='C', OPENSSL_CONF=config.as_posix())
        env.pop('BASH_ENV', None); env.pop('SHELLOPTS', None)
        def run():
            return subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL,
                                  capture_output=True, timeout=30, env=env)
        result = run()
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        self.assertTrue(cert.is_file(), 'Native generator must actually produce a temporary certificate')
        return root, config, key, cert, trace, run

    def certificate_text(self, cert):
        result = self.openssl('x509', '-in', str(cert), '-noout', '-text', '-subject', '-issuer', '-dates')
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.decode('utf-8')

    def check_ip(self, cert, address):
        return self.openssl('verify', '-CAfile', str(cert), '-verify_ip', address, str(cert)).returncode

    def test_original_real_certificate_reproduces_brand_and_ip_identity_gap(self):
        _root, _config, _key, cert, trace, _run = self.run_generator(self.original)
        text = self.certificate_text(cert)
        self.assertRegex(text, r'\bO\s*=\s*Issabel')
        self.assertNotIn('MytelPBX', text)
        self.assertNotEqual(self.check_ip(cert, '192.168.122.150'), 0)
        self.assertEqual(trace.read_text(), 'restart httpd\n')

    def test_derived_real_certificate_has_product_identity_ip_sans_and_native_crypto_policy(self):
        candidate = module('brand-native-dialogs').transform('certificate', self.original)
        _root, _config, _key, cert, trace, _run = self.run_generator(candidate)
        text = self.certificate_text(cert)
        self.assertRegex(text, r'\bO\s*=\s*MytelPBX - Mytel.one')
        self.assertNotRegex(text, r'\bO\s*=\s*Issabel')
        self.assertIn('DNS:mytelpbx.local', text)
        for address in ('192.168.122.150', '10.23.4.5'):
            self.assertEqual(self.check_ip(cert, address), 0)
        self.assertIn('Public-Key: (2048 bit)', text)
        self.assertIn('sha256WithRSAEncryption', text)
        self.assertIn('TLS Web Server Authentication, TLS Web Client Authentication', text)
        dates = dict(line.split('=', 1) for line in text.splitlines() if line.startswith(('notBefore=', 'notAfter=')))
        ttl = datetime.strptime(dates['notAfter'], '%b %d %H:%M:%S %Y %Z') - datetime.strptime(dates['notBefore'], '%b %d %H:%M:%S %Y %Z')
        self.assertEqual(ttl.days, 824)
        self.assertEqual(ttl.seconds, 0)
        self.assertEqual(trace.read_text(), 'restart httpd\n')

    def test_existing_native_eku_guard_preserves_config_key_certificate_and_no_restart(self):
        candidate = module('brand-native-dialogs').transform('certificate', self.original)
        _root, config, key, cert, trace, run = self.run_generator(candidate)
        before = [path.read_bytes() for path in (config, key, cert, trace)]
        self.assertEqual(run().returncode, 0)
        self.assertEqual([path.read_bytes() for path in (config, key, cert, trace)], before)

    def test_preexisting_custom_certificate_and_key_are_not_opened_or_replaced(self):
        candidate = module('brand-native-dialogs').transform('certificate', self.original)
        _root, config, key, cert, trace, run = self.run_generator(candidate, existing=True)
        self.assertEqual(key.read_bytes(), b'CUSTOM PRIVATE KEY FIXTURE SENTINEL\n')
        self.assertEqual(cert.read_bytes(), b'CUSTOM CERTIFICATE FIXTURE SENTINEL\n')
        self.assertFalse(trace.exists())
        before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in (config, key, cert)]
        self.assertEqual(run().returncode, 0)
        self.assertEqual([(path.read_bytes(), path.stat().st_mtime_ns) for path in (config, key, cert)], before)

    def test_invalid_names_addresses_and_duplicates_cannot_inject_extensions(self):
        candidate = module('brand-native-dialogs').transform('certificate', self.original)
        bad = ['256.1.2.3', '01.2.3.4', '127.0.0.1', '0.0.0.0', '224.1.2.3', '169.254.1.2', '1.2.3.4,DNS:evil.example', '1.2.3.4;critical']
        addresses = ''.join('2: eth0 inet ' + address + '/24 scope global eth0\n' for address in bad)
        addresses += '2: eth0 inet 192.168.122.150/24 scope global eth0\n' * 2
        for hostname in ('bad,name', '-bad.local', 'bad-.local', 'bad..local', 'bad_name.local'):
            with self.subTest(hostname=hostname):
                _root, _config, _key, cert, _trace, _run = self.run_generator(candidate, hostname, addresses)
                text = self.certificate_text(cert)
                self.assertNotIn('DNS:', text)
                self.assertEqual(text.count('IP Address:192.168.122.150'), 1)
                self.assertNotIn('evil.example', text)
                self.assertEqual(self.check_ip(cert, '192.168.122.150'), 0)

    def test_ip_san_inventory_is_bounded_and_no_valid_san_keeps_native_generation(self):
        candidate = module('brand-native-dialogs').transform('certificate', self.original)
        addresses = ''.join('2: eth0 inet 10.20.0.' + str(n) + '/24 scope global eth0\n' for n in range(1, 41))
        _root, _config, _key, cert, _trace, _run = self.run_generator(candidate, addresses=addresses)
        self.assertEqual(self.certificate_text(cert).count('IP Address:'), 16)
        _root, _config, _key, cert, _trace, _run = self.run_generator(candidate, hostname='bad_name.local', addresses='')
        self.assertNotIn('Subject Alternative Name', self.certificate_text(cert))


@unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
class NativeSipFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.original = (ROOT / 'tests/fixtures/vendor-native/issabel-change-sip').read_bytes()
        self.branded = module('brand-native-dialogs').transform('sip', self.original)

    def run_helper(self, major, selection, branded):
        root = self.base / (str(major) + '-' + (selection or 'cancel') + ('-branded' if branded else '-native'))
        (root / 'etc').mkdir(parents=True)
        config = root / 'etc/issabel.conf'; config.write_text('mysqlrootpwd=FixtureDbOnly\n')
        variables = ''.join(name + '=' + shlex.quote((root / filename).as_posix()) + '\n'
                            for name, filename in [('SQLTRACE', 'sql'), ('SVCTRACE', 'service'), ('DISPLAYTRACE', 'display')])
        setup = variables + 'asterisk(){ printf "Asterisk ' + str(major) + '.99.0\\n"; }\n'
        setup += 'SIP_SELECTION=' + shlex.quote(selection) + '\n'
        setup += '''dialog(){
  printf '%s\\n' "$*" >> "$DISPLAYTRACE"
  if [ "${1:-}" = --backtitle ]; then printf '%s' "$SIP_SELECTION" >&2; fi
  return 0
}
mysql(){ printf '%s\\n' "$*" >> "$SQLTRACE"; return 0; }
amportal(){ printf '%s\\n' "$*" >> "$SVCTRACE"; return 0; }
clear(){ :; }
'''
        source = (self.branded if branded else self.original).decode('utf-8')
        source = source.replace('/etc/issabel.conf', config.as_posix()).replace('> /dev/tty', '> /dev/null')
        script = root / 'helper.sh'; script.write_text('#!/bin/bash\n' + setup + source, encoding='utf-8')
        env = dict(os.environ, LANG='C', LC_ALL='C'); env.pop('BASH_ENV', None); env.pop('SHELLOPTS', None)
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=15, env=env)
        read = lambda name: (root / name).read_text() if (root / name).exists() else ''
        return result, read('sql'), read('service'), read('display')

    def test_native_choices_defaults_sql_ports_and_reload_are_unchanged(self):
        for major in (16, 18, 20):
            for selection in ('sip', 'pjsip'):
                with self.subTest(major=major, selection=selection):
                    native = self.run_helper(major, selection, False)
                    branded = self.run_helper(major, selection, True)
                    self.assertEqual((native[0].returncode, native[1:3]), (branded[0].returncode, branded[1:3]))
                    self.assertEqual(branded[0].returncode, 0, branded[0].stderr)
                    self.assertEqual(branded[2], 'a r\n')
                    self.assertIn('sip chan_sip off pjsip chan_pjsip on', branded[3])
                    self.assertIn('Select default SIP channel driver(default port 5060, secondary 5066):', branded[3])
                    self.assertIn('MytelPBX / Mytel.one', branded[3]); self.assertNotIn('Issabel', branded[3])
                    self.assertIn("VALUES('bindport','5060',1)", branded[1])
                    self.assertIn("VALUES('bindport','5066',1)", branded[1])
                    self.assertIn("VALUES('tlsbindport','5061',1)", branded[1])
                    self.assertIn("VALUES('tlsbindport','5067',1)", branded[1])

    def test_native_cancel_and_unknown_choice_do_not_mutate_ports_or_reload(self):
        for selection, code in [('', 2), ('unknown', 1)]:
            native = self.run_helper(20, selection, False); branded = self.run_helper(20, selection, True)
            self.assertEqual((native[0].returncode, native[1:3]), (branded[0].returncode, branded[1:3]))
            self.assertEqual(branded[0].returncode, code)
            self.assertNotIn('REPLACE INTO', branded[1]); self.assertEqual(branded[2], '')


@unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
class NativeLanguageStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.original = (ROOT / 'tests/fixtures/vendor-native/issabel-change-language').read_bytes()
        self.guarded = module('brand-native-dialogs').transform('language', self.original)

    def run_helper(self, mode, guarded):
        root = self.base / (mode + ('-guarded' if guarded else '-native'))
        (root / 'etc').mkdir(parents=True)
        (root / 'tmp').mkdir()
        config = root / 'etc/issabel.conf'
        if mode == 'valid':
            config.write_text('mysqlrootpwd=FixtureDbOnly\n')
        elif mode == 'malformed':
            config.write_text("mysqlrootpwd='unclosed\n")
        elif mode == 'directory':
            config.mkdir()
        elif mode == 'broken-link':
            try:
                config.symlink_to(root / 'nonexistent-config')
            except OSError as error:
                self.skipTest('Native symbolic links are unavailable: ' + str(error))
        source = (self.guarded if guarded else self.original).decode('utf-8')
        # Virtualize the fixed filesystem paths and terminal only. Fake clients
        # select English; SQL and telephony execution cannot touch the host.
        source = source.replace('/etc/issabel.conf', config.as_posix())
        source = source.replace('/tmp/ipbx.lang', (root / 'tmp/ipbx.lang').as_posix())
        source = source.replace('/var/www/db/settings.db', (root / 'settings.db').as_posix())
        source = source.replace('> /dev/tty', '> /dev/null')
        setup = 'AUTH_FILE=' + shlex.quote((root / 'auth').as_posix()) + '\n'
        setup += '''dialog(){ if [ "${1:-}" = --backtitle ]; then printf 'en\\n' >&2; fi; return 0; }
mysql(){ printf 'UNEXPECTED_DB_CALL\\n' >&2; return 99; }
which(){ printf '%s' "$MYSQLAUTH" > "$AUTH_FILE"; return 1; }
'''
        script = root / 'helper.sh'
        script.write_text('#!/bin/bash\n' + setup + source, encoding='utf-8')
        env = dict(os.environ, LANG='C', LC_ALL='C')
        env.pop('BASH_ENV', None)
        env.pop('SHELLOPTS', None)
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)],
                                stdin=subprocess.DEVNULL, capture_output=True,
                                encoding='utf-8', errors='replace', timeout=15, env=env)
        selection = (root / 'tmp/ipbx.lang').read_text()
        auth = (root / 'auth').read_bytes()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('UNEXPECTED_DB_CALL', result.stderr)
        return result, selection, auth, config

    def compare(self, mode):
        native = self.run_helper(mode, False)
        guarded = self.run_helper(mode, True)
        self.assertEqual(native[1:3], guarded[1:3])
        self.assertEqual(guarded[1], 'webLang=en\nfopLang=en\nipbxLang=en_US\nselLang=en\n')
        return native, guarded

    def test_absent_config_is_quiet_without_creating_credentials(self):
        native, guarded = self.compare('absent')
        self.assertIn('No such file or directory', native[0].stderr)
        self.assertEqual(guarded[0].stderr, '')
        self.assertEqual(guarded[2], b'')
        self.assertFalse(guarded[3].exists())
        self.assertFalse(guarded[3].is_symlink())

    def test_valid_config_is_loaded_with_unchanged_native_auth_and_selection(self):
        native, guarded = self.compare('valid')
        self.assertEqual(native[0].stderr, '')
        self.assertEqual(guarded[0].stderr, '')
        self.assertEqual(guarded[2], b'-pFixtureDbOnly')

    def test_malformed_existing_config_still_reports_source_error(self):
        native, guarded = self.compare('malformed')
        self.assertIn('unexpected EOF', native[0].stderr)
        self.assertIn('unexpected EOF', guarded[0].stderr)

    def test_existing_directory_still_reports_source_error(self):
        native, guarded = self.compare('directory')
        self.assertIn('directory', native[0].stderr)
        self.assertIn('directory', guarded[0].stderr)

    def test_broken_symlink_still_reports_source_error(self):
        native, guarded = self.compare('broken-link')
        self.assertIn('No such file or directory', native[0].stderr)
        self.assertIn('No such file or directory', guarded[0].stderr)
        self.assertTrue(guarded[3].is_symlink())


@unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
class NativePostInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.counter = 0

    def fixture(self, sample=False, custom=False, configured=False, fail='', runs=1, invalid=''):
        self.counter += 1; root = self.base / str(self.counter)
        for name in ('etc/asterisk', 'etc/selinux', 'etc/sysconfig', 'work'):
            (root / name).mkdir(parents=True)
        (root / 'etc/selinux/config').write_text('SELINUX=enforcing\n')
        (root / 'etc/sysconfig/iptables').write_text('fixture firewall\n')
        modules = root / 'etc/asterisk/modules_additional.conf'
        modules.write_text('; native module content\n')
        sample_path = root / 'etc/asterisk/extensions_custom.conf.sample'
        custom_path = root / 'etc/asterisk/extensions_custom.conf'
        amportal = root / 'etc/amportal.conf'
        if sample: sample_path.write_bytes(b'[native-sample]\n')
        if custom: custom_path.write_bytes(b'[customer-kept]\nexten => fixture,1,NoOp(keep)\n')
        if configured: amportal.write_text('native configuration fixture\n')
        if invalid:
            name, kind = invalid.split(':', 1)
            path = {'sample':sample_path, 'custom':custom_path, 'amportal':amportal, 'modules':modules}[name]
            if path.exists(): path.unlink()
            if kind == 'directory': path.mkdir()
            elif kind == 'symlink': path.symlink_to(root / 'absent-destination')
            elif kind == 'file-symlink':
                other = root / 'untouched-file'; other.write_bytes(b'unchanged\n'); path.symlink_to(other)
            else: self.fail('Unknown fixture path kind')
        events = root / 'events'
        setup = 'EVENTS=' + shlex.quote(events.as_posix()) + '\nFAIL=' + shlex.quote(fail) + '\n'
        setup += '''systemctl(){
  printf 'systemctl:%s\n' "$*" >> "$EVENTS"
  [ "$FAIL" != "systemctl:$*" ] || return 31
}
MYSQL_CALLS=0
mysql(){
  MYSQL_CALLS=$((MYSQL_CALLS + 1))
  printf 'mysql:%s\n' "$MYSQL_CALLS" >> "$EVENTS"
  [ "$FAIL" != "mysql:$MYSQL_CALLS" ] || return 29
}
setenforce(){ :; }
firewall-cmd(){ :; }
fixture_amportal(){ printf 'amportal:chown\n' >> "$EVENTS"; [ "$FAIL" != chown ] || return 33; }
mv(){ [ "$FAIL" != move ] || return 35; command mv "$@"; }
grep(){ [ "$FAIL" != grep ] || return 36; command grep "$@"; }
echo(){ [ "$FAIL" != append ] || return 37; builtin echo "$@"; }
'''
        source = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        body = source.split('function post_install\n{\n', 1)[1].split('\n}\n', 1)[0]
        # Exercise the actual function with every filesystem path confined to this
        # temporary fixture. DB, service and firewall commands are shell fakes.
        body = body.replace('/etc/', shlex.quote((root / 'etc').as_posix() + '/'))
        body = body.replace('/var/log/', shlex.quote((root / 'var/log').as_posix() + '/'))
        body = body.replace('/usr/sbin/amportal', 'fixture_amportal')
        setup += 'MYTEL_NATIVE_WORK=' + shlex.quote((root / 'work').as_posix()) + '\n'
        script = root / 'run.sh'
        calls = '\n'.join('post_install\nstatus=$?\n[ "$status" = 0 ] || exit "$status"' for _ in range(runs))
        script.write_text('#!/bin/bash\n' + setup + 'post_install(){\n' + body + '\n}\n' + calls + '\n', encoding='utf-8')
        env = dict(os.environ, LANG='C', LC_ALL='C'); env.pop('BASH_ENV', None); env.pop('SHELLOPTS', None)
        result = subprocess.run([BASH, '--noprofile', '--norc', str(script)], stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=20, env=env)
        observed = events.read_text().splitlines() if events.exists() else []
        return result, root, observed

    def test_genuine_preinit_absence_defers_configs_and_chown_to_native_initializer(self):
        result, root, events = self.fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('extensions_custom.conf', 'extensions_custom.conf.sample'):
            self.assertFalse((root / 'etc/asterisk' / name).exists())
        self.assertFalse((root / 'etc/amportal.conf').exists())
        self.assertNotIn('amportal:chown', events)
        self.assertEqual((root / 'etc/asterisk/modules_additional.conf').read_text().count('noload => cdr_mysql.so\n'), 1)
        source = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        body = source.split('function post_install\n{\n', 1)[1].split('\n}\n', 1)[0]
        self.assertNotIn('issabel-admin-passwords', body)
        self.assertNotIn('install_amp', body)

    def test_regular_sample_moves_and_configured_chown_runs(self):
        result, root, events = self.fixture(sample=True, configured=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((root / 'etc/asterisk/extensions_custom.conf.sample').exists())
        self.assertEqual((root / 'etc/asterisk/extensions_custom.conf').read_bytes(), b'[native-sample]\n')
        self.assertEqual(events.count('amportal:chown'), 1)

    def test_existing_custom_target_is_preserved_with_or_without_sample(self):
        for sample in (False, True):
            with self.subTest(sample=sample):
                result, root, events = self.fixture(sample=sample, custom=True, configured=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((root / 'etc/asterisk/extensions_custom.conf').read_bytes(),
                                 b'[customer-kept]\nexten => fixture,1,NoOp(keep)\n')
                self.assertEqual((root / 'etc/asterisk/extensions_custom.conf.sample').exists(), sample)
                self.assertEqual(events.count('amportal:chown'), 1)

    def test_recovery_repeat_does_not_duplicate_native_noload_line(self):
        for sample in (False, True):
            with self.subTest(sample=sample):
                result, root, _events = self.fixture(sample=sample, runs=2)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((root / 'etc/asterisk/modules_additional.conf').read_text(),
                                 '; native module content\nnoload => cdr_mysql.so\n')

    def test_partial_amportal_configuration_defers_missing_custom_files_but_rejects_wrong_types(self):
        result, root, events = self.fixture(configured=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events.count('amportal:chown'), 1)
        for name in ('extensions_custom.conf', 'extensions_custom.conf.sample'):
            self.assertFalse((root / 'etc/asterisk' / name).exists())
        failed, _root, events = self.fixture(configured=True,fail='chown')
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(events[-1], 'amportal:chown')
        for path in ('sample', 'custom', 'amportal', 'modules'):
            with self.subTest(path=path):
                self.assertNotEqual(self.fixture(invalid=path+':directory')[0].returncode, 0)

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX symlinks')
    def test_symlinks_including_broken_links_are_not_treated_as_absence(self):
        for path in ('sample', 'custom', 'amportal', 'modules'):
            for kind in ('symlink', 'file-symlink'):
                with self.subTest(path=path,kind=kind):
                    result, root, _events = self.fixture(invalid=path+':'+kind)
                    self.assertNotEqual(result.returncode, 0)
                    other = root / 'untouched-file'
                    if other.exists(): self.assertEqual(other.read_bytes(), b'unchanged\n')

    def test_real_move_grep_or_configured_chown_errors_remain_fatal(self):
        for failed in ('move', 'grep', 'append', 'chown'):
            with self.subTest(failed=failed):
                self.assertNotEqual(self.fixture(sample=True,configured=True,fail=failed)[0].returncode, 0)

    def test_mysql_and_required_service_errors_still_stop_before_later_work(self):
        for failed in ('mysql:1', 'mysql:2', 'systemctl:enable mariadb.service',
                       'systemctl:start mariadb', 'systemctl:enable httpd'):
            with self.subTest(failed=failed):
                result, root, events = self.fixture(fail=failed)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(events[-1], failed)
                self.assertNotIn('amportal:chown', events)
                self.assertEqual((root / 'etc/asterisk/modules_additional.conf').read_text(), '; native module content\n')


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
        # Run the real derived stage flow with native actions stubbed and an
        # in-memory handoff carrying only synthetic fixture values.
        body += 'MYTEL_BUNDLE_ROOT=' + shlex.quote(ROOT.as_posix()) + '\n'
        body += 'exec 3< <(printf "DemoDb-1234\\nDemoPanel-4321\\npjsip\\n")\n'
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

    def test_failed_independent_post_cleanup_doctor_prevents_completion_and_reboot(self):
        result, events = self.fixture('mytel_verify_addons')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1], 'mytel_verify_addons')
        self.assertNotIn('bye', events)
        self.assertNotIn('reboot', events)


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

    def test_real_native_package_progress_propagates_package_failure(self):
        source = (NATIVE / 'mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        definitions = source.split('\n# MYTEL_NATIVE_FLOW\n', 1)[0]
        runner = self.base / 'gauge.sh'
        runner.write_text(definitions + '\nMYTEL_NATIVE_WORK=' + shlex.quote(self.work.as_posix())
                          + '\nMYTEL_BUNDLE_ROOT=' + shlex.quote(ROOT.as_posix())
                          + '\nMYTEL_PYTHON=' + shlex.quote(os.sys.executable.replace('\\', '/'))
                          + '\nsource "$MYTEL_BUNDLE_ROOT/installer/vendor-native/terminal-ui.sh"\n'
                          + 'rpm(){ return 1; }\nyum(){ return 34; }\n'
                          + 'yum_gauge "required-package" core install\n', encoding='utf-8')
        result = subprocess.run([BASH, '--noprofile', '--norc', str(runner)],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('required-package: ERROR', (self.work / 'netinstall_errors.txt').read_text())


if __name__ == '__main__':
    unittest.main()
