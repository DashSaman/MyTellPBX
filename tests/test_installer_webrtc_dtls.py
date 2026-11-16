"""Real OpenSSL crypto and disposable native-path fixtures; never touch host TLS/PBX."""
import datetime
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
HELPER=ROOT/'installer/prepare-webrtc-dtls.py'
OPENSSL=shutil.which('openssl') or 'C:/Program Files/Git/usr/bin/openssl.exe'
POSIX=unittest.skipUnless(os.name=='posix','Native descriptor/ownership fixture requires POSIX')

def load():
 spec=importlib.util.spec_from_file_location('prepare_webrtc_dtls',str(HELPER));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class WebRTCDTLSTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='mytell-dtls-');self.addCleanup(self.tmp.cleanup)
  self.base=Path(self.tmp.name);self.root=self.base/'root';self.root.mkdir(mode=0o700)
  self.backup=self.root/'var/lib/mytelpbx-installer/webrtc-dtls';self.target=self.root/'etc/asterisk/keys/asterisk.pem'
  self.uid=os.getuid() if hasattr(os,'getuid') else 989;self.gid=os.getgid()if hasattr(os,'getgid') else 984
  self.m=load();self.labels=[]
 def command(self,*args,data=None):
  return subprocess.check_output([OPENSSL]+list(args),input=data,stderr=subprocess.PIPE)
 def material(self,subject='Existing customer WebRTC'):
  cert=self.base/'cert.pem';key=self.base/'key.pem'
  subprocess.check_call([OPENSSL,'req','-x509','-newkey','rsa:2048','-nodes','-sha256','-days','2','-subj','/CN='+subject,'-keyout',str(key),'-out',str(cert)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  return cert.read_bytes()+key.read_bytes()
 def prepare(self,**kw):
  args=dict(openssl=OPENSSL,relabel=lambda paths:self.labels.extend(paths));args.update(kw)
  return self.m.prepare(self.root,self.backup,self.uid,self.gid,**args)
 def write(self,data,mode=0o600):
  self.target.parent.mkdir(parents=True,exist_ok=True);self.target.write_bytes(data);os.chmod(str(self.target),mode)
 def test_real_plaintext_combined_pair_has_sha256_fingerprint_without_files_or_commands_on_host(self):
  value=self.material();result=self.m.validate_material(value,OPENSSL)
  self.assertRegex(result,r'^[a-f0-9]{64}$');self.assertEqual(result,self.m.digest(self.command('x509','-outform','DER',data=value)))
 def test_mismatched_partial_encrypted_and_duplicate_private_material_are_refused(self):
  first=self.material();second=self.material('Another identity')
  cert=first.split(b'-----BEGIN PRIVATE KEY-----')[0]
  wrong=second[second.index(b'-----BEGIN PRIVATE KEY-----'):]
  for value in [b'',b'not a certificate',cert,wrong,cert+wrong,first+wrong]:
   with self.subTest(shape=len(value)):
    with self.assertRaises(ValueError):self.m.validate_material(value,OPENSSL)
  encrypted=self.base/'encrypted.pem';self.command('pkcs8','-topk8','-in',str(self.base/'key.pem'),'-passout','pass:','-out',str(encrypted))
  with self.assertRaises(ValueError):self.m.validate_material(cert+encrypted.read_bytes(),OPENSSL)
 def test_expired_or_not_yet_valid_certificate_is_refused_without_rewriting(self):
  value=self.material();original=datetime.datetime
  for year in [2000,2050]:
   class Clock(original):
    @classmethod
    def utcnow(cls):return original(year,1,1)
   with mock.patch.object(self.m.datetime,'datetime',Clock):
    with self.assertRaises(ValueError):self.m.validate_material(value,OPENSSL)
 @POSIX
 def test_absent_native_pem_is_distinct_valid_branded_service_private_and_idempotent(self):
  # Existing unrelated Apache material must never be used as a key source.
  apache=self.root/'etc/pki/tls/private/localhost.key';apache.parent.mkdir(parents=True);apache.write_bytes(b'UNRELATED APACHE KEY - MUST REMAIN EXACT')
  before=apache.read_bytes();result=self.prepare();self.assertEqual(result['status'],'created')
  value=self.target.read_bytes();self.assertEqual(self.m.validate_material(value,OPENSSL),result['fingerprint_sha256']);self.assertIn(b'BEGIN CERTIFICATE',value);self.assertIn(b'BEGIN PRIVATE KEY',value)
  self.assertIn(b'MyTellPBX',self.command('x509','-noout','-subject',data=value));self.assertEqual(apache.read_bytes(),before)
  st=self.target.stat();self.assertEqual((st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode)),(self.uid,self.gid,0o600))
  frozen=(value,st.st_mtime_ns,st.st_ino);again=self.prepare();self.assertEqual(again['status'],'preserved');self.assertEqual(frozen,(self.target.read_bytes(),self.target.stat().st_mtime_ns,self.target.stat().st_ino))
  self.assertEqual(self.labels,[self.target])
 @POSIX
 def test_exact_empty_native_placeholder_is_backed_up_before_atomic_repair(self):
  self.write(b'',0o664);before=self.target.stat();result=self.prepare();self.assertEqual(result['status'],'repaired-empty')
  originals=list(self.backup.glob('*/original.pem'));self.assertEqual(len(originals),1);self.assertEqual(originals[0].read_bytes(),b'');self.assertEqual(stat.S_IMODE(originals[0].stat().st_mode),0o600)
  import json
  receipt=json.loads((originals[0].parent/'receipt.json').read_text());self.assertEqual(receipt['before']['ino'],before.st_ino);self.assertEqual(receipt['before']['mode'],0o664);self.assertEqual(receipt['before']['sha256'],self.m.digest(b''))
  self.assertGreater(self.target.stat().st_size,0);self.assertNotEqual(self.target.stat().st_ino,before.st_ino);self.assertEqual(stat.S_IMODE(self.target.stat().st_mode),0o600)
 @POSIX
 def test_valid_custom_material_preserves_bytes_inode_mode_mtime_and_does_not_create_backup(self):
  self.write(self.material(),0o640);before=self.target.stat();raw=self.target.read_bytes()
  result=self.prepare();after=self.target.stat();self.assertEqual(result['status'],'preserved');self.assertEqual(raw,self.target.read_bytes());self.assertEqual((before.st_ino,before.st_mode,before.st_mtime_ns),(after.st_ino,after.st_mode,after.st_mtime_ns));self.assertFalse(self.backup.exists());self.assertFalse(self.labels)
 @POSIX
 def test_nonempty_invalid_and_unknown_empty_modes_never_change_or_backup(self):
  for value,mode in [(b'operator invalid key\n',0o600),(b'',0o600),(b'',0o666)]:
   self.write(value,mode);before=self.target.stat()
   with self.assertRaises(ValueError):self.prepare()
   self.assertEqual(self.target.read_bytes(),value);self.assertEqual(self.target.stat().st_ino,before.st_ino);self.assertFalse(self.backup.exists())
 @POSIX
 def test_check_mode_has_no_file_or_directory_mutations_and_missing_empty_refuses(self):
  with self.assertRaises(ValueError):self.prepare(check=True)
  self.assertFalse((self.root/'etc').exists());self.assertFalse(self.backup.exists())
  self.write(b'',0o664)
  with self.assertRaises(ValueError):self.prepare(check=True)
  self.assertFalse(self.backup.exists());self.assertEqual(self.target.read_bytes(),b'')
  self.write(self.material(),0o600);before=self.target.stat();result=self.prepare(check=True)
  self.assertEqual(result['status'],'valid');self.assertEqual((before.st_ino,before.st_mtime_ns),(self.target.stat().st_ino,self.target.stat().st_mtime_ns));self.assertFalse(self.backup.exists());self.assertFalse(self.labels)
 @POSIX
 def test_symlink_leaf_parent_and_backup_are_refused(self):
  other=self.base/'operator.pem';other.write_bytes(b'keep owner bytes');self.target.parent.mkdir(parents=True)
  self.target.symlink_to(other)
  with self.assertRaises(ValueError):self.prepare()
  self.assertEqual(other.read_bytes(),b'keep owner bytes');self.target.unlink()
  self.target.parent.rmdir();self.target.parent.symlink_to(self.base,target_is_directory=True)
  with self.assertRaises(ValueError):self.prepare()
  self.target.parent.unlink();self.target.parent.mkdir();self.backup.parent.mkdir(parents=True);self.backup.symlink_to(self.base,target_is_directory=True)
  with self.assertRaises(ValueError):self.prepare()
 @POSIX
 def test_generation_failure_leaves_empty_original_exact(self):
  self.write(b'',0o664);before=self.target.stat()
  with mock.patch.object(self.m,'generate_material',side_effect=ValueError('fixture generation failed')):
   with self.assertRaises(ValueError):self.prepare()
  self.assertEqual(self.target.read_bytes(),b'');self.assertEqual(self.target.stat().st_ino,before.st_ino)
 @POSIX
 def test_relabel_failure_rolls_back_only_created_inode_or_exact_empty_original(self):
  for empty in [False,True]:
   if self.target.exists():self.target.unlink()
   if empty:self.write(b'',0o664)
   def fail(_):raise OSError('fixture context failure')
   with self.assertRaises(OSError):self.prepare(relabel=fail)
   self.assertEqual(self.target.exists(),empty)
   if empty:self.assertEqual(self.target.read_bytes(),b'');self.assertEqual(stat.S_IMODE(self.target.stat().st_mode),0o664)
 @POSIX
 def test_owner_edit_during_generation_is_retained_and_never_overwritten(self):
  self.write(b'',0o664);original=self.m.generate_material
  def change(*a,**kw):
   material=original(*a,**kw);self.target.unlink();self.target.write_bytes(b'new owner bytes');return material
  with mock.patch.object(self.m,'generate_material',side_effect=change):
   with self.assertRaises(ValueError):self.prepare()
  self.assertEqual(self.target.read_bytes(),b'new owner bytes')
 @POSIX
 def test_relabel_owner_replacement_survives_rollback(self):
  def change(_):
   self.target.unlink();self.target.write_bytes(b'new owner material');raise OSError('fixture relabel failure')
  with self.assertRaises(OSError):self.prepare(relabel=change)
  self.assertEqual(self.target.read_bytes(),b'new owner material')
 def test_commands_use_bounded_timeout_closed_stdin_or_explicit_bytes_and_scrubbed_environment(self):
  value=self.material();real=self.m.subprocess.run;seen=[]
  def record(*a,**kw):seen.append((a,kw));return real(*a,**kw)
  with mock.patch.object(self.m.subprocess,'run',side_effect=record):self.m.validate_material(value,OPENSSL)
  self.assertTrue(seen)
  for _a,kw in seen:
   self.assertGreater(kw['timeout'],0);self.assertFalse(kw.get('shell',False));self.assertEqual(set(kw['env']),{'PATH','LC_ALL'});self.assertIsInstance(kw.get('input'),bytes)
 def test_command_failures_are_sanitized_and_cli_requires_root(self):
  for err in [OSError('private payload'),subprocess.TimeoutExpired('private command',30)]:
   with mock.patch.object(self.m.subprocess,'run',side_effect=err):
    with self.assertRaisesRegex(ValueError,'unavailable or timed out'):self.m.run_command(['fixture'])
  with mock.patch.object(self.m.os,'geteuid',return_value=1000,create=True):
   with self.assertRaises(SystemExit):self.m.main([])

if __name__=='__main__':unittest.main()
