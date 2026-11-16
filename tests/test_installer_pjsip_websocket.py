"""Fresh-only native WebSocket ownership; all subprocesses are fixture-owned."""
import importlib.util
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('pjsip_websocket', ROOT / 'installer/prepare-pjsip-websocket.py')
WS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WS)


class NativeRowsTests(unittest.TestCase):
    def test_factory_adds_exactly_one_native_boolean_preserving_every_seed(self):
        before = WS.factory_rows()
        actual = WS.plan_rows(before)
        self.assertEqual(actual, sorted(before + [['websocket_enabled', 'no', '0', '0']]))
        self.assertEqual(len(before), 17)
        self.assertEqual(before, WS.factory_rows())

    def test_explicit_operator_choice_is_never_changed(self):
        for choice in ['yes', 'no', 'unknown']:
            self.assertIsNone(WS.plan_rows(WS.factory_rows() + [['websocket_enabled', choice, '0', '0']]))

    def test_nonfactory_profile_and_custom_values_are_refused(self):
        for rows in [[], WS.factory_rows()[1:], WS.factory_rows() + [['nat_mode', 'public', '0', '0']]]:
            with self.assertRaises(ValueError):
                WS.plan_rows(rows)

    def test_malformed_rows_and_nonstring_values_are_refused(self):
        for rows in [None, {}, [[1, 'no', '0', '0']], [['x']]]:
            with self.assertRaises(ValueError): WS.plan_rows(rows)

    def test_native_idle_and_module_status_are_not_http_or_exit_code_proxies(self):
        WS.idle('0 active channels\n0 active calls\n1 calls processed\n')
        for value in ['', '0 active calls', '1 active channels\n0 active calls',
                      '0 active channels\n0 active calls\n0 active calls']:
            with self.assertRaises(ValueError): WS.idle(value)
        for value in ['Running', '0 modules loaded', 'res_pjsip_transport_websocket.so broken 0 Unknown core']:
            with self.assertRaises(ValueError): WS.module_status(value)


class NativeConfigBytesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.config=self.root/'etc/asterisk';self.config.mkdir(parents=True)

    def write(self,name,value):
        path=self.config/name;path.write_bytes(value);return path

    def test_native_legacy_comment_does_not_block_or_rewrite_unrelated_config(self):
        raw=b'; native legacy comment \xe5\n[general]\nmailcmd=/usr/sbin/sendmail -t\n'
        path=self.write('minivm.conf',raw)
        self.assertFalse(WS.overrides(self.root));self.assertEqual(path.read_bytes(),raw)

    def test_legacy_comment_does_not_hide_explicit_yes_or_noload(self):
        for directive in [b'websocket_enabled=yes\n',b'noload => res_pjsip_transport_websocket.so ; legacy \xe5\n']:
            with self.subTest(directive=directive):
                raw=b'; legacy \xe5\n'+directive;path=self.write('custom.conf',raw)
                self.assertTrue(WS.overrides(self.root));self.assertEqual(path.read_bytes(),raw)

    def test_generated_only_no_remains_valid_with_legacy_comments_elsewhere(self):
        other=self.write('minivm.conf',b'; legacy \xe5\n[general]\n')
        generated=self.write('sip_general_additional.conf',b'; generated legacy \xe5\nwebsocket_enabled=no\n')
        before={path.name:path.read_bytes()for path in [other,generated]}
        self.assertFalse(WS.overrides(self.root,generated=True))
        self.assertEqual({path.name:path.read_bytes()for path in [other,generated]},before)

    def test_nonascii_boolean_value_is_preserved_and_not_accepted_as_generated_no(self):
        raw=b'websocket_enabled=no\xe5\n';path=self.write('sip_general_additional.conf',raw)
        self.assertTrue(WS.overrides(self.root));self.assertTrue(WS.overrides(self.root,generated=True))
        self.assertEqual(path.read_bytes(),raw)

    def test_nonascii_suffix_on_known_module_noload_is_preserved(self):
        raw=b'noload => res_pjsip_transport_websocket.so\xe5\n';path=self.write('modules.conf',raw)
        self.assertTrue(WS.overrides(self.root));self.assertTrue(WS.overrides(self.root,generated=True))
        self.assertEqual(path.read_bytes(),raw)

    def test_duplicate_or_custom_generated_choice_is_still_refused(self):
        self.write('sip_general_additional.conf',b'; legacy \xe5\nwebsocket_enabled=no\n')
        self.write('sip_general_custom.conf',b'websocket_enabled=no\n')
        self.assertTrue(WS.overrides(self.root,generated=True))

    def test_nul_binary_configuration_is_refused_without_rewriting(self):
        raw=b'w\x00e\x00b\x00s\x00o\x00c\x00k\x00e\x00t\x00_enabled=no\n';path=self.write('custom.conf',raw)
        with self.assertRaises(ValueError):WS.overrides(self.root)
        self.assertEqual(path.read_bytes(),raw)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'; self.state.mkdir(mode=0o700)
        self.version = '7.6.1'; self.bundle = 'a' * 64
        self.write('etc/os-release', 'ID="rocky"\nVERSION_ID="8.10"\n')
        self.write('etc/machine-id', 'b' * 32)
        self.write('run/asterisk/asterisk.pid', '123')
        self.write('proc/123/comm', 'asterisk\n')
        self.write('proc/123/stat', '123 (asterisk) ' + ' '.join(['S'] + ['0'] * 18 + ['456']) + '\n')
        (self.root / 'etc/asterisk').mkdir()
        source = self.state / 'source.json'
        source.write_text(json.dumps(dict(owner='MyTellPBX', schema=1, version=self.version,
                                         bundle_sha256=self.bundle)), encoding='utf-8'); source.chmod(0o600)
        self.snapshot = dict(rows=WS.factory_rows(), columns=copy.deepcopy(WS.SCHEMA),
                             primary=['keyword','seq','type'], engine='InnoDB',
                             counts=dict(devices=0,users=0,trunks=0), transaction=0, autocommit=True)
        self.commands = []; self.actions = []; self.major = 20
        self.module = 'Not Running'; self.load_failures = 0; self.calls = 0
        self.insert_failure = None

    def write(self, relative, text):
        path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8')); return path

    def fixture_run(self, command, payload=None, timeout=30):
        self.commands.append(command)
        value = command[-1]
        if value == 'core show version': return 'Asterisk {}.12.0 built by fixture'.format(self.major)
        if value == 'core show channels count': return '0 active channels\n{} active calls\n0 calls processed\n'.format(self.calls)
        if value == 'sip reload': return 'SIP Reload queued\n'
        if value == 'module show like ' + WS.MODULE:
            return WS.MODULE + ' PJSIP WebSocket Transport Support 0 ' + self.module + ' core\n1 modules loaded\n'
        if value == 'module load ' + WS.MODULE:
            if self.load_failures:
                self.load_failures -= 1; raise ValueError('Still occupied')
            self.module = 'Running'; return 'Loaded\n'
        self.fail('Unexpected native command ' + repr(command))

    def native(self, action, payload, run):
        self.actions.append(action)
        if action == 'insert':
            journal = json.loads((self.state / 'pjsip-websocket.json').read_text())
            self.assertEqual(journal['phase'], 'prepared')
            self.assertEqual(journal['before']['rows'], WS.factory_rows())
            self.assertEqual(payload, {'before_rows_sha256': WS.digest(WS.factory_rows())})
            if self.insert_failure == 'before': raise ValueError('Fixture before write')
            self.snapshot['rows'] = sorted(WS.factory_rows() + [WS.ROW])
            if self.insert_failure == 'after': raise ValueError('Fixture lost acknowledgment')
        return copy.deepcopy(self.snapshot)

    def execute(self, phase):
        return WS.execute(phase, self.root, self.state, self.version, self.bundle,
                          self.fixture_run, self.native, sleep=lambda seconds: None)

    def generate(self):
        self.write('etc/asterisk/sip_general_additional.conf', '; native generated\nwebsocket_enabled=no\n')

    def test_prepare_then_native_generation_then_activate_is_bounded_and_idempotent(self):
        self.assertEqual(self.execute('prepare'), 'prepared')
        self.assertEqual(self.actions.count('insert'), 1)
        self.assertFalse(any('reload' in c[-1] or 'module load' in c[-1] for c in self.commands))
        self.assertEqual(self.execute('prepare'), 'prepared')
        self.assertEqual(self.actions.count('insert'), 1)
        self.generate()
        self.assertEqual(self.execute('activate'), 'ready')
        self.assertEqual(sum(c[-1] == 'sip reload' for c in self.commands), 1)
        self.assertEqual(self.module, 'Running')
        before = len(self.commands)
        self.snapshot['rows'][-1] = ['websocket_enabled', 'yes', '0', '0']
        self.assertEqual(self.execute('prepare'), 'completed; not reapplied')
        self.assertEqual(len(self.commands), before, 'Completed stage must not reassert over a later operator choice')
        self.assertFalse(any('restart' in c[-1] or 'unload' in c[-1] or 'core reload' in c[-1] for c in self.commands))

    def test_supported_asterisk_families_and_other_platform_refusal(self):
        for major in [16,18,20]:
            self.major = major
            self.assertEqual(WS.platform(self.root, self.fixture_run)['pid'], '123')
        self.major = 22
        with self.assertRaises(ValueError): self.execute('prepare')
        for distro in ['ID="rocky"\nVERSION_ID="9.0"', 'ID="rhel"\nVERSION_ID="8.10"']:
            self.write('etc/os-release', distro)
            with self.assertRaises(ValueError): self.execute('prepare')
        self.assertFalse(self.actions)

    def test_source_receipt_and_completed_framework_refuse_before_changes(self):
        with self.assertRaises(ValueError):
            WS.execute('prepare', self.root, self.state, self.version, 'c' * 64, self.fixture_run, self.native)
        self.write('state/stages/framework.done', '')
        with self.assertRaises(ValueError): self.execute('prepare')
        self.assertFalse(self.commands); self.assertFalse(self.actions)

    def test_existing_devices_users_trunks_and_active_calls_preserved(self):
        for table in ['devices','users','trunks']:
            self.snapshot['counts'][table] = 1
            with self.assertRaises(ValueError): self.execute('prepare')
            self.snapshot['counts'][table] = 0
        self.calls = 1
        with self.assertRaises(ValueError): self.execute('prepare')
        self.assertNotIn('insert', self.actions)
        self.assertFalse((self.state / 'pjsip-websocket.json').exists())

    def test_unknown_schema_engine_or_transaction_never_writes(self):
        for key,value in [('engine','MyISAM'),('transaction',1),('autocommit',False),('primary',['keyword']),
                          ('columns',[]),('counts',dict(devices=False,users=0,trunks=0))]:
            saved = self.snapshot[key]; self.snapshot[key] = value
            with self.assertRaises(ValueError): self.execute('prepare')
            self.snapshot[key] = saved
        self.assertNotIn('insert', self.actions)

    def test_explicit_native_choices_are_skipped_even_no_without_reloading(self):
        for choice in ['yes','no']:
            self.snapshot['rows'] = WS.factory_rows() + [['websocket_enabled',choice,'0','0']]
            self.assertEqual(self.execute('prepare'), 'skipped')
            self.assertEqual(self.execute('activate'), 'skipped')
            (self.state / 'pjsip-websocket.json').unlink()
        self.assertNotIn('insert', self.actions)
        self.assertFalse(any(c[-1] == 'sip reload' for c in self.commands))

    def test_custom_overrides_and_explicit_module_noload_preserved(self):
        path = self.write('etc/asterisk/sip_general_custom.conf', 'websocket_enabled=yes\n')
        self.assertEqual(self.execute('prepare'), 'skipped')
        (self.state / 'pjsip-websocket.json').unlink(); path.unlink()
        self.write('etc/asterisk/modules.conf', 'noload => res_pjsip_transport_websocket.so\n')
        self.assertEqual(self.execute('prepare'), 'skipped')
        self.assertNotIn('insert', self.actions)

    def test_actual_native_core_sip_link_is_read_without_treating_it_as_an_override(self):
        link = self.write('etc/asterisk/sip.conf', 'placeholder for link metadata')
        target = '/var/www/html/admin/modules/core/etc/sip.conf'
        self.write(target.lstrip('/'), '[general]\n#include sip_general_additional.conf\n')
        # Runs the actual is_symlink/readlink decision on Windows as well. The
        # native POSIX fixture below additionally uses a real symbolic link.
        with mock.patch.object(WS.Path, 'is_symlink', lambda p: p == link), \
             mock.patch.object(WS.os, 'readlink', return_value=target):
            self.assertFalse(WS.overrides(self.root))

    def test_unrecognized_outward_config_link_is_refused_without_reading_it(self):
        link = self.write('etc/asterisk/sip.conf', 'placeholder')
        with mock.patch.object(WS.Path, 'is_symlink', lambda p: p == link), \
             mock.patch.object(WS.os, 'readlink', return_value='/etc/shadow'):
            with self.assertRaises(ValueError): WS.overrides(self.root)

    @unittest.skipIf(os.name == 'nt', 'Native symbolic-link shape of retrieve_conf')
    def test_all_fifteen_native_module_links_are_supported_but_nested_redirect_is_not(self):
        for name,target in WS.CONFIG_LINKS.items():
            self.write(target.lstrip('/'), '; disposable native module fixture\n')
            (self.root / 'etc/asterisk' / name).symlink_to(target)
        self.assertEqual(len(WS.CONFIG_LINKS), 15)
        self.assertFalse(WS.overrides(self.root))
        target = self.root / WS.CONFIG_LINKS['sip.conf'].lstrip('/')
        target.unlink(); target.symlink_to(self.root / 'unrecognized')
        with self.assertRaises(ValueError): WS.overrides(self.root)

    def test_durable_intent_recovers_only_exact_before_or_after_write(self):
        self.insert_failure = 'before'
        with self.assertRaises(ValueError): self.execute('prepare')
        self.insert_failure = 'after'
        with self.assertRaises(ValueError): self.execute('prepare')
        count = self.actions.count('insert')
        self.insert_failure = None
        self.assertEqual(self.execute('prepare'), 'prepared')
        self.assertEqual(self.actions.count('insert'), count)
        self.snapshot['rows'].append(['changed','retained','0','0'])
        with self.assertRaises(ValueError): self.execute('prepare')

    def test_activation_requires_exact_generated_setting_and_same_pid(self):
        self.execute('prepare')
        with self.assertRaises(ValueError): self.execute('activate')
        self.generate(); self.write('etc/asterisk/sip_custom.conf', 'websocket_enabled=yes\n')
        with self.assertRaises(ValueError): self.execute('activate')
        (self.root / 'etc/asterisk/sip_custom.conf').unlink()
        self.write('proc/123/stat', '123 (asterisk) ' + ' '.join(['S'] + ['0'] * 18 + ['999']))
        with self.assertRaises(ValueError): self.execute('activate')
        self.assertFalse(any(c[-1] == 'sip reload' for c in self.commands))

    def test_queued_sip_reload_can_decline_then_recover_exact_module(self):
        self.execute('prepare'); self.generate(); self.load_failures = 2
        self.assertEqual(self.execute('activate'), 'ready')
        self.assertEqual(sum(c[-1] == 'module load ' + WS.MODULE for c in self.commands), 3)

    def test_persistent_module_failure_stops_and_keeps_owned_intent(self):
        self.execute('prepare'); self.generate(); self.load_failures = 10
        with self.assertRaises(ValueError): self.execute('activate')
        self.assertEqual(sum(c[-1] == 'module load ' + WS.MODULE for c in self.commands), 4)
        self.assertEqual(json.loads((self.state / 'pjsip-websocket.json').read_text())['phase'], 'prepared')
        self.assertEqual(self.snapshot['rows'], sorted(WS.factory_rows() + [WS.ROW]))

    @unittest.skipIf(os.name == 'nt', 'POSIX private-state mode enforcement')
    def test_state_and_receipt_mode_or_symlink_drift_refused(self):
        (self.state / 'source.json').chmod(0o644)
        with self.assertRaises(ValueError): self.execute('prepare')
        (self.state / 'source.json').chmod(0o600)
        self.execute('prepare')
        journal = self.state / 'pjsip-websocket.json'
        self.assertEqual(journal.stat().st_mode & 0o777, 0o600)
        journal.rename(self.state / 'previous'); journal.symlink_to(self.state / 'previous')
        with self.assertRaises(ValueError): self.execute('prepare')


PHP = shutil.which('php')


@unittest.skipUnless(PHP, 'Native PHP adapter fixture runs on Linux/PHP')
class NativeAdapterTests(unittest.TestCase):
    def fixture(self, mode):
        adapter = ROOT / 'installer/pjsip-websocket-native.php'
        body = r'''<?php
define('DB_FETCHMODE_ORDERED',1); define('DB_FETCHMODE_ASSOC',2);
class DB { static function isError($v) { return $v instanceof Exception; } }
class FixtureDB {
 public $autocommit=true, $rows, $before, $transaction=0, $writes=array(), $mode;
 function __construct($rows,$mode) { $this->rows=$rows; $this->before=$rows; $this->mode=$mode; }
 function getOne($q) {
  if (strpos($q,'COUNT(*)')!==false) return $this->mode==='existing' ? 1 : 0;
  if (strpos($q,'SELECT ENGINE')===0) return $this->mode==='myisam' ? 'MyISAM' : 'InnoDB';
  if ($q==='SELECT @@in_transaction') return $this->mode==='outer' ? 1 : $this->transaction;
  throw new Exception('Unexpected scalar SQL');
 }
 function getAll($q,$params=null,$fetch=null) {
  if (strpos($q,'SELECT keyword')===0) return $this->rows;
  if ($q==='SHOW COLUMNS FROM sipsettings') {
   $a=array(); foreach (array(array('keyword','varchar(50)','NO','','PRI',''),array('data','varchar(255)','NO','','',''),
    array('seq','tinyint(1)','NO','1','PRI',''),array('type','tinyint(1)','NO','0','PRI','')) as $v) {
    if ($this->mode==='schema' && $v[0]==='keyword') $v[1]='varchar(100)';
    if ($this->mode==='nulldefault' && $v[0]==='keyword') $v[3]=null;
    $a[]=array_combine(array('Field','Type','Null','Default','Key','Extra'),$v); } return $a;
  }
  if ($q==='SHOW INDEX FROM sipsettings') return array(array('Key_name'=>'PRIMARY','Seq_in_index'=>1,'Column_name'=>'keyword'),
   array('Key_name'=>'PRIMARY','Seq_in_index'=>2,'Column_name'=>'seq'),array('Key_name'=>'PRIMARY','Seq_in_index'=>3,'Column_name'=>'type'));
  throw new Exception('Unexpected rows SQL');
 }
 function query($q) {
  $this->writes[]=$q;
  if ($q==='START TRANSACTION') {$this->transaction=1; return true;}
  if ($q==='COMMIT') {if ($this->mode==='commitfail') return new Exception('Lost commit acknowledgment'); $this->transaction=0; return true;}
  if ($q==='ROLLBACK') {$this->rows=$this->before; $this->transaction=0; return true;}
  throw new Exception('Unexpected mutating SQL');
 }
 function prepare($q) {if ($q!=='INSERT INTO sipsettings (keyword,data,seq,type) VALUES (?,?,?,?)') throw new Exception('SQL changed'); return $q;}
 function execute($q,$params) {$this->writes[]=array($q,$params); if ($this->mode==='insertfail') return new Exception('Insert failure'); $this->rows[]=$params; sort($this->rows); return true;}
}
$input=json_decode(stream_get_contents(STDIN),true);
require ''' + json.dumps(str(adapter).replace('\\','/')) + r''';
$db=new FixtureDB($input['rows'],$input['mode']);
if ($input['mode']==='noautocommit') $db->autocommit=false;
$ok=true; try { $result=mytel_ws_insert($db,$input['hash']); } catch (Throwable $e) { $ok=false; }
echo json_encode(array('ok'=>$ok,'rows'=>$db->rows,'writes'=>$db->writes));
'''
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'fixture.php'; script.write_bytes(body.encode('utf-8'))
            # The adapter uses the normal native PHP CLI: Rocky PHP 7.4 loads JSON
            # as a shared extension, so -n would test a different, unusable runtime.
            result = subprocess.run([PHP, str(script)], input=json.dumps(dict(rows=WS.factory_rows(),
                                    mode=mode, hash=WS.digest(WS.factory_rows()))).encode('utf-8'),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        return json.loads(result.stdout.decode('utf-8'))

    def test_native_parameterized_single_insert_preserves_every_other_row(self):
        result = self.fixture('ready')
        self.assertTrue(result['ok']); self.assertEqual(result['rows'], sorted(WS.factory_rows() + [WS.ROW]))
        self.assertEqual(result['writes'][0], 'START TRANSACTION')
        self.assertEqual(result['writes'][1][1], WS.ROW)
        self.assertEqual(result['writes'][2], 'COMMIT')

    def test_existing_devices_unknown_schema_engine_and_outer_transaction_do_not_write(self):
        for mode in ['existing','myisam','outer','noautocommit','schema','nulldefault']:
            result = self.fixture(mode); self.assertFalse(result['ok']); self.assertEqual(result['writes'], [])
            self.assertEqual(result['rows'], WS.factory_rows())

    def test_native_insert_or_commit_failure_rolls_back_only_owned_transaction(self):
        for mode in ['insertfail','commitfail']:
            result = self.fixture(mode); self.assertFalse(result['ok'])
            self.assertEqual(result['writes'][-1], 'ROLLBACK')
            self.assertEqual(result['rows'], WS.factory_rows())


if __name__ == '__main__':
    unittest.main()
