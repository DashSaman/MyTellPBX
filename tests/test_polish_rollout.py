"""7.6 deployment remains a UI-only, reviewed and reversible operation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('polish_policy_test',str(REPO/'scripts/ui/rollout.py'))
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
PROFILE='panel-polish-desk-entry-v760'


class PolishScopeTests(unittest.TestCase):
    def test_reviewed_presentation_and_acl_entry_paths_are_supported(self):
        for root,name in [('panel','css/mt-calendar.css'),('panel','_common/index.tpl'),
                          ('admin','assets/mytel/workspace.css'),('admin','views/header.php'),
                          ('legacy','modules/mytellpbxopdesk/index.php')]:
            with self.subTest(root=root,name=name):
                self.assertTrue(policy.allowed({'root':root,'path':name},PROFILE))

    def test_profile_does_not_broaden_telephony_or_immutable_desk_permissions(self):
        for root,name in [('admin','functions.inc.php'),('admin','libraries/mytell-apply.php'),
                          ('admin','modules/core/functions.inc.php'),('legacy','modules/calendar/index.php'),
                          ('legacy','index.php'),('legacy','modules/mytellpbxopdesk/credentials.php'),
                          ('desk','dist/index.html'),('desk','src/main.tsx'),('phone','index.html'),
                          ('panel','../config.php')]:
            with self.subTest(root=root,name=name):
                self.assertFalse(policy.allowed({'root':root,'path':name},PROFILE))

    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);base=Path(temp.name)
        roots={name:base/name for name in policy.ROOTS}
        for root in roots.values():root.mkdir()
        relative='modules/mytellpbxopdesk/index.php';target=roots['legacy']/relative
        target.parent.mkdir(parents=True);target.write_bytes(b'old ACL entry')
        artifact=base/'artifact';payload='payload/legacy/'+relative
        p=artifact/payload;p.parent.mkdir(parents=True);p.write_bytes(b'new ACL entry')
        entry={'root':'legacy','path':relative,'payload':payload,'before':policy.digest(target),
               'after':policy.digest(p),'size':p.stat().st_size,'order':30}
        checks=['offline-tests','js-syntax','php-syntax','polish-browser','entry-auth','apply-browser','calendar-tests']
        manifest={'schema':1,'base':'/MytellDesk/','source_id':'a'*40,'profile':PROFILE,
                  'checks':[{'check':c,'rc':0} for c in checks],'files':[entry],'inputs':[]}
        (artifact/'manifest.json').write_text(json.dumps(manifest))
        review=base/'review.txt';review.write_text('Independent reviewer\nTREE '+manifest['source_id']+'\nREADY sha256:'+policy.digest(artifact/'manifest.json')+'\n')
        return base,roots,artifact,manifest,review,target

    def test_new_profile_preflight_has_no_side_effects(self):
        base,roots,artifact,manifest,_,target=self.fixture()
        plan=policy.validate(artifact,manifest,roots)
        self.assertEqual(len(plan),1)
        self.assertEqual(target.read_bytes(),b'old ACL entry')
        self.assertFalse((base/'backup').exists())

    def test_new_entry_roundtrip_keeps_original_and_unrelated_owner_data(self):
        base,roots,artifact,manifest,review,target=self.fixture()
        unrelated=target.with_name('operator-note.txt');unrelated.write_bytes(b'keep owner data')
        policy.apply(artifact,roots,base/'backup',review)
        self.assertEqual(target.read_bytes(),b'new ACL entry')
        policy.rollback(base/'backup',roots)
        self.assertEqual(target.read_bytes(),b'old ACL entry')
        self.assertEqual(unrelated.read_bytes(),b'keep owner data')

    def test_entry_and_visual_evidence_cannot_be_omitted(self):
        _,roots,artifact,manifest,_,_=self.fixture()
        for name in ['entry-auth','polish-browser','apply-browser']:
            candidate=dict(manifest,checks=[r for r in manifest['checks'] if r['check']!=name])
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'checks'):
                policy.validate(artifact,candidate,roots)


if __name__=='__main__':unittest.main()
