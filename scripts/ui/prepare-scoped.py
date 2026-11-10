#!/usr/bin/env python3
"""Build the Apply/calendar artifact from installed snapshots, never live-write.

Checks are recorded by the test runner; an independent reviewer must verify
their evidence and bind READY to the resulting manifest before rollout.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = ('_common/index.tpl', 'css/workspace.css', 'js/workspace.js', 'js/theme.js', 'css/mt-secadv.css',
         'css/mt-calendar.css', 'js/mt-calendar.js', 'js/calendar-core.js', 'js/calendar-editor.js')


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, str(REPO / relative))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(output, roots, source_id, checks):
    policy = load('scoped_policy', 'scripts/ui/rollout.py')
    policy.outside_served(output, roots)
    if output.exists():
        raise ValueError('Use a new artifact directory')
    proposed = {}
    for patch in ('admin-theme/patch-admin-theme.py', 'admin-fixes/patch-apply-backend.py'):
        for path, text in load(patch, patch).plan(roots['admin']).items():
            proposed[('admin', path.relative_to(roots['admin']).as_posix())] = text.encode('utf-8')
    calendar = load('calendar', 'admin-fixes/patch-calendar.py')
    for path, text in calendar.plan(roots['legacy'] / 'modules/calendar', roots['legacy'] / 'modules/calendar/scenarios/rest/CalendarEvent.class.php').items():
        proposed[('legacy', path.relative_to(roots['legacy']).as_posix())] = text.encode('utf-8')
    for relative in PANEL:
        proposed[('panel', relative)] = (REPO / 'theme' / relative).read_bytes()
    manifest = {'schema':1, 'base':'/MytellDesk/', 'profile':policy.SCOPED_PROFILE,
                'source_id':source_id, 'checks':checks, 'files':[], 'inputs':[]}
    output.mkdir(parents=True)
    for (root, relative), data in sorted(proposed.items()):
        target = policy.within(roots[root], relative)
        before = policy.digest(target)
        after = hashlib.sha256(data).hexdigest()
        if before == after:
            manifest['inputs'].append({'root':root,'path':relative,'sha256':before})
            continue
        payload = 'payload/' + root + '/' + relative
        destination = output / payload
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        item = {'root':root,'path':relative,'payload':payload,'before':before,'after':after,'size':len(data)}
        item['order'] = policy.priority(item)
        manifest['files'].append(item)
    guards = [('panel', 'css/tokens.css'), ('panel','css/theme-dark.css'), ('panel','js/mt-secadv.js'),
              ('admin','assets/js/pbxlib.js'), ('admin','libraries/ampuser.class.php')]
    guards += [('legacy','modules/calendar/'+relative) for relative in
               ('libs/core.class.php','libs/paloSantoCalendar.class.php','themes/default/calendar_event_dialog.tpl',
                'themes/default/js/fullcalendar.js','themes/default/js/bootstrap-datetimepicker.min.js')]
    for root, relative in guards:
        digest = policy.digest(policy.within(roots[root],relative))
        if digest is None:
            raise ValueError('Missing runtime guard: ' + relative)
        manifest['inputs'].append({'root':root,'path':relative,'sha256':digest})
    policy.validate(output, manifest, roots)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--roots',type=Path,required=True)
    parser.add_argument('--source-id',required=True)
    parser.add_argument('--checks',type=Path,required=True)
    args=parser.parse_args()
    roots={k:Path(v) for k,v in json.loads(args.roots.read_text()).items()}
    manifest=prepare(args.output,roots,args.source_id,json.loads(args.checks.read_text()))
    print('Prepared',len(manifest['files']),'scoped files; no installed paths modified')
