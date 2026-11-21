"""Repository checks use isolated metadata and report all failed sources."""

import importlib.util
import io
import subprocess
import os
import shlex
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'installer/vendor-native/repository-preflight.py'
SPEC = importlib.util.spec_from_file_location('preflight', SOURCE)
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class RepositoryPreflightTests(unittest.TestCase):
    def test_native_rpm_replacement_is_restored_without_touching_other_repos(self):
        bash = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')
        if not bash or not Path(bash).is_file():
            self.skipTest('Bash is required')
        native = SOURCE.with_name('mytelpbx-netinstall.sh').read_text(encoding='utf-8')
        function = native.split('function mytel_restore_vendor_repos()', 1)[1].split('\n}', 1)[0]
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            verified, installed = root / 'vendor', root / 'system'
            verified.mkdir(); installed.mkdir()
            files = ['Issabel.repo', 'Issabel5.repo', 'commercial-addons.repo']
            for filename in files:
                (verified / filename).write_text('pinned:' + filename)
                (installed / filename).write_text('rpm-supplied')
            (installed / 'unrelated.repo').write_text('keep')
            script = ('function mytel_restore_vendor_repos()' + function + '\n}\n').replace('/etc/yum.repos.d', installed.as_posix())
            script += 'MYTEL_APPROVED_VENDOR_REPOS=' + shlex.quote(verified.as_posix()) + '\nmytel_restore_vendor_repos\n'
            subprocess.run([bash, '-s'], input=script.encode(), check=True, capture_output=True)
            self.assertEqual([(installed / f).read_text() for f in files], ['pinned:' + f for f in files])
            self.assertEqual((installed / 'unrelated.repo').read_text(), 'keep')

    def test_slow_active_fetch_can_finish_and_idle_fetch_times_out(self):
        process = Mock(pid=123, args=['dnf'])
        timeout = subprocess.TimeoutExpired(['dnf'], 5)
        process.wait.side_effect = [timeout, timeout, 0]
        with patch.object(preflight, 'process_activity', side_effect=[(0, 0), (131072, 0), (262144, 0)]):
            self.assertEqual(preflight.wait_for_metadata(process, iter([0, 110, 220]).__next__), 0)
        process.wait.side_effect = timeout
        with patch.object(preflight, 'process_activity', return_value=(0, 0)), self.assertRaises(subprocess.TimeoutExpired):
            preflight.wait_for_metadata(process, iter([0, 151]).__next__)

    def test_cache_handoff_only_moves_native_metadata_for_matching_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'first', Path(directory) / 'second'
            source.mkdir()
            for name in ['baseos-0123456789abcdef', 'baseos-other-0123456789abcdef']:
                (source / name).mkdir()
            (source / 'metadata_lock.pid').write_text('fixture')
            preflight.move_repo_metadata('baseos', source, target)
            self.assertEqual([p.name for p in target.iterdir()], ['baseos-0123456789abcdef'])
            self.assertEqual({p.name for p in source.iterdir()}, {'baseos-other-0123456789abcdef', 'metadata_lock.pid'})

    def test_dnf_refreshes_only_selected_repo_with_private_paths_and_no_silent_skip(self):
        home = Path('/work/probe')
        args = preflight.dnf_command('issabel-base', ['/work/overlay'], home)
        for expected in ('--refresh', '--disablerepo=*', '--enablerepo=issabel-base',
                         '--setopt=issabel-base.skip_if_unavailable=False', 'makecache'):
            self.assertIn(expected, args)
        for setting, suffix in [('cachedir', 'cache'), ('persistdir', 'state'), ('logdir', '')]:
            self.assertIn('--setopt=' + setting + '=' + str(home / suffix), args)
        self.assertNotIn('install', args)

    def test_aggregates_success_failure_required_missing_and_bootstrap_download(self):
        inventory = (['/work/overlay'], ['baseos', 'issabel-base'], ['powertools'])
        expected_url = 'https://repo.example/remi.rpm'
        seen = set()

        def fake_probe(task):
            label, _args, logfile = task
            seen.add(label)
            failed = label == 'issabel-base'
            return label, int(failed), 'Curl error (35)' if failed else '', logfile

        with tempfile.TemporaryDirectory() as root, \
                patch.object(preflight, 'repository_inventory', return_value=inventory), \
                patch.object(preflight, 'probe', side_effect=fake_probe), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(preflight.run(Path(root), None, [], [expected_url]), 1)
            self.assertEqual(seen, {'baseos', 'issabel-base', expected_url})
            self.assertIn('FAIL issabel-base', output.getvalue())
            self.assertIn('FAIL powertools', output.getvalue())
            self.assertIn('2 passed, 2 failed', output.getvalue())
            self.assertEqual([p.name for p in Path(root).iterdir()], ['repository-checks'])

    def test_diagnostics_keep_hostname_and_reason_but_remove_url_credentials(self):
        raw = '  - Curl error (35) for https://name:pass@example.org/meta?token=private [SSL error]'
        result = preflight.diagnostic(raw)
        self.assertIn('https://example.org/meta', result)
        self.assertIn('Curl error (35)', result)
        self.assertNotIn('pass', result)
        self.assertNotIn('private', result)

    def test_bootstrap_download_and_redirects_require_https(self):
        args = preflight.curl_command('https://repo.example/r.rpm')
        self.assertEqual(args[args.index('--proto') + 1], '=https')
        self.assertEqual(args[args.index('--proto-redir') + 1], '=https')
        self.assertNotIn('--insecure', args)


if __name__ == '__main__':
    unittest.main()
