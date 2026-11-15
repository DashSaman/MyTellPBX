#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare the separately authorized report-only update from private site sources."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[2]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def prepare(output,roots,source_id,checks,source=REPO):
    policy=load('asternic_prepare_policy',REPO/'scripts/ui/rollout.py')
    policy.outside_served(output,roots)
    if output.exists():raise ValueError('Use a new artifact directory')
    if not isinstance(source_id,str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',source_id):
        raise ValueError('An exact Git tree is required')
    if not isinstance(checks,list) or any(not isinstance(c,dict) or not isinstance(c.get('check'),str) or type(c.get('rc')) is not int for c in checks):
        raise ValueError('Malformed check records')
    names={c['check'] for c in checks}
    if len(names)!=len(checks) or not policy.ASTERNIC_CHECKS.issubset(names) or any(c['rc'] for c in checks):
        raise ValueError('Required checks did not pass')
    prefix='modules/asternic_cdr/'
    inputs=[]
    for name in ['module.xml','asternic_cdr.js','menu.php']:
        digest=policy.digest(policy.within(roots['admin'],prefix+name))
        if digest is None:raise ValueError('Missing native report guard: '+name)
        inputs.append({'root':'admin','path':prefix+name,'sha256':digest})
    try:metadata=ET.fromstring(policy.within(roots['admin'],prefix+'module.xml').read_text(encoding='utf-8'))
    except ET.ParseError:raise ValueError('Unsupported module version metadata') from None
    if metadata.findtext('rawname')!='asternic_cdr' or metadata.findtext('version')!='1.6.6':
        raise ValueError('Unsupported Asternic module version')
    source=Path(source);patch=load('asternic_direction_patch',source/'admin-fixes/patch-asternic-direction.py')
    helper=(source/'admin-fixes/asternic-direction.php').read_bytes()
    helper_path=policy.within(roots['admin'],prefix+'mytell-direction.php')
    if helper_path.exists() and policy.digest(helper_path)!=hashlib.sha256(helper).hexdigest():
        raise ValueError('Existing classifier helper differs; preserve it for reviewed maintenance')
    proposed={prefix+'mytell-direction.php':helper}
    for name,transform in [('page.asternic_cdr.php',patch.transform_page),('functions.inc.php',patch.transform_functions)]:
        path=policy.within(roots['admin'],prefix+name)
        proposed[prefix+name]=transform(path.read_text(encoding='utf-8')).encode('utf-8')
    records=[]
    for name,data in sorted(proposed.items()):
        target=policy.within(roots['admin'],name)
        if not target.parent.is_dir():raise ValueError('Report destination parent is missing')
        before=policy.digest(target);after=hashlib.sha256(data).hexdigest()
        if before==after:inputs.append({'root':'admin','path':name,'sha256':before});continue
        item={'root':'admin','path':name,'payload':'payload/admin/'+name,'before':before,'after':after,'size':len(data)}
        if not policy.allowed(item,policy.ASTERNIC_PROFILE):raise ValueError('Report candidate outside scoped policy')
        item['order']=policy.priority(item);records.append((item,data))
    if not records:raise ValueError('No report changes to prepare')
    manifest={'schema':1,'base':'/MytellDesk/','profile':policy.ASTERNIC_PROFILE,'source_id':source_id,
              'checks':checks,'files':[item for item,_ in records],'inputs':inputs}
    output.mkdir(parents=True)
    for item,data in records:
        path=output/item['payload'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    policy.validate(output,manifest,roots)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--roots',type=Path,required=True)
    parser.add_argument('--source-id',required=True);parser.add_argument('--checks',type=Path,required=True)
    args=parser.parse_args();roots={k:Path(v) for k,v in json.loads(args.roots.read_text()).items()}
    result=prepare(args.output,roots,args.source_id,json.loads(args.checks.read_text()))
    print('Prepared '+str(len(result['files']))+' report-only files; no installed path modified')
