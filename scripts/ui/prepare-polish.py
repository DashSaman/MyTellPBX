#!/usr/bin/env python3
"""Prepare a scoped presentation/Desk-entry artifact from private live snapshots."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def prepare(output,roots,source_id,checks,source=REPO):
    policy=load('polish_prepare_policy',REPO/'scripts/ui/rollout.py')
    policy.outside_served(output,roots)
    if output.exists():raise ValueError('Use a new artifact directory')
    if not isinstance(source_id,str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',source_id):
        raise ValueError('An exact Git tree is required')
    if not isinstance(checks,list) or any(not isinstance(c,dict) or not isinstance(c.get('check'),str) or type(c.get('rc')) is not int for c in checks):
        raise ValueError('Malformed check records')
    names={c['check'] for c in checks}
    if len(names)!=len(checks) or not policy.POLISH_CHECKS.issubset(names) or any(c['rc'] for c in checks):
        raise ValueError('Required checks did not pass')
    source=Path(source)
    proposed={('panel',name):(source/'theme'/name).read_bytes() for name in sorted(policy.POLISH_PANEL)}
    patch=load('polish_header_patch',source/'admin-theme/patch-admin-theme.py')
    header=policy.within(roots['admin'],'views/header.php')
    proposed[('admin','views/header.php')]=patch.transform_header(header.read_text(encoding='utf-8')).encode('utf-8')
    for name in ['workspace.css','workspace.js']:
        proposed[('admin','assets/mytel/'+name)]=(source/'admin-theme'/name).read_bytes()
    for name in ['index.php','launcher-access.php']:
        proposed[('legacy','modules/mytellpbxopdesk/'+name)]=(source/'modules/mytellpbxopdesk'/name).read_bytes()
    # These native dependencies stay read-only. They must be present before any
    # artifact output is created, and their hashes participate in rollout guards.
    inputs=[]
    for name in ['assets/js/pbxlib.js','libraries/ampuser.class.php','assets/mytel/apply.js',
                 'assets/mytel/feedback.js','assets/mytel/save.js','assets/mytel/apply.css']:
        digest=policy.digest(policy.within(roots['admin'],name))
        if digest is None:raise ValueError('Missing native dependency guard: '+name)
        inputs.append({'root':'admin','path':name,'sha256':digest})
    records=[]
    for (root,name),data in sorted(proposed.items()):
        if not policy.allowed({'root':root,'path':name},policy.POLISH_PROFILE):
            raise ValueError('Candidate is outside polish scope')
        target=policy.within(roots[root],name)
        if not target.parent.is_dir():raise ValueError('Destination parent does not exist: '+name)
        before=policy.digest(target);after=hashlib.sha256(data).hexdigest()
        if before==after:
            inputs.append({'root':root,'path':name,'sha256':before});continue
        item={'root':root,'path':name,'payload':'payload/'+root+'/'+name,
              'before':before,'after':after,'size':len(data)}
        item['order']=policy.priority(item);records.append((item,data))
    if not records:raise ValueError('No presentation or entry changes to prepare')
    manifest={'schema':1,'base':'/MytellDesk/','profile':policy.POLISH_PROFILE,
              'source_id':source_id,'checks':checks,'files':[item for item,_ in records],'inputs':inputs}
    output.mkdir(parents=True)
    for item,data in records:
        destination=output/item['payload'];destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
    policy.validate(output,manifest,roots)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--roots',type=Path,required=True)
    parser.add_argument('--source-id',required=True)
    parser.add_argument('--checks',type=Path,required=True)
    args=parser.parse_args()
    roots={name:Path(value) for name,value in json.loads(args.roots.read_text()).items()}
    result=prepare(args.output,roots,args.source_id,json.loads(args.checks.read_text()))
    print('Prepared '+str(len(result['files']))+' scoped files; no installed paths modified')
