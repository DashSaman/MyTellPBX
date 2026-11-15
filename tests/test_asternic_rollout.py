# SPDX-License-Identifier: GPL-3.0-or-later
"""The separately authorized report fix never broadens PBX configuration writes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('asternic_rollout_policy',str(REPO/'scripts/ui/rollout.py'))
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
PROFILE='asternic-trunk-direction-v760'
REPORTS=['modules/asternic_cdr/'+n for n in ['page.asternic_cdr.php','functions.inc.php','mytell-direction.php']]
CHECKS=['offline-tests','php-syntax','cdr-direction','cdr-mariadb','cdr-readonly-preview']

class AsternicScopeTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);base=Path(temp.name)
        roots={name:base/name for name in policy.ROOTS};roots['admin'].mkdir()
        folder=roots['admin']/'modules/asternic_cdr';folder.mkdir(parents=True)
        (folder/'page.asternic_cdr.php').write_bytes(b'<?php // owner report')
        (folder/'functions.inc.php').write_bytes(b'<?php // owner functions')
        (folder/'other.php').write_bytes(b'preserve unrelated file')
        artifact=base/'artifact';records=[]
        for relative in REPORTS:
            target=roots['admin']/relative;payload='payload/admin/'+relative;p=artifact/payload;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'<?php // reviewed '+relative.encode())
            records.append({'root':'admin','path':relative,'payload':payload,'before':policy.digest(target),'after':policy.digest(p),'size':p.stat().st_size,'order':10 if relative.endswith('mytell-direction.php') else 30})
        manifest={'schema':1,'base':'/MytellDesk/','source_id':'a'*40,'profile':PROFILE,'checks':[{'check':c,'rc':0} for c in CHECKS],'files':records,'inputs':[]}
        (artifact/'manifest.json').write_text(json.dumps(manifest))
        review=base/'review.txt';review.write_text('Independent\nTREE '+manifest['source_id']+'\nREADY sha256:'+policy.digest(artifact/'manifest.json')+'\n')
        return base,roots,artifact,manifest,review,folder

    def test_only_three_report_sources_are_authorized(self):
        for name in REPORTS:
            with self.subTest(name=name):
                self.assertTrue(policy.allowed({'root':'admin','path':name},PROFILE))
                self.assertFalse(policy.allowed({'root':'admin','path':name},'panel-polish-desk-entry-v760'))

    def test_report_profile_rejects_configuration_other_reports_and_runtime_writes(self):
        for root,name in [('admin','functions.inc.php'),('admin','modules/core/functions.inc.php'),('admin','modules/sipsettings/functions.inc.php'),('admin','modules/asternic_cdr/menu.php'),('admin','modules/asternic_cdr/../core/functions.inc.php'),('admin','assets/mytel/workspace.js'),('legacy','modules/asternic_cdr/functions.inc.php'),('desk','dist/index.html'),('panel','js/theme.js')]:
            with self.subTest(root=root,name=name):self.assertFalse(policy.allowed({'root':root,'path':name},PROFILE))

    def test_helper_precedes_both_native_report_sources(self):
        helper={'root':'admin','path':REPORTS[-1]}
        for name in REPORTS[:2]:self.assertLess(policy.priority(helper),policy.priority({'root':'admin','path':name}))

    def test_preflight_requires_only_existing_admin_root_and_does_not_write(self):
        base,roots,artifact,manifest,_,folder=self.fixture()
        self.assertEqual(len(policy.validate(artifact,manifest,roots)),3)
        self.assertEqual((folder/'page.asternic_cdr.php').read_bytes(),b'<?php // owner report')
        self.assertFalse((base/'backup').exists())

    def test_missing_direction_sql_or_readonly_evidence_rejects_preflight(self):
        _,roots,artifact,manifest,_,_=self.fixture()
        for name in CHECKS:
            candidate=dict(manifest,checks=[x for x in manifest['checks'] if x['check']!=name])
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'checks'):policy.validate(artifact,candidate,roots)

    def test_scoped_apply_rollback_preserves_originals_and_removes_only_new_helper(self):
        base,roots,artifact,_,review,folder=self.fixture()
        policy.apply(artifact,roots,base/'backup',review)
        self.assertTrue((folder/'mytell-direction.php').is_file())
        policy.rollback(base/'backup',roots)
        self.assertFalse((folder/'mytell-direction.php').exists())
        self.assertEqual((folder/'page.asternic_cdr.php').read_bytes(),b'<?php // owner report')
        self.assertEqual((folder/'functions.inc.php').read_bytes(),b'<?php // owner functions')
        self.assertEqual((folder/'other.php').read_bytes(),b'preserve unrelated file')

if __name__=='__main__':unittest.main()
