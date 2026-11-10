#!/usr/bin/env python3
"""Prepare only the eight Submit/Apply/SIP-save paths from current snapshots."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, str(REPO / relative))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(output, roots, source_id, checks):
    policy = load('submit_policy', 'scripts/ui/rollout.py')
    theme = load('submit_theme', 'admin-theme/patch-admin-theme.py')
    policy.outside_served(output, roots)
    if output.exists():
        raise ValueError('Use a new artifact directory')
    admin = roots['admin']
    proposed = load('submit_patch', 'admin-fixes/patch-submit.py').plan(admin)
    header = admin / 'views/header.php'
    proposed[header] = theme.transform_header(header.read_text(encoding='utf-8'))
    for name in ('feedback.js', 'save.js', 'apply.js', 'apply.css'):
        proposed[admin/'assets/mytel'/name] = (REPO/'admin-theme'/name).read_text(encoding='utf-8')
    manifest = {'schema':1, 'base':'/MytellDesk/', 'profile':policy.SUBMIT_PROFILE,
                'source_id':source_id, 'checks':checks, 'files':[], 'inputs':[]}
    output.mkdir(parents=True)
    for target, text in sorted(proposed.items()):
        data = text.encode('utf-8'); relative = target.relative_to(admin).as_posix()
        before = policy.digest(target); after = hashlib.sha256(data).hexdigest()
        if before == after:
            manifest['inputs'].append({'root':'admin','path':relative,'sha256':before})
            continue
        payload = 'payload/admin/'+relative
        dest = output/payload; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
        item = {'root':'admin','path':relative,'payload':payload,'before':before,'after':after,'size':len(data)}
        item['order'] = policy.priority(item); manifest['files'].append(item)
    for relative in ('assets/js/pbxlib.js','assets/js/unpoly.min.js','libraries/ampuser.class.php','functions.inc.php',
                     'libraries/mytell-apply.php','libraries/view.functions.php',
                     'modules/sipsettings/assets/js/sipsettings.js'):
        digest = policy.digest(admin/relative)
        if digest is None: raise ValueError('Missing installed dependency: '+relative)
        manifest['inputs'].append({'root':'admin','path':relative,'sha256':digest})
    policy.validate(output,manifest,roots)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--roots',type=Path,required=True)
    parser.add_argument('--source-id',required=True)
    parser.add_argument('--checks',type=Path,required=True)
    args=parser.parse_args()
    roots={k:Path(v) for k,v in json.loads(args.roots.read_text()).items()}
    manifest=prepare(args.output,roots,args.source_id,json.loads(args.checks.read_text()))
    print('Prepared',len(manifest['files']),'lifecycle paths; no live write')
