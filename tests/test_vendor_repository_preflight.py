"""Repository checks use isolated metadata and report all failed sources."""

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'installer/vendor-native/repository-preflight.py'
SPEC = importlib.util.spec_from_file_location('preflight', SOURCE)
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class RepositoryPreflightTests(unittest.TestCase):
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
