"""Preserve the supplied ISO's native installer, package groups and firstboot."""
import configparser
import importlib.util
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/vendor-iso'
BASH = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')


def builder():
    spec = importlib.util.spec_from_file_location('native_iso', ROOT / 'scripts/remaster-vendor-iso.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeIsoStructureTests(unittest.TestCase):
    def test_kickstart_preserves_storage_packages_and_native_core_trigger(self):
        module = builder()
        original = (FIXTURE / 'issabel.ks').read_text(encoding='utf-8')
        result = module.kickstart(original)
        for token in ['clearpart --all --initlabel', 'autopart --type=plain --fstype=ext4',
                      '@^issabelast20', '@rbl', '@guru', 'touch /mnt/sysimage/installamp',
                      'reboot --eject', 'firewall --disabled', 'selinux --disabled']:
            self.assertIn(token, result)
        self.assertEqual(re.search(r'%packages\n(.*?)\n%end', result, re.S).group(1),
                         re.search(r'%packages\n(.*?)\n%end', original, re.S).group(1))
        expected = original.replace('issabel.local', 'mytelpbx.local')
        for line in module.ONLINE_POST_LINES:
            self.assertEqual(expected.count(line), 1)
            expected = expected.replace(line, '')
        self.assertEqual(result.split('\n# MYTEL_NATIVE_ADDONS_BEGIN\n')[0], expected.rstrip('\n'))
        self.assertNotIn('install_amp', result)
        self.assertNotIn('prepare-native-start', result)
        self.assertNotIn('geoip_install.sh', result)
        self.assertIn('--verify-media', result)
        self.assertIn('--tool completion', result)

    def test_unknown_native_kickstart_drift_is_refused(self):
        with self.assertRaises(ValueError):
            builder().kickstart((FIXTURE / 'issabel.ks').read_text() + '\n# unreviewed\n')

    def test_success_only_dropin_does_not_replace_native_execstart(self):
        module = builder()
        scripts = (FIXTURE / 'firstboot-rpm-scripts.txt').read_text()
        unit = scripts.split("<<'ISSABELFIRSTBOOT'\n", 1)[1].split('\nISSABELFIRSTBOOT', 1)[0]
        self.assertIn('/usr/bin/issabel-admin-passwords --init && chvt 1 && dmesg -E', unit)
        dropin = module.firstboot_dropin()
        self.assertNotRegex(dropin, r'(?m)^ExecStart=')
        self.assertNotIn('ExecStartPre=', dropin)
        self.assertIn('ExecStartPost=', dropin)
        self.assertIn('chvt 2 && /bin/bash /usr/local/libexec/mytelpbx/run-offline.sh && chvt 1', dropin)
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


if __name__ == '__main__':
    unittest.main()
