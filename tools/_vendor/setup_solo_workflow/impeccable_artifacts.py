"""Bridge explicitly owned Impeccable runtime paths to an enrolled project run.

Native paths remain available until the owner finishes the task. Permanent design
context, legacy files, links and unresolved critiques are never collected.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import artifact_lifecycle as life

RUNTIME = {'mocks', 'prototypes', 'review', 'questions', 'critique'}

def context(project):
    project = life.safe(project)
    root = life.safe(project / '.artifacts/runs')
    config = life.configuration(root)
    if config.get('layout') != 'runs' or not Path(config['project']).samefile(project):
        raise ValueError('adapter requires this project enrolled with runs layout')
    return project, root

def scope(project, text):
    rel = Path(text)
    if rel.is_absolute() or '..' in rel.parts or len(rel.parts) < 2:
        raise ValueError('explicit relative Impeccable runtime path required')
    if rel.parts[0] != '.impeccable' or rel.parts[1] not in RUNTIME:
        raise ValueError('persistent context or unknown runtime path refused')
    if rel.name in {'.gitignore', 'ignore.md'}:
        raise ValueError('persistent marker cannot be an output scope')
    return life.safe(project / rel)

def marker(project, path):
    rel = path.relative_to(project).as_posix()
    return path.name == '.gitignore' or rel == '.impeccable/critique/ignore.md'

def inventory(project, paths):
    found = {}
    for text in paths:
        target = scope(project, text)
        items = []
        if target.is_file():
            items = [target]
        elif target.exists():
            for directory, dirs, files in os.walk(target, followlinks=False):
                for name in dirs:
                    life.safe(Path(directory) / name)
                items.extend(Path(directory) / name for name in files)
        for item in items:
            item = life.safe(item)
            if marker(project, item):
                continue
            if not item.is_file():
                raise ValueError('non-file output refused')
            key = item.relative_to(project).as_posix()
            found[key] = hashlib.sha256(item.read_bytes()).hexdigest()
    return found

def binding(root, name):
    record, files, state = life.load(root, name)
    path = life.safe(files / 'impeccable.json')
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('version') != 1 or value.get('group') != name:
        raise ValueError('invalid Impeccable binding')
    return record, files, state, path, value

def start(project, name, owner, paths):
    project, root = context(project)
    if not paths:
        raise ValueError('at least one output scope required')
    paths = [scope(project, p).relative_to(project).as_posix() for p in paths]
    targets = [scope(project, p) for p in paths]
    if any(a == b or a in b.parents or b in a.parents for i,a in enumerate(targets) for b in targets[i+1:]):
        raise ValueError('overlapping output scopes')
    if inventory(project, paths):
        raise ValueError('existing output requires its original owner; not adopted')
    files = Path(life.register(root, name, owner, 'Impeccable task outputs', workspace=project))
    try:
        with life.lock(root):
            for other in root.iterdir():
                if other == files or not other.is_dir() or not (other / 'impeccable.json').exists():
                    continue
                _, _, state, _, old = binding(root, other.name)
                if state['state'] != 'active':
                    continue
                for text in old['paths']:
                    candidate = scope(project, text)
                    if any(candidate == p or candidate in p.parents or p in candidate.parents for p in targets):
                        raise ValueError('output scope belongs to an active task')
            if inventory(project, paths):
                raise ValueError('output appeared during registration')
            life.atomic(files / 'impeccable.json', dict(version=1, group=name, project=str(project),
                        paths=paths, phase='active'))
    except Exception:
        life.hold(root, name, 'Impeccable output claim failed', 'Inspect the failed claim before releasing this run')
        raise
    return dict(group=name, output=str(files), paths=paths, state='active')

def execute(project, name, command, *, reading=False):
    project, root = context(project)
    if not command:
        raise ValueError('command required')
    with life.consume(root, name, writing=not reading):
        with life.lock(root):
            _, files, state, _, value = binding(root, name)
            if (not reading and value['phase'] != 'active') or state['hold']:
                raise ValueError('output is collecting or held')
            env = dict(os.environ, IMPECCABLE_ARTIFACT_RUN=str(files))
        return subprocess.run(command, cwd=project, env=env, check=False).returncode

def finish(project, name, *, confirmed=False, days=30):
    if not confirmed:
        raise ValueError('explicit end-of-use confirmation required')
    if days not in (30,60):
        raise ValueError('retention must be 30 or 60 days')
    project, root = context(project)
    with life.lock(root):
        record, files, state, path, value = binding(root, name)
        if state['state'] != 'active' or state['hold'] or life.consumption_state(state) != 'ended':
            raise ValueError('active/unknown consumer, hold or closed run prevents collection')
        if value['project'] != str(project):
            raise ValueError('project binding mismatch')
        current = inventory(project, value['paths'])
        if value['phase'] == 'active':
            for rel in current:
                if rel.startswith('.impeccable/critique/') and rel.endswith('.md'):
                    text = (project / rel).read_text(encoding='utf-8')
                    front = text.split('---',2)
                    if len(front) < 3 or front[0].strip() or not re.search(r'^closed:\s*true\s*$',front[1],re.M):
                        raise ValueError('unresolved critique prevents closure')
            value.update(phase='collecting', inventory=current)
            life.atomic(path, value)
        elif value['phase'] not in {'collecting', 'collected'}:
            raise ValueError('invalid collection phase')
        expected = value['inventory']
        if any(expected.get(k) != v for k,v in current.items()):
            raise ValueError('native output changed after collection began')
        # Validate every file and retry target before moving any of this pass.
        for rel,digest in expected.items():
            source = life.safe(project / rel)
            if not any(source == scope(project,p) or scope(project,p) in source.parents for p in value['paths']):
                raise ValueError('recorded output outside declared scopes')
            dest = life.safe(files / 'evidence' / rel)
            if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
                raise ValueError('collected evidence changed')
            if not source.exists() and not dest.exists():
                raise ValueError('output missing from both native and collected paths')
        for rel,digest in expected.items():
            source = life.safe(project / rel)
            dest = life.safe(files / 'evidence' / rel)
            if source.exists():
                if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                    raise ValueError('output changed during collection')
                if dest.exists():
                    raise ValueError('both native and collected copies exist; investigate')
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source,dest)
        if inventory(project,value['paths']):
            raise ValueError('new output appeared during collection')
        value['phase'] = 'collected'
        life.atomic(path,value)
        life.seal(record,files,state,life.stamp(),days)
    return dict(group=name,state='closed',files=len(expected),output=str(files/'evidence'))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    subs=parser.add_subparsers(dest='action',required=True)
    begin=subs.add_parser('start');begin.add_argument('--group',required=True);begin.add_argument('--owner',required=True);begin.add_argument('--path',action='append',required=True)
    run=subs.add_parser('exec');run.add_argument('--group',required=True);run.add_argument('--read',action='store_true');run.add_argument('command',nargs=argparse.REMAINDER)
    end=subs.add_parser('finish');end.add_argument('--group',required=True);end.add_argument('--confirmed',action='store_true');end.add_argument('--days',type=int,choices=[30,60],default=30)
    args=parser.parse_args(argv)
    if args.action=='start':
        result=start(args.project,args.group,args.owner,args.path)
    elif args.action=='exec':
        return execute(args.project,args.group,args.command[1:] if args.command[:1]==['--'] else args.command,reading=args.read)
    else:
        result=finish(args.project,args.group,confirmed=args.confirmed,days=args.days)
    print(json.dumps(result,ensure_ascii=False))
    return 0

if __name__=='__main__':
    try:
        sys.exit(main())
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False),file=sys.stderr)
        sys.exit(1)
