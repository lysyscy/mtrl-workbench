"""Keep smyw task output in an enrolled project run without modifying smyw.

The current upstream build and feedback scripts are exercised with synthetic
inputs before each use. A changed but compatible upstream continues to work;
an incompatible contract leaves the existing run and its contents untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import artifact_lifecycle as life


def context(project):
    project = life.safe(project)
    root = life.safe(project / '.artifacts/runs')
    config = life.configuration(root)
    if config.get('layout') != 'runs' or not Path(config['project']).samefile(project):
        raise ValueError('smyw requires this project enrolled with runs layout')
    return project, root


def scripts(skill):
    # The Skills Manager deployment itself can be a link; it is read-only here.
    skill = Path(skill).resolve(strict=True)
    build = skill / 'scripts/build.mjs'
    feedback = skill / 'scripts/apply-feedback.mjs'
    if not (skill / 'SKILL.md').is_file() or not build.is_file() or not feedback.is_file():
        raise ValueError('installed smyw entry or scripts missing; review upstream compatibility')
    return build, feedback


def check_upstream(skill, node='node'):
    build, feedback = scripts(skill)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (build, feedback)}
    with tempfile.TemporaryDirectory(prefix='smyw-contract-') as temp:
        directory = Path(temp)
        spec = directory / 'spec.json'
        spec.write_text(json.dumps({'title': 'contract-check', 'version': 1,
                                    'stage': 'prototype', 'pages': [], 'flows': [],
                                    'backend': [], 'changes': [], 'questions': []}), encoding='utf-8')
        patch = {'format': 'smyw-patch@1', 'base': 1,
                 'ops': [{'op': 'top', 'set': {'title': 'contract-updated'}}]}
        notes = directory / 'feedback-v1.md'
        notes.write_text('```json\n' + json.dumps(patch) + '\n```\n', encoding='utf-8', newline='\n')
        commands = ([node, str(build), str(spec)],
                    [node, str(feedback), str(notes), str(spec), '--dry-run'],
                    [node, str(feedback), str(notes), str(spec)])
        for index, command in enumerate(commands):
            try:
                result = subprocess.run(command, cwd=directory, capture_output=True, timeout=30, check=False)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise ValueError('cannot verify installed smyw; review upstream compatibility') from error
            if result.returncode:
                detail = result.stderr.decode('utf-8', errors='replace').strip()[:1000]
                raise ValueError(f'installed smyw contract check failed; review upstream compatibility: {detail}')
            if index == 1:
                try:
                    dry_state = json.loads(spec.read_text(encoding='utf-8'))
                except (OSError, ValueError) as error:
                    raise ValueError('smyw dry-run changed the spec; review upstream compatibility') from error
                if (not isinstance(dry_state, dict) or dry_state.get('version') != 1 or
                        dry_state.get('title') != 'contract-check' or (directory / 'spec-v1.json').exists()):
                    raise ValueError('smyw dry-run changed the spec; review upstream compatibility')
        preview = directory / 'preview.html'
        backup = directory / 'spec-v1.json'
        try:
            updated = json.loads(spec.read_text(encoding='utf-8'))
            original = json.loads(backup.read_text(encoding='utf-8'))
            valid = ('contract-check' in preview.read_text(encoding='utf-8') and
                     original.get('version') == 1 and original.get('title') == 'contract-check' and
                     updated.get('version') == 2 and updated.get('title') == 'contract-updated')
        except (OSError, ValueError, AttributeError):
            valid = False
        if not valid:
            raise ValueError('installed smyw output or feedback contract changed; review upstream compatibility')
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (build, feedback)}
    if after != before:
        raise ValueError('installed smyw changed during compatibility check; retry after update')
    return after


def binding(root, group):
    _, files, state = life.load(root, group)
    metadata = life.safe(files / 'smyw.json')
    data = json.loads(metadata.read_text(encoding='utf-8'))
    if data.get('version') != 1 or data.get('group') != group or state.get('kind') != 'work':
        raise ValueError('invalid smyw run binding')
    directory = life.safe(files / 'work/smyw')
    return files, state, directory


def start(project, group, owner, skill, node='node'):
    project, root = context(project)
    hashes = check_upstream(skill, node)
    files = Path(life.register(root, group, owner, 'smyw preview and feedback', 'work', workspace=project))
    try:
        with life.lock(root):
            directory = life.safe(files / 'work/smyw')
            directory.mkdir(parents=True)
            life.atomic(files / 'smyw.json', {'version': 1, 'group': group, 'initial_script_sha256': hashes})
    except Exception:
        life.hold(root, group, 'smyw setup interrupted', 'Inspect the incomplete run before release')
        raise
    return {'group': group, 'state': 'active', 'directory': str(directory), 'spec': str(directory / 'spec.json')}


def invoke(project, group, skill, action, *, feedback=None, node='node', dry_run=False):
    project, root = context(project)
    with life.consume(root, group):
        _, state, directory = binding(root, group)
        if state['state'] != 'active' or state['hold']:
            raise ValueError('smyw run is not writable')
        verified = check_upstream(skill, node)
        build, apply_feedback = scripts(skill)
        if {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (build, apply_feedback)} != verified:
            raise ValueError('installed smyw changed after compatibility check; retry after update')
        spec = life.safe(directory / 'spec.json')
        if not spec.is_file():
            raise ValueError('smyw spec is missing')
        if action == 'build':
            command = [node, str(build), str(spec)]
        elif action == 'apply':
            rel = Path(feedback or '')
            if rel.is_absolute() or not rel.parts or '..' in rel.parts:
                raise ValueError('feedback must be inside this smyw run')
            source = life.safe(directory / rel)
            if not source.is_relative_to(directory) or not source.is_file():
                raise ValueError('feedback must be inside this smyw run')
            command = [node, str(apply_feedback), str(source), str(spec)]
            if dry_run:
                command.append('--dry-run')
        else:
            raise ValueError('unknown smyw action')
        return subprocess.run(command, cwd=directory, check=False).returncode


def execute(project, group, command):
    project, root = context(project)
    if not command:
        raise ValueError('command required')
    with life.consume(root, group):
        _, state, directory = binding(root, group)
        if state['state'] != 'active' or state['hold']:
            raise ValueError('smyw run is not writable')
        env = dict(os.environ, SMYW_ARTIFACT_DIR=str(directory))
        return subprocess.run(command, cwd=project, env=env, check=False).returncode


def finish(project, group, *, confirmed=False):
    if not confirmed:
        raise ValueError('explicit end-of-use confirmation required')
    _, root = context(project)
    binding(root, group)
    life.close(root, group)
    return {'group': group, 'state': 'closed', 'kind': 'work'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    subs = parser.add_subparsers(dest='action', required=True)
    begin = subs.add_parser('start')
    begin.add_argument('--group', required=True); begin.add_argument('--owner', required=True)
    begin.add_argument('--skill', type=Path, required=True); begin.add_argument('--node', default='node')
    for action in ('build', 'apply'):
        command = subs.add_parser(action)
        command.add_argument('--group', required=True); command.add_argument('--skill', type=Path, required=True)
        command.add_argument('--node', default='node')
        if action == 'apply':
            command.add_argument('--feedback', required=True); command.add_argument('--dry-run', action='store_true')
    run = subs.add_parser('exec'); run.add_argument('--group', required=True); run.add_argument('command', nargs=argparse.REMAINDER)
    end = subs.add_parser('finish'); end.add_argument('--group', required=True); end.add_argument('--confirmed', action='store_true')
    args = parser.parse_args(argv)
    if args.action == 'start':
        result = start(args.project, args.group, args.owner, args.skill, args.node)
    elif args.action in {'build', 'apply'}:
        return invoke(args.project, args.group, args.skill, args.action, feedback=getattr(args, 'feedback', None), node=args.node, dry_run=getattr(args, 'dry_run', False))
    elif args.action == 'exec':
        return execute(args.project, args.group, args.command[1:] if args.command[:1] == ['--'] else args.command)
    else:
        result = finish(args.project, args.group, confirmed=args.confirmed)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
