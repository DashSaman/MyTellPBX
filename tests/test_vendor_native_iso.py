"""Preserve the supplied ISO's native installer, package groups and firstboot."""
import configparser
import importlib.util
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/vendor-iso'
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


def builder():
    spec = importlib.util.spec_from_file_location('native_iso', ROOT / 'scripts/remaster-vendor-iso.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeEmbeddedEfiTests(unittest.TestCase):
    def fixture(self, mode='known'):
        module = builder()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        stage = Path(temp.name)
        outer = (FIXTURE / 'grub.cfg').read_bytes()
        paths = ('::/EFI/BOOT/grub.cfg', '::/EFI/BOOT/BOOT.conf')
        fat = {paths[0]: (FIXTURE / 'embedded-grub.cfg').read_bytes(),
               paths[1]: (FIXTURE / 'embedded-BOOT.conf').read_bytes(),
               '::/EFI/BOOT/BOOTX64.EFI': b'native EFI binary bytes',
               '::/EFI/BOOT/splash.png': b'old splash'}
        for path in paths:
            self.assertEqual(hashlib.sha256(fat[path]).hexdigest(),
                             '1cdcf9e23e018bb1cd2d1f39206392beba1ac3eb574cedb65eb337855618243b')
        self.assertEqual(hashlib.sha256(outer).hexdigest(),
                         'e5f4765d89e5835b75d864763c1aaa3d29c831b2248a3ca004ab4bcd2a487414')
        if mode == 'changed-inner':
            fat[paths[1]] += b'\n# drift\n'
        elif mode == 'missing-pair':
            del fat[paths[1]]
        elif mode == 'unknown-config':
            fat['::/other/custom.cfg'] = fat[paths[0]]
        elif mode == 'changed-outer':
            outer += b'\n# drift\n'
        writes, reads = [], []
        def extract(_iso, member, output):
            if member == 'images/efiboot.img':
                output.write_bytes(b'fixture FAT container')
            elif member == 'EFI/BOOT/grub.cfg':
                output.write_bytes(outer)
            else:
                self.fail('Unexpected extraction: ' + member)
        def command(args):
            if args[0] == 'mdir':
                return ('\n'.join(fat) + '\n').encode()
            self.assertEqual(args[0], 'mcopy')
            source, target = args[-2:]
            if '-o' in args:
                writes.append(target)
                fat[target] = Path(source).read_bytes()
                if mode == 'bad-readback' and target == paths[1]:
                    fat[target] += b'corrupt'
            else:
                reads.append(source)
                Path(target).write_bytes(fat[source])
            return b''
        splash = stage / 'approved.png'
        splash.write_bytes(b'approved splash')
        with mock.patch.object(module, 'extract', side_effect=extract), \
                mock.patch.object(module, 'command', side_effect=command):
            if mode != 'known':
                with self.assertRaises(ValueError):
                    module.efi_image(Path('original.iso'), stage, 'MytelPBX-7.7.0-x86_64', '7.7.0', splash)
                if mode != 'bad-readback':
                    self.assertEqual(writes, [], 'unknown inputs must fail before FAT writes')
                return
            _image, count = module.efi_image(Path('original.iso'), stage, 'MytelPBX-7.7.0-x86_64', '7.7.0', splash)
        self.assertEqual(count, 2)
        expected = module.boot_config(outer.decode(), 'MytelPBX-7.7.0-x86_64', '7.7.0').encode()
        for path in paths:
            self.assertEqual(fat[path], expected)
            self.assertGreaterEqual(reads.count(path), 2, 'both embedded configs require readback')
        self.assertEqual(fat['::/EFI/BOOT/BOOTX64.EFI'], b'native EFI binary bytes')
        self.assertNotIn('::/EFI/BOOT/BOOTX64.EFI', writes)

    def test_actual_known_stale_pair_uses_pinned_native_outer_menu_and_readbacks(self):
        self.fixture()

    def test_unknown_or_incomplete_embedded_inputs_stop_before_image_writes(self):
        for mode in ['changed-inner', 'changed-outer', 'missing-pair', 'unknown-config']:
            with self.subTest(mode=mode):
                self.fixture(mode)

    def test_successful_mcopy_with_bad_readback_is_refused(self):
        self.fixture('bad-readback')

    def test_generic_boot_transform_still_refuses_stale_or_unknown_input(self):
        with self.assertRaises(ValueError):
            builder().boot_config((FIXTURE / 'embedded-grub.cfg').read_text(),
                                  'MytelPBX-7.7.0-x86_64', '7.7.0')


class NativeIsoStructureTests(unittest.TestCase):
    def test_kickstart_preserves_storage_packages_and_native_core_trigger(self):
        module = builder()
        original = (FIXTURE / 'issabel.ks').read_text(encoding='utf-8')
        result = module.kickstart(original)
        for token in ['clearpart --all --initlabel', 'autopart --type=plain --fstype=ext4',
                      '@^issabelast20', '@rbl', 'touch /mnt/sysimage/installamp',
                      'reboot --eject', 'firewall --disabled', 'selinux --disabled']:
            self.assertIn(token, result)
        self.assertNotIn('\n@guru\n', result)
        expected = original.replace('issabel.local', 'mytelpbx.local').replace('\n@guru\n', '\n')
        for line in module.ONLINE_POST_LINES:
            self.assertEqual(expected.count(line), 1)
            expected = expected.replace(line, '')
        self.assertEqual(result.split('\n# MYTEL_NATIVE_ADDONS_BEGIN\n')[0], expected.rstrip('\n'))
        self.assertNotIn('install_amp', result)
        self.assertNotIn('prepare-native-start', result)
        self.assertNotIn('geoip_install.sh', result)
        self.assertIn('--verify-media', result)
        self.assertIn('--tool completion', result)
        self.assertIn('chroot /mnt/sysimage dnf -y config-manager --set-enabled remi\n', result)
        self.assertIn('chroot /mnt/sysimage dnf -y config-manager --set-enabled powertools\n', result)
        self.assertNotIn('chroot /mnt/sysimage dnf -y module enable php:remi-7.4\n', result)
        self.assertNotIn('chroot /mnt/sysimage dnf -y check-upgrade\n', result)

    def test_unknown_native_kickstart_drift_is_refused(self):
        with self.assertRaises(ValueError):
            builder().kickstart((FIXTURE / 'issabel.ks').read_text() + '\n# unreviewed\n')

    def test_guided_dropin_reuses_native_tty_and_orders_final_reload(self):
        module = builder()
        scripts = (FIXTURE / 'firstboot-rpm-scripts.txt').read_text()
        unit = scripts.split("<<'ISSABELFIRSTBOOT'\n", 1)[1].split('\nISSABELFIRSTBOOT', 1)[0]
        self.assertIn('/usr/bin/issabel-admin-passwords --init && chvt 1 && dmesg -E', unit)
        dropin = module.firstboot_dropin()
        self.assertRegex(dropin, r'(?m)^ExecStart=\nExecStart=/bin/bash')
        self.assertNotIn('ExecStartPre=', dropin)
        self.assertIn('ExecStartPost=', dropin)
        self.assertIn('chvt 2 && exec /bin/bash /usr/local/libexec/mytelpbx/run-offline.sh', dropin)
        self.assertIn('TTYPath=/dev/tty2', unit)
        self.assertIn('StandardError=tty', dropin)
        self.assertIn('After=issabel-firstboot.service\n', module.reload_dropin())
        self.assertIn('ConditionPathExists=/var/lib/mytelpbx-native-addons/offline-complete\n', module.reload_dropin())
        self.assertRegex(dropin, r'&& chvt 1"\n$')
        runner = (ROOT / 'installer/vendor-native/run-offline.sh').read_text()
        for forbidden in ['issabel-admin-passwords --init', 'install_amp', 'prepare-native-start',
                          'geoip_install.sh', 'dnf ', 'yum ']:
            self.assertNotIn(forbidden, runner)
        self.assertIn('installer/install-mytel-addons.sh', runner)
        self.assertIn('MYTEL_MEDIA_MANIFEST_SHA256', runner)

    def test_native_bios_and_uefi_keep_boot_arguments_and_rescue_behavior(self):
        module = builder()
        for name in ['isolinux.cfg', 'grub.cfg']:
            original = (FIXTURE / name).read_text()
            result = module.boot_config(original, 'MytelPBX-7.7.0-x86_64', '7.7.0')
            self.assertNotIn('Issabel5-x86_64', result)
            self.assertNotIn('/ks/issabel.ks', result)
            self.assertIn('/ks/mytelpbx.ks', result)
            self.assertIn('Mytel.one', result)
            self.assertIn('inst.geoloc=provider_fedora_geoip', original)
            self.assertIn('inst.geoloc-use-with-ks', original)
            self.assertNotIn('inst.geoloc', result)
            self.assertEqual(result.count('inst.ks='), original.count('inst.ks='))
            self.assertEqual(result.count('rd.live.check'), original.count('rd.live.check'))
            self.assertEqual(result.count('net.ifnames=0'), original.count('net.ifnames=0'))
            self.assertEqual(result.count('inst.rescue'), original.count('inst.rescue'))

    def test_runtime_identity_keeps_native_uuid_variant_and_lorax(self):
        module = builder()
        original = (FIXTURE / '.buildstamp').read_text()
        result = module.buildstamp(original, '7.7.0')
        old = configparser.ConfigParser(); old.read_string(original)
        new = configparser.ConfigParser(); new.read_string(result)
        self.assertEqual(new.get('Main', 'Product'), 'MytelPBX')
        self.assertEqual(new.get('Main', 'Version'), '7.7.0')
        for section, key in [('Main', 'UUID'), ('Main', 'Variant'), ('Compose', 'Lorax')]:
            self.assertEqual(new.get(section, key), old.get(section, key))
        overlay = module.product_config()
        self.assertIn('[Base Product]\nproduct_name = Issabel', overlay)
        self.assertNotIn('[Storage]', overlay)
        self.assertNotIn('[Payload]', overlay)

    def test_output_publication_copies_hashes_and_never_overwrites(self):
        module = builder()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'source/candidate.iso'
            candidate.parent.mkdir()
            output = root / 'output/release.iso'
            output.parent.mkdir()
            candidate.write_bytes(b'fixture native ISO payload\n')
            checksum = hashlib.sha256(candidate.read_bytes()).hexdigest()
            module.publish_candidate(candidate, output, checksum)
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), checksum)
            self.assertFalse(candidate.exists())
            candidate.write_bytes(b'replacement must be retained')
            with self.assertRaises(FileExistsError):
                module.publish_candidate(candidate, output, hashlib.sha256(candidate.read_bytes()).hexdigest())
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), checksum)
            self.assertEqual(candidate.read_bytes(), b'replacement must be retained')
            self.assertEqual(list(output.parent.iterdir()), [output])

    def test_failed_candidate_hash_cannot_publish_or_delete_source(self):
        module = builder()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'candidate.iso'; source.write_bytes(b'changed source')
            output = root / 'release.iso'
            with self.assertRaises(ValueError):
                module.publish_candidate(source, output, 'a' * 64)
            self.assertTrue(source.exists())
            self.assertFalse(output.exists())
            self.assertEqual(list(root.iterdir()), [source])

    def test_native_inventory_detects_modified_or_extra_package_bytes(self):
        module = builder()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rpm = root / 'asterisk20.rpm'; rpm.write_bytes(b'original signed package')
            original = module.inventory(root)
            rpm.write_bytes(b'different package bytes')
            self.assertNotEqual(original, module.inventory(root))
            rpm.write_bytes(b'original signed package')
            self.assertEqual(original, module.inventory(root))
            (root / 'unexpected.rpm').write_bytes(b'extra')
            self.assertNotEqual(original, module.inventory(root))

    @unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
    def test_offline_success_runner_shell_syntax(self):
        result = subprocess.run([BASH, '-n', str(ROOT / 'installer/vendor-native/run-offline.sh')], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
    def test_guided_offline_handoff_orders_probes_access_core_and_addons(self):
        vendor = ROOT / 'installer/vendor-native'
        source = (vendor / 'run-offline.sh').read_text(encoding='utf-8')
        actual_credentials = (vendor / 'online-credentials.sh').read_text(encoding='utf-8')
        for mode, expected in (
            ('wrong-version', ['version']),
            ('missing-package', ['version', 'package']),
            ('established', ['version', 'package']),
            ('cancelled', ['version', 'package', 'mariadb', 'sip', 'collect']),
            ('core-fails', ['version', 'package', 'mariadb', 'sip', 'collect', 'core']),
            ('marker-remains', ['version', 'package', 'mariadb', 'sip', 'collect', 'core']),
            ('addons-fail', ['version', 'package', 'mariadb', 'sip', 'collect', 'core', 'addons']),
            ('success', ['version', 'package', 'mariadb', 'sip', 'collect', 'core', 'addons']),
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                trace = root / 'events'
                marker = root / 'installamp'
                config = root / 'issabel.conf'
                marker.touch()
                if mode == 'established':
                    config.write_text('mysqlrootpwd=existing-credential\n', encoding='utf-8')
                native = root / 'installer/vendor-native'
                native.mkdir(parents=True)
                shutil.copyfile(vendor / 'terminal-ui.sh', native / 'terminal-ui.sh')
                (native / 'online-credentials.sh').write_text(actual_credentials + r'''
mytel_collect_online_passwords(){
    printf 'collect\n' >> "$TRACE"
    [ "$MODE" != cancelled ] || return 1
    printf '%s\n' 'FakeDB.42!' 'FakeAdmin.52!' pjsip
}
mytel_apply_online_passwords(){
    printf 'core\n' >> "$TRACE"
    [ "$_mytel_db_password" = 'FakeDB.42!' ] && [ "$_mytel_admin_password" = 'FakeAdmin.52!' ] || return 2
    [ "$MYTEL_ONLINE_SIP_DRIVER" = pjsip ] || return 3
    printf 'native fixture diagnostic\n' >&2
    [ "$MODE" != core-fails ] || return 4
    if [ "$MODE" != marker-remains ]; then rm -- "$MARKER" || return 5; fi
}
''', encoding='utf-8')
                runner = root / 'fixture-runner.sh'
                runner.write_text(source.replace('/installamp', marker.as_posix())
                                  .replace('/etc/issabel.conf', config.as_posix()), encoding='utf-8')
                # Check only home-grown fixture stubs. No live sockets, RPM or systemd calls.
                script = 'source ' + shlex.quote(runner.as_posix()) + '\n'
                for variable, value in dict(MODE=mode, TRACE=trace, MARKER=marker, MYTEL_BUNDLE_ROOT=root,
                                            MYTEL_NATIVE_WORK=root, MYTEL_MEDIA_ROOT=root,
                                            MYTEL_MEDIA_MANIFEST_SHA256='sealed', MYTEL_PYTHON='fixture_python').items():
                    script += variable + '=' + shlex.quote(value.as_posix() if isinstance(value, Path) else value) + '\n'
                script += r'''
asterisk(){
    printf 'version\n' >> "$TRACE"
    [ "$*" = '-V' ] || return 90
    if [ "$MODE" = wrong-version ]; then echo 'Asterisk 18.0.0'; else echo 'Asterisk 20.3.0'; fi
}
rpm(){ printf 'package\n' >> "$TRACE"; [ "$*" = '-q --quiet issabel-packetbl' ] && [ "$MODE" != missing-package ]; }
systemctl(){ printf 'mariadb\n' >> "$TRACE"; [ "$*" = 'is-active --quiet mariadb.service' ]; }
fixture_python(){ printf 'sip\n' >> "$TRACE"; [ "$1 $2" = '-I -B' ]; }
bash(){
    printf 'addons\n' >> "$TRACE"
    [ "$1" = "$MYTEL_BUNDLE_ROOT/installer/install-mytel-addons.sh" ] && [ "$ASTVER" = 20 ] && [ "$MODE" != addons-fail ]
}
guided_offline_setup
'''
                result = subprocess.run([BASH, '--noprofile', '--norc', '-s'], input=script.encode(),
                                        capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0 if mode == 'success' else 1, result.stderr)
                self.assertEqual(trace.read_text().splitlines(), expected)
                self.assertNotIn(b'native fixture diagnostic', result.stdout + result.stderr)
                self.assertNotIn(b'FakeAdmin.52!', result.stdout + result.stderr)
                if 'core' in expected:
                    self.assertIn(b'native fixture diagnostic', (root / 'native-init.log').read_bytes())


@unittest.skipUnless(BASH and Path(BASH).is_file(), 'Bash is required')
class NativeOfflineCompletionTests(unittest.TestCase):
    """Execute the generated shell with external stubs and temporary paths only."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='mytel-offline-completion-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.trace = self.root / 'trace'
        self.state = self.root / 'state'
        self.state.mkdir(mode=0o755)
        self.marker = self.state / 'offline-complete'
        self.runner = self.root / 'run-offline.sh'
        scripts = {
            self.bin / 'chvt': 'printf "chvt:%s\\n" "$1" >>"$TRACE"\n',
            self.runner: 'printf "run-offline\\n" >>"$TRACE"\nexit "$RUNNER_RESULT"\n',
            self.bin / 'stat': '''[ "$1" = -c ] && [ "$#" = 3 ] && [ "$3" = "$FIXTURE_STATE" ] || exit 85
case "$2" in
    %u) printf '%s\\n' "$PARENT_UID" ;;
    %a) printf '%s\\n' "$PARENT_MODE" ;;
    *) exit 86 ;;
esac
''',
            self.bin / 'install': '''{
    printf install
    printf ' %s' "$@"
    printf '\\n'
} >>"$TRACE"
directory=0
mode=
while [ "$#" -gt 0 ]; do
    case "$1" in
        -d) directory=1; shift ;;
        -o|-g) [ "$2" = root ] || exit 81; shift 2 ;;
        -m) mode="$2"; shift 2 ;;
        *) break ;;
    esac
done
if [ "$directory" = 1 ]; then
    [ "$#" = 1 ] || exit 82
    target="$1"
else
    [ "$#" = 2 ] && [ "$1" = /dev/null ] || exit 83
    target="$2"
    [ "$INSTALL_RESULT" = 0 ] || exit "$INSTALL_RESULT"
fi
case "$target" in "$FIXTURE_ROOT"/*) ;; *) exit 84 ;; esac
if [ "$directory" = 1 ]; then mkdir -p "$target"; else : >"$target"; fi
chmod "$mode" "$target"
''',
        }
        for path, script in scripts.items():
            path.write_bytes(('#!/bin/bash\nset -eu\n' + script).encode('utf-8'))
            path.chmod(0o755)

    def shell_path(self, path):
        text = path.as_posix()
        return '/' + text[0].lower() + text[2:] if os.name == 'nt' else text

    def boot(self, runner_result=0, install_result=0, parent_uid=0, parent_mode='755', before_command=None):
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.read_string(builder().firstboot_dropin())
        condition = config.get('Unit', 'ConditionPathExists', fallback=None)
        if condition is not None:
            self.assertEqual(condition, '!/var/lib/mytelpbx-native-addons/offline-complete')
            if self.marker.exists():
                return None  # systemd skips the entire unit when this condition fails.
        command = shlex.split(config['Service']['ExecStartPost'])
        start = shlex.split(config['Service']['ExecStart'])
        self.assertEqual(start[:2], ['/bin/bash', '-c'])
        self.assertEqual(command[:2], ['/bin/bash', '-c'])
        # systemd expands %% to a literal % before the command reaches Bash.
        self.assertNotRegex(command[2].replace('%%', ''), r'%[a-zA-Z]',
                            'All stat formats must escape systemd specifiers')
        script = '(' + start[2] + ') && ' + command[2].replace('%%', '%')
        script = script.replace('/usr/local/libexec/mytelpbx/run-offline.sh',
                                shlex.quote(self.shell_path(self.runner)))
        script = script.replace('/var/lib/mytelpbx-native-addons',
                                shlex.quote(self.shell_path(self.state)))
        script = 'PATH=' + shlex.quote(self.shell_path(self.bin)) + ':/usr/bin:/bin\n' + script
        script = 'sleep(){ [ "$1" = 5 ]; }\n' + script
        environment = dict(os.environ, TRACE=self.shell_path(self.trace),
                           FIXTURE_ROOT=self.shell_path(self.root),
                           FIXTURE_STATE=self.shell_path(self.state),
                           PARENT_UID=str(parent_uid), PARENT_MODE=parent_mode,
                           RUNNER_RESULT=str(runner_result), INSTALL_RESULT=str(install_result))
        if before_command is not None:
            before_command()
        return subprocess.run([BASH, '--noprofile', '--norc', '-c', script],
                              env=environment, capture_output=True, timeout=20)

    def events(self):
        return self.trace.read_text().splitlines() if self.trace.exists() else []

    def test_success_marks_private_completion_after_addons_before_returning_to_vt1(self):
        result = self.boot()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.marker.is_file(), 'Successful offline add-ons must prevent next-boot replay')
        self.assertFalse(self.marker.is_symlink())
        self.assertEqual(self.marker.stat().st_nlink, 1)
        events = self.events()
        self.assertEqual(events[:2], ['chvt:2', 'run-offline'])
        self.assertIn('install -d -o root -g root -m 0700 ', events[2])
        self.assertIn('install -o root -g root -m 0600 /dev/null ', events[3])
        self.assertEqual(events[4:], ['chvt:1'])
        if os.name != 'nt':
            self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
            self.assertEqual(self.marker.stat().st_mode & 0o777, 0o600)

    def test_failed_addons_leave_no_completion_and_preserve_failure_on_vt2(self):
        result = self.boot(runner_result=71)
        self.assertEqual(result.returncode, 71, result.stderr)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.events(), ['chvt:2', 'run-offline'])

    def test_completed_previous_boot_skips_even_when_addons_would_now_fail(self):
        self.marker.write_bytes(b'')
        self.marker.chmod(0o600)
        self.assertIsNone(self.boot(runner_result=71), 'Completed installation must skip native unit on reboot')
        self.assertEqual(self.events(), [])

    def test_failed_completion_write_is_not_hidden_or_marked_successful(self):
        result = self.boot(install_result=74)
        self.assertEqual(result.returncode, 74, result.stderr)
        self.assertFalse(self.marker.exists())
        events = self.events()
        self.assertEqual(events[:2], ['chvt:2', 'run-offline'])
        self.assertEqual(len(events), 4)
        self.assertTrue(events[2].startswith('install -d '))
        self.assertTrue(events[3].startswith('install -o '))

    def test_unsafe_existing_parent_is_rejected_before_metadata_changes(self):
        for uid, mode in ((99, '755'), (0, '775'), (0, '757')):
            with self.subTest(uid=uid, mode=mode):
                if self.trace.exists():
                    self.trace.unlink()
                result = self.boot(parent_uid=uid, parent_mode=mode)
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertFalse(self.marker.exists())
                self.assertEqual(self.events(), ['chvt:2', 'run-offline'])

    def symlink(self, path, target, directory=False):
        try:
            path.symlink_to(target, target_is_directory=directory)
        except OSError as error:
            if os.name == 'nt' and getattr(error, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege is unavailable')
            raise

    def test_symlinked_parent_is_rejected_without_touching_its_target(self):
        target = self.root / 'other'
        target.mkdir()
        self.state.rmdir()
        self.symlink(self.state, target, directory=True)
        result = self.boot()
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(self.events(), ['chvt:2', 'run-offline'])

    def test_dangling_marker_link_after_unit_condition_is_rejected(self):
        target = self.root / 'missing-target'
        result = self.boot(before_command=lambda: self.symlink(self.marker, target))
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.marker.is_symlink())
        self.assertFalse(target.exists())
        self.assertEqual(self.events(), ['chvt:2', 'run-offline'])


if __name__ == '__main__':
    unittest.main()
