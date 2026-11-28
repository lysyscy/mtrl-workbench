"""Drive the document and closeout commands against disposable Git checkouts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[2]
CLI = REPO / 'tools/audit/doc_ops.py'
RUNTIME = 'tools/_vendor/setup_solo_workflow/artifact_lifecycle.py'
COMMIT = 'a' * 40


def command(root, *args, expected=0, stdin=None):
    result = subprocess.run(args, cwd=root, encoding='utf-8', capture_output=True, check=False, input=stdin)
    assert result.returncode == expected, (args, result.stdout, result.stderr)
    return result.stdout


def git(root, *args, expected=0, stdin=None):
    return command(root, 'git', *args, expected=expected, stdin=stdin).strip()


def doc(root, config_path, action, *args, expected=0):
    output = command(root, sys.executable, '-B', '-X', 'utf8', str(CLI), action,
                     '--config', str(config_path), '--root', str(root), *args, expected=expected)
    return json.loads(output)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8', newline='\n')
    return path


def put_json(path, value):
    return put(path, json.dumps(value, ensure_ascii=False))


def task(root, name, **changes):
    fields = dict(id=name, kind='story', status='pending', parent=None, children=[], blocked_by=[],
                  worktree=None, worktree_state=None, managed_runs=[], remaining_acceptance=['confirm result'],
                  next_step='inspect output', updated_at='2026-11-27T12:00:00+00:00')
    fields.update(changes)
    metadata = '\n'.join(f'{key}: {json.dumps(value, ensure_ascii=False)}' for key, value in fields.items())
    return put(root / f'work/{name}.md', f'---\n{metadata}\n---\n\n# Task {name}\n')


def receipt(root, run_id, action, commit, at, pid):
    put_json(root / f'proof/{run_id}/data/release.json', {
        'event': action, 'ok': True, 'revision': commit, 'listener': {'process': pid}, 'time': at,
    })


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / 'src'
    root.mkdir()
    git(root, 'init', '--initial-branch=trunk')
    config = {
        'schema_version': 1,
        'git': {'base': 'trunk', 'remote': 'archive', 'worktree_root': '../trees'},
        'entry': {
            'status_path': 'handbook/index.md', 'release_heading': '## Running now',
            'view_start': '<!-- Begin activity -->', 'view_end': '<!-- End activity -->',
            'active_heading': '## Activity', 'worktree_heading': '## Checkouts',
            'labels': {'status': 'State', 'acceptance': 'Accept', 'next': 'Next', 'none': 'None'},
            'release_limit': 2, 'utc_offset_minutes': -300,
            'release_history_note': 'Find earlier runs in Git history and local receipts.',
            'release_sources': [{'glob': 'proof/*/data/release.json', 'run_id_parent': 1}],
            'release_verified': {'ok': True},
            'release_fields': {'action': 'event', 'product_commit': 'revision',
                               'pid': 'listener.process', 'finished_at': 'time'},
            'release_actions': ['rollout', 'reload'],
        },
        'tasks': {'glob': 'work/*.md', 'id_pattern': '[a-z]+-[a-z]+', 'kinds': ['story'],
                  'statuses': ['pending', 'finished'], 'finished_states': ['finished']},
        'closeout': {'worktrees': []},
    }
    config_path = put_json(tmp_path / 'settings.json', config)
    put(root / '.gitignore', '/proof/\n/runtime/\n/outputs/\n')
    status = put(root / 'handbook/index.md', '# Dashboard\n\n## Running now\n\n'
                 '<!-- Begin activity -->\n\n<!-- End activity -->\n')
    receipt(root, 'old', 'rollout', COMMIT, '2026-11-26T12:00:00+00:00', 421)
    receipt(root, 'new', 'reload', COMMIT, '2026-11-26T12:30:00+00:00', 475)
    git(root, 'add', '--', '.gitignore', 'handbook/index.md')
    return root, config_path, config, status


def test_generic_engine_has_no_project_identifiers():
    files = [CLI, *(CLI.parent / 'doc_ops').glob('*.py')]
    for path in files:
        text = path.read_text(encoding='utf-8').casefold()
        for token in ('mtrl', 'tail-', 'frontend-release', 'notice-fetch', 'docs/status.md', '设备', '前端打磨'):
            assert token not in text, (path.name, token)


def test_links_distinguish_untracked_from_missing_and_ignore_code_and_external_links(checkout):
    root, config_path, _, status = checkout
    put(root / 'handbook/notes/已登记.md', '# Tracked\n')
    put(root / 'handbook/notes/file (one).md', '# Spaces\n')
    put(root / 'handbook/draft.md', '# Local only\n')
    git(root, 'add', '--', 'handbook/notes')
    put(status, r"""# Dashboard

[Windows path](notes\已登记.md)
[Encoded filename](notes/file%20%28one%29.md#spaces)
[Hosted](https://example.com/some/file)
[Same document](#dashboard)
Examples like `[inline](inline-example.md)` and <!-- [comment](comment.md) --> stay literal.

```text
[Sample](fenced-example.md)
```

[draft](draft.md)
[missing](missing.md)
See [reference][note].

[note]: <notes/file (one).md>
""")
    result = doc(root, config_path, 'links', expected=1)
    assert result['local_links_examined'] == 5
    assert [(item['code'], item['target']) for item in result['diagnostics']] == [
        ('LINK_UNTRACKED_TARGET', 'handbook/draft.md'),
        ('LINK_MISSING_TARGET', 'handbook/missing.md'),
    ]


def test_task_schema_parent_backlinks_and_retired_worktree_consistency(checkout):
    root, config_path, config, _ = checkout
    task(root, 'top-task', children=['wrong-child'])
    task(root, 'child-task', parent='top-task', worktree='retired-tree', worktree_state='in-use')
    task(root, 'invalid-task', remaining_acceptance='requires an array')
    git(root, 'add', '--', 'work')
    config['closeout']['worktrees'].append(
        {'id': 'retired-tree', 'state': 'retired', 'label': 'Old checkout', 'reason': 'Already ended'},
    )
    put_json(config_path, config)
    result = doc(root, config_path, 'check', expected=1)
    assert {item['code'] for item in result['diagnostics']} == {
        'TASK_SCHEMA_INVALID', 'TASK_PARENT_BACKLINK', 'TASK_CHILD_BACKLINK', 'TASK_RETIRED_WORKTREE',
    }

    task(root, 'top-task', children=['child-task'])
    task(root, 'child-task', parent='top-task', worktree_state='retired')
    task(root, 'invalid-task')
    assert doc(root, config_path, 'refresh')['task_count'] == 3
    assert doc(root, config_path, 'check')['diagnostics'] == []


def test_refresh_rebuilds_release_and_active_view_and_check_detects_drift(checkout):
    root, config_path, _, status = checkout
    task(root, 'open-task')
    task(root, 'done-task', status='finished')
    git(root, 'add', '--', 'work')
    assert doc(root, config_path, 'refresh')['changed']
    text = status.read_text(encoding='utf-8')
    assert '| 2026-11-26T07:30:00-05:00 | `new` | `reload`' in text
    assert text.index('`new`') < text.index('`old`')
    assert '[Task open-task](../work/open-task.md)' in text
    assert 'done-task' not in text
    assert not doc(root, config_path, 'refresh')['changed']
    assert not doc(root, config_path, 'check')['changed']

    task(root, 'open-task', next_step='new next step')
    put(status, text.replace('| 475 |', '| 999 |'))
    drift = doc(root, config_path, 'check', expected=1)
    assert {item['code'] for item in drift['diagnostics']} == {'ACTIVE_VIEW_DRIFT', 'RELEASE_SECTION_DRIFT'}
    assert '| 999 |' in status.read_text(encoding='utf-8')
    assert doc(root, config_path, 'refresh')['changed']
    assert not doc(root, config_path, 'check')['diagnostics']


def test_closeout_rechecks_plan_and_finalizers_and_converges(checkout, tmp_path):
    root, config_path, config, _ = checkout
    tree = git(root, 'write-tree')
    base = git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
               'commit-tree', tree, '-m', 'Disposable closeout fixture')
    git(root, 'update-ref', 'refs/heads/trunk', base)
    bare = tmp_path / 'archive.git'
    git(root, 'clone', '--bare', '--no-hardlinks', str(root), str(bare))
    git(root, 'remote', 'add', 'archive', str(bare))
    receipt(root, 'saved-job', 'rollout', base, '2026-11-25T12:00:00+00:00', 550)
    handoff = put(root / 'outputs/old.md', '# Superseded handoff\n')
    unknown = put(root / 'outputs/releases/unknown/value.txt', 'unknown')
    current = put(root / f'outputs/releases/{COMMIT[:12]}/bundle.txt', 'current')
    rollback = put(root / 'outputs/releases/rollback/bundle.txt', 'rollback')
    put_json(root / 'outputs/retention.json', {'version': 1, 'previous': str(rollback.parent),
                                             'enrolled': {current.parent.name: 'sample', 'rollback': 'sample'}})

    run_root = root / 'runtime'
    runtime_cli = [sys.executable, '-B', '-X', 'utf8', str(REPO / RUNTIME)]
    command(root, *runtime_cli, 'enroll', '--root', str(run_root), '--project', str(root))
    for name, kind in [('temporary-run', 'work'), ('rejected-run', 'evidence'), ('protected-run', 'evidence')]:
        command(root, *runtime_cli, 'register', '--root', str(run_root), '--group', name, '--kind', kind,
                '--owner', 'fixture', '--reason', 'Exercise the real lifecycle runtime')
        put(run_root / name / 'notes.txt', name)
    protected = put(root / 'outputs/keep.txt', 'other local material')

    specs, paths = [], {}
    for name, state in [('finished-tree', 'settled'), ('blocked-tree', 'running')]:
        path = tmp_path / 'trees' / name
        git(root, 'worktree', 'add', '-b', name, str(path), 'trunk')
        git(bare, 'update-ref', f'refs/heads/{name}', base)
        git(root, 'update-ref', f'refs/remotes/archive/{name}', base)
        paths[name] = path
        specs.append({
            'id': name, 'branch': name, 'head': base, 'state': 'retiring', 'label': name,
            'reason': 'Disposable closeout fixture', 'consumers_checked': True,
            'thread_bindings': [{'id': name + '-owner', 'state': state}],
        })
    specs[1]['runs'] = [{'id': 'protected-run', 'location': 'primary'}]
    config['closeout'].update(
        worktrees=specs,
        handoffs=[{'path': 'outputs/old.md', 'sha256': hashlib.sha256(handoff.read_bytes()).hexdigest(),
                   'saved_commit': base, 'run_id': 'saved-job', 'action': 'rollout', 'reason': 'Saved and released'}],
        runs={'runtime': RUNTIME, 'root': 'runtime', 'retention_days': 30,
              'release': [{'id': name, 'kind': kind, 'owner': 'fixture', 'released_on': '2026-01-01',
                           'reason': 'Approved release'} for name, kind in
                          [('temporary-run', 'work'), ('rejected-run', 'evidence')]]},
        retention={'path': 'outputs/retention.json', 'directories': 'outputs/releases',
                   'registry_field': 'enrolled', 'rollback_field': 'previous', 'schema_version': 1,
                   'dir_pattern': '[a-z]+', 'revision_prefix_length': 12},
    )
    put_json(config_path, config)
    plan_path = tmp_path / 'plan.json'
    plan = doc(root, config_path, 'closeout-plan', '--out', str(plan_path))
    assert plan == json.loads(plan_path.read_text(encoding='utf-8'))
    assert [(item['kind'], item['id']) for item in plan['actions']] == [
        ('retire_worktree', 'finished-tree'), ('remove_stale_handoff', 'outputs/old.md'),
        ('close_run', 'rejected-run'), ('close_run', 'temporary-run'),
    ]
    assert plan['actions'][2]['arguments'] == ['close', '--group', 'rejected-run', '--days', '30']
    assert plan['actions'][3]['arguments'] == ['close', '--group', 'temporary-run', '--discard-work']
    assert plan['blocked'][0]['id'] == 'blocked-tree'
    assert {item['code'] for item in plan['blocked'][0]['finalizers']} == {'THREAD_UNSETTLED', 'MANAGED_RUN_RETAINED'}
    assert plan['worktrees'][1]['diff_vs_remote_base'] == {'ahead': 0, 'behind': 0}
    assert [(item['id'], item['reason']) for item in plan['review']] == [('unknown', 'unknown-ownership')]
    assert handoff.exists() and paths['finished-tree'].exists()

    config['closeout']['preview_registries'] = ['runtime/previews/*.json']
    put_json(config_path, config)
    registration = put_json(root / 'runtime/previews/slot.json', {
        'source_root': str(paths['finished-tree']),
        'owner_path': str(root / 'runtime/preview-receipt.json'),
    })
    with_preview = doc(root, config_path, 'closeout-plan')
    assert 'finished-tree' not in {item['id'] for item in with_preview['actions']}
    assert next(item for item in with_preview['blocked'] if item['id'] == 'finished-tree')['finalizers'] == [
        {'code': 'WORKTREE_PREVIEW_REGISTERED', 'record': str(registration)},
    ]
    receipt_path = put_json(root / 'runtime/preview-receipt.json', {'source_root': str(paths['finished-tree'])})
    put_json(registration, {'owner_path': str(receipt_path)})
    assert doc(root, config_path, 'closeout-plan') == with_preview

    receipt_path.unlink()
    unresolved = doc(root, config_path, 'closeout-plan')
    assert 'finished-tree' not in {item['id'] for item in unresolved['actions']}
    assert next(item for item in unresolved['blocked'] if item['id'] == 'finished-tree')['finalizers'] == [
        {'code': 'WORKTREE_PREVIEW_SOURCE_UNCONFIRMED', 'record': str(registration)},
    ]
    registration.unlink()
    del config['closeout']['preview_registries']
    put_json(config_path, config)

    note = run_root / 'temporary-run/notes.txt'
    put(note, 'changed after approval')
    refused = doc(root, config_path, 'closeout-apply', '--plan', str(plan_path), expected=1)
    assert refused['diagnostics'] == [{'code': 'PLAN_STALE'}]
    assert refused['applied'] == [] and handoff.exists() and paths['finished-tree'].exists() and note.exists()

    approved = tmp_path / 'rechecked.json'
    doc(root, config_path, 'closeout-plan', '--out', str(approved))
    result = doc(root, config_path, 'closeout-apply', '--plan', str(approved))
    assert len(result['applied']) == 4
    assert not handoff.exists() and not paths['finished-tree'].exists()
    assert 'finished-tree' not in git(root, 'worktree', 'list', '--porcelain')
    assert git(root, 'for-each-ref', '--format=%(refname)', 'refs/heads/finished-tree',
               'refs/remotes/archive/finished-tree') == ''
    assert git(bare, 'for-each-ref', '--format=%(refname)', 'refs/heads/finished-tree') == ''
    assert paths['blocked-tree'].exists() and git(bare, 'rev-parse', 'refs/heads/blocked-tree') == base
    assert current.exists() and rollback.exists() and unknown.exists() and protected.exists()
    work = json.loads((run_root / 'temporary-run/run.json').read_text(encoding='utf-8'))
    evidence = json.loads((run_root / 'rejected-run/run.json').read_text(encoding='utf-8'))
    assert work['state'] == 'deleted' and not note.exists()
    assert evidence['state'] == 'closed' and evidence['days'] == 30
    assert (run_root / 'rejected-run/notes.txt').read_text(encoding='utf-8') == 'rejected-run'

    second = doc(root, config_path, 'closeout-plan')
    assert second['actions'] == []
    assert [item['id'] for item in second['blocked']] == ['blocked-tree']
