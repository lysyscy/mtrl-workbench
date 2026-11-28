"""Plan closeout from declared ownership and revalidate each operation before use."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys

from .links import referrers
from .releases import COMMIT_PATTERN, receipts, timestamp, value_at
from .repo import git, json_text, read_json, relative_path, safe_path, tracked_paths
from .tasks import load_tasks, tree_specs


@dataclass(frozen=True)
class GitState:
    base_ref: str
    remote: str
    local_refs: dict[str, str]
    remote_refs: dict[str, str]
    remote_error: str | None
    bare_remote: Path | None
    endpoint_hash: str | None

    @property
    def local_base(self):
        return self.local_refs.get(self.base_ref)

    @property
    def remote_base(self):
        return self.remote_refs.get(self.base_ref)


def git_state(root: Path, settings: dict, trees: dict[str, dict]) -> GitState:
    base_ref = f'refs/heads/{settings["base"]}'
    branches = {base_ref}
    branches.update(f'refs/heads/{tree["branch"]}' for tree in trees.values() if tree.get('branch'))
    for ref in branches:
        git(root, 'check-ref-format', ref)
    remote = settings['remote']
    if not re.fullmatch(r'[\w.-]+', remote) or remote.startswith('-'):
        raise ValueError('invalid remote name')
    tracked = {ref.replace('refs/heads/', f'refs/remotes/{remote}/', 1) for ref in branches}
    local_refs = {}
    for line in git(root, 'for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads',
                    f'refs/remotes/{remote}').stdout.splitlines():
        ref, head = line.split()
        if ref in branches or ref in tracked:
            local_refs[ref] = head
    bare_remote, endpoint_hash = None, None
    try:
        # A tracking ref can be stale. Query the configured endpoint without fetching.
        fetch = git(root, 'remote', 'get-url', '--all', remote).stdout.splitlines()
        push = git(root, 'remote', 'get-url', '--push', '--all', remote).stdout.splitlines()
        if len(fetch) != 1 or fetch != push:
            raise ValueError('closeout needs one matching remote fetch and push endpoint')
        endpoint_hash = sha256(fetch[0].encode())
        advertised = git(root, 'ls-remote', '--refs', '--', remote, *sorted(branches)).stdout
        remote_refs = {ref: head for head, ref in (line.split('\t') for line in advertised.splitlines())}
        error = None if base_ref in remote_refs else 'remote base ref absent'
        local_endpoint = Path(fetch[0])
        if local_endpoint.is_absolute() and local_endpoint.is_dir():
            endpoint = local_endpoint.resolve()
            if git(endpoint, 'rev-parse', '--is-bare-repository').stdout.strip() == 'true':
                bare_remote = endpoint
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        remote_refs, error = {}, str(exc)
    return GitState(base_ref, remote, local_refs, remote_refs, error, bare_remote, endpoint_hash)


def included(root: Path, head: str | None, state: GitState) -> bool:
    return bool(head and re.fullmatch(COMMIT_PATTERN, head) and all(
        base and git(root, 'merge-base', '--is-ancestor', head, base, allowed=(0, 1, 128)).returncode == 0
        for base in (state.local_base, state.remote_base)
    ))


def registered_trees(root: Path) -> dict[Path, dict]:
    result = {}
    for block in git(root, 'worktree', 'list', '--porcelain', '-z').stdout.split('\0\0'):
        record = dict(field.partition(' ')[::2] for field in block.split('\0') if field)
        if record:
            result[Path(record['worktree'])] = record
    return result


def tree_inventory(path: Path) -> dict:
    args = ('-c', 'core.longpaths=true')
    changes = git(path, *args, 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--no-renames').stdout
    ignored = git(path, *args, 'ls-files', '--others', '--ignored', '--exclude-standard', '--directory', '-z').stdout
    flags = git(path, *args, 'ls-files', '-v', '-z').stdout.split('\0')
    return {'changes': changes.count('\0'), 'ignored': ignored.count('\0'),
            'hidden_flags': sum(flag[:1].islower() or flag.startswith('S ') for flag in flags)}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RunRecords:
    """Use the shipped lifecycle implementation and verify its enrolled project root."""

    def __init__(self, settings: dict):
        self.settings = settings
        tool_root = Path(__file__).resolve().parents[3]
        self.script = relative_path(tool_root, settings['runtime'])
        spec = importlib.util.spec_from_file_location('_doc_ops_lifecycle', self.script)
        self.runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runtime)

    def open(self, project: Path, run_id: str):
        root = relative_path(project, self.settings['root'])
        enrollment = self.runtime.configuration(root)
        if enrollment.get('layout') != 'runs' or not Path(enrollment['project']).samefile(project):
            raise ValueError('lifecycle area belongs to a different project')
        return self.runtime.load(root, run_id)

    def retention(self, project: Path, run_id: str, now: datetime) -> dict | None:
        try:
            receipt, _, value = self.open(project, run_id)
            state = value['state']
            expiry = value.get('expires_at')
            protected = (value.get('hold') or self.runtime.consumption_state(value) != 'ended'
                         or state in {'active', 'deleting'}
                         or (state == 'closed' and (expiry is None or timestamp(expiry) > now)))
            if not protected:
                return None
            return {'code': 'MANAGED_RUN_RETAINED', 'run_id': run_id, 'state': state,
                    'expires_at': expiry, 'record': str(receipt)}
        except (KeyError, OSError, TypeError, ValueError):
            return {'code': 'MANAGED_RUN_UNCONFIRMED', 'run_id': run_id, 'project': str(project)}

    def close_action(self, root: Path, candidate: dict, now: datetime) -> tuple[dict | None, dict]:
        run_id = candidate['id']
        report = {'id': run_id}
        try:
            record, files, value = self.open(root, run_id)
            report.update(state=value['state'], kind=value['kind'])
            kind, state = value['kind'], value['state']
            if state == 'deleted' or (kind == 'evidence' and state == 'closed'):
                return None, {**report, 'reason': 'CLOSURE_RECORDED', 'expires_at': value.get('expires_at')}
            if kind not in {'work', 'evidence'} or kind != candidate['kind'] or value['owner'] != candidate['owner']:
                return None, {**report, 'reason': 'RUN_OWNERSHIP_UNCONFIRMED'}
            if date.fromisoformat(candidate['released_on']) > now.date():
                return None, {**report, 'reason': 'RUN_RELEASE_PENDING'}
            if value.get('hold') or self.runtime.consumption_state(value) != 'ended':
                return None, {**report, 'reason': 'RUN_HELD_OR_CONSUMED'}
            if collection := self.settings.get('collection'):
                guard = relative_path(files, collection['record'])
                if guard.exists() and value_at(read_json(guard), collection['field']) != collection['complete']:
                    return None, {**report, 'reason': 'RUN_COLLECTION_PENDING', 'record': str(guard)}
            if state != 'active' and (kind != 'work' or self.runtime.evaluate(value, files, now) != 'due'):
                return None, {**report, 'reason': 'RUN_STATE_UNCONFIRMED'}
            inventory = self.runtime.data_inventory(files, value)
            options = ['--discard-work'] if kind == 'work' else ['--days', str(self.settings['retention_days'])]
            action = {**report, 'kind': 'close_run', 'group_kind': kind, 'record': str(record),
                      'record_sha256': sha256(record.read_bytes()), 'inventory_sha256': sha256(json_text(inventory).encode()),
                      'arguments': ['close', '--group', run_id, *options], 'basis': candidate['reason']}
            return action, report
        except (KeyError, OSError, TypeError, ValueError) as exc:
            return None, {**report, 'reason': 'RUN_UNCONFIRMED', 'detail': str(exc)}

    def close(self, root: Path, action: dict) -> dict:
        output_root = relative_path(root, self.settings['root'])
        result = subprocess.run(
            [sys.executable, '-B', '-X', 'utf8', str(self.script), *action['arguments'],
             '--root', str(output_root)], cwd=root, check=False, capture_output=True, encoding='utf-8', timeout=60,
        )
        if result.returncode:
            raise RuntimeError(f'lifecycle close failed for {action["id"]} (exit {result.returncode})')
        _, _, value = self.open(root, action['id'])
        expected = 'deleted' if action['group_kind'] == 'work' else 'closed'
        if value['state'] != expected:
            raise RuntimeError(f'lifecycle did not reach {expected} for {action["id"]}')
        return {'state': value['state'], 'expires_at': value['expires_at']}


def preview_source(record: Path, root: Path) -> Path:
    saved = read_json(safe_path(record, root))
    source = saved.get('source_root')
    if source is None:
        owner = Path(saved['owner_path'])
        if not owner.is_absolute():
            raise ValueError('preview owner path must be absolute')
        receipt = read_json(owner)
        if saved.get('process') is not None and saved['process'] != receipt.get('process'):
            raise ValueError('preview owner receipt has changed')
        source = receipt['source_root']
    path = Path(source)
    if not path.is_absolute() or not path.is_dir():
        raise ValueError('preview source directory cannot be confirmed')
    return path.resolve(strict=True)


def tree_finalizers(root, path, tree, runs, now, active_owners, settings, registered) -> list[dict]:
    blocked = []
    if tree['state'] != 'retiring' or active_owners:
        blocked.append({'code': 'TASK_OR_WORKTREE_RETAINED', 'state': tree['state'], 'tasks': active_owners})
    bindings = tree.get('thread_bindings')
    if bindings is None:
        blocked.append({'code': 'THREAD_BINDINGS_UNCONFIRMED'})
    elif pending := [binding['id'] for binding in bindings if binding['state'] != 'settled']:
        blocked.append({'code': 'THREAD_UNSETTLED', 'bindings': pending})
    for binding in tree.get('runs', []):
        project = {'primary': root, 'worktree': path}[binding['location']]
        retained = runs.retention(project, binding['id'], now)
        if retained:
            blocked.append(retained)
    if tree['state'] == 'retiring':
        if tree.get('consumers_checked') is not True:
            blocked.append({'code': 'CONSUMERS_UNCONFIRMED'})
        if path.is_dir() and settings.get('inspect_windows_processes'):
            from tools.audit.worktree_check import process_references
            observed = process_references([path])
            if not observed['checked'] or observed['matches']:
                blocked.append({'code': 'WORKTREE_PROCESS_CHECK', **observed})
        for pattern in settings.get('preview_registries', []):
            for record in sorted(root.glob(pattern)):
                try:
                    source = preview_source(record, root)
                except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                    source = None
                if source == path:
                    blocked.append({'code': 'WORKTREE_PREVIEW_REGISTERED', 'record': str(record)})
                elif source not in registered:
                    blocked.append({'code': 'WORKTREE_PREVIEW_SOURCE_UNCONFIRMED', 'record': str(record)})
    return blocked


def inspect_tree(root: Path, path: Path, tree: dict, records: dict[Path, dict], state: GitState,
                 runs: RunRecords | None, now: datetime, active_owners: list[str], settings: dict) -> dict:
    record = records.get(path)
    branch = tree.get('branch')
    ref = f'refs/heads/{branch}' if branch else None
    local, remote = state.local_refs.get(ref), state.remote_refs.get(ref)
    tracking = state.local_refs.get(f'refs/remotes/{state.remote}/{branch}') if branch else None
    head = record['HEAD'] if record else tree.get('head')
    observation = {'id': tree['id'], 'path': str(path), 'branch': branch, 'head': head, 'registered': bool(record),
                   'local_branch_tip': local, 'remote_branch_tip': remote, 'tracking_tip': tracking,
                   'reason': tree['reason']}
    absent = not record and not path.exists() and local is None and remote is None and tracking is None
    if absent and state.remote_error is None and tree['state'] in {'retired', 'retiring'}:
        return {**observation, 'disposition': 'already_absent'}
    finalizers = tree_finalizers(root, path, tree, runs, now, active_owners, settings, records)
    reasons = [item['code'] for item in finalizers]
    inventory = None
    try:
        if record and not ({'locked', 'prunable', 'bare'} & record.keys()):
            inventory = tree_inventory(path)
            if any(inventory.values()):
                reasons.append('WORKTREE_HAS_LOCAL_CONTENT')
        elif record or path.exists():
            reasons.append('WORKTREE_REGISTRATION_UNCONFIRMED')
    except (OSError, RuntimeError, subprocess.SubprocessError):
        reasons.append('WORKTREE_INVENTORY_UNCONFIRMED')
    if (record and record.get('branch') != ref) or (tree.get('head') and head != tree['head']):
        reasons.append('WORKTREE_IDENTITY_CHANGED')
    if tree['state'] == 'retiring' and not tree.get('head'):
        reasons.append('WORKTREE_HEAD_UNPINNED')
    if ref and (ref == state.base_ref or any(r.get('branch') == ref for p, r in records.items() if p != path)):
        reasons.append('BRANCH_IN_USE')
    if ref and ((record and local != head) or any(tip not in (None, head) for tip in (local, remote, tracking))):
        reasons.append('BRANCH_TIP_UNCONFIRMED')
    if not included(root, head, state):
        reasons.append('HEAD_NOT_IN_BOTH_MAINLINES')
    diff = None
    if head and re.fullmatch(COMMIT_PATTERN, head) and state.remote_base:
        comparison = git(root, 'rev-list', '--left-right', '--count', f'{head}...{state.remote_base}', allowed=(0, 128))
        if comparison.returncode == 0:
            ahead, behind = map(int, comparison.stdout.split())
            diff = {'ahead': ahead, 'behind': behind}
    return {**observation, 'inventory': inventory, 'diff_vs_remote_base': diff, 'finalizers': finalizers,
            'reasons': sorted(set(reasons)), 'disposition': 'blocked' if reasons else 'retiring'}


def handoff_action(root: Path, candidate: dict, verified_runs: dict, state: GitState) -> tuple[dict | None, dict | None]:
    name = candidate['path']
    path = relative_path(root, name)
    if not path.exists():
        return None, None
    references = referrers(root, name)
    digest = sha256(path.read_bytes()) if path.is_file() else None
    reasons = []
    if not digest or digest != candidate['sha256'] or name in tracked_paths(root):
        reasons.append('HANDOFF_CONTENT_UNCONFIRMED')
    if references:
        reasons.append('HANDOFF_STILL_REFERENCED')
    release = verified_runs.get((candidate['run_id'], candidate['action'], candidate['saved_commit']))
    if release is None:
        reasons.append('HANDOFF_RELEASE_UNCONFIRMED')
    if not included(root, candidate['saved_commit'], state):
        reasons.append('HANDOFF_SAVE_UNCONFIRMED')
    if reasons:
        return None, {'id': name, 'reason': 'HANDOFF_EXIT_UNCONFIRMED', 'checks': reasons, 'references': references}
    return {'kind': 'remove_stale_handoff', 'id': name, 'sha256': digest, 'saved_commit': candidate['saved_commit'],
            'release_run': release.run_id, 'release_action': release.action, 'release_pid': release.pid,
            'release_finished_at': release.finished_at, 'basis': candidate['reason']}, None


def release_directories(root: Path, policy: dict, latest) -> tuple[list[dict], list[dict]]:
    registry = read_json(relative_path(root, policy['path']))
    if registry.get('version') != policy['schema_version']:
        raise ValueError('unsupported release directory registry')
    directory = relative_path(root, policy['directories'])
    current = latest.product_commit[:policy['revision_prefix_length']]
    previous = registry[policy['rollback_field']]
    rollback = safe_path(Path(previous), directory).name if previous else None
    kept, review = [], []
    for path in sorted(directory.iterdir()):
        if not re.fullmatch(policy['dir_pattern'], path.name):
            continue
        record = {'id': path.name, 'path': str(path)}
        if path.name == current:
            kept.append({**record, 'reason': 'current'})
        elif path.name == rollback:
            kept.append({**record, 'reason': 'rollback'})
        elif path.is_symlink() or path.is_junction() or path.name not in registry[policy['registry_field']]:
            review.append({**record, 'reason': 'unknown-ownership'})
        else:
            kept.append({**record, 'reason': 'registered-release'})
    return kept, review


def tree_path(root: Path, config: dict, tree_id: str) -> Path:
    configured = Path(config['git']['worktree_root'])
    if configured.is_absolute():
        raise ValueError('worktree root must be relative to the checkout')
    directory = safe_path(root / configured, root.parent)
    path = safe_path(directory / tree_id, directory)
    if path == root or root.is_relative_to(path) or path.is_relative_to(root):
        raise ValueError('retirement candidate overlaps the primary checkout')
    return path


def plan(root: Path, config: dict) -> dict:
    settings = config['closeout']
    trees = tree_specs(settings)
    tasks, errors = load_tasks(root, config['tasks'], trees)
    if errors:
        return {'ok': False, 'diagnostics': errors}
    now = datetime.now(timezone.utc)
    state = git_state(root, config['git'], trees)
    records = registered_trees(root)
    if next(iter(records), None) != root:
        raise ValueError('closeout must start from the primary checkout')
    runs = RunRecords(settings['runs']) if 'runs' in settings else None
    verified = receipts(root, config['entry'])
    actions, blocked, observations, retained, review = [], [], [], [], []
    known_paths = {root}
    for tree in trees.values():
        path = tree_path(root, config, tree['id'])
        known_paths.add(path)
        active = sorted(task.id for task in tasks.values()
                        if task.worktree == tree['id'] and task.status not in config['tasks']['finished_states'])
        seen = inspect_tree(root, path, tree, records, state, runs, now, active, settings)
        observations.append(seen)
        if seen['disposition'] == 'blocked':
            blocked.append({'id': tree['id'], 'reasons': seen['reasons'], 'finalizers': seen['finalizers']})
        elif seen['disposition'] == 'retiring':
            actions.append({'kind': 'retire_worktree', 'id': tree['id'], 'proof': seen,
                            'local_base': state.local_base, 'remote_base': state.remote_base,
                            'remote_endpoint_sha256': state.endpoint_hash,
                            'bare_remote': str(state.bare_remote) if state.bare_remote else None})
    for path, record in sorted(records.items()):
        if path not in known_paths:
            review.append({'id': path.name, 'path': str(path), 'head': record.get('HEAD'),
                           'branch': record.get('branch'), 'reason': 'unknown-worktree-ownership'})
    verified_keys = {(run.run_id, run.action, run.product_commit): run for run in verified}
    for handoff in settings.get('handoffs', []):
        action, pending = handoff_action(root, handoff, verified_keys, state)
        if action:
            actions.append(action)
        if pending:
            review.append(pending)
    if runs:
        candidates = {item['id']: item for item in settings['runs'].get('release', [])}
        if len(candidates) != len(settings['runs'].get('release', [])):
            raise ValueError('duplicate run release declaration')
        for _, candidate in sorted(candidates.items()):
            action, keep = runs.close_action(root, candidate, now)
            if action:
                actions.append(action)
            elif keep['reason'] != 'CLOSURE_RECORDED':
                retained.append(keep)
        locations = {binding['id']: tree_path(root, config, tree['id'])
                     for tree in trees.values() for binding in tree.get('runs', [])
                     if binding['location'] == 'worktree'}
        for run_id in sorted({run for task in tasks.values() for run in task.managed_runs} - candidates.keys()):
            if keep := runs.retention(locations.get(run_id, root), run_id, now):
                retained.append(keep)
    if policy := settings.get('retention'):
        if not verified:
            raise ValueError('cannot classify release directories without a verified current receipt')
        keep, unknown = release_directories(root, policy, verified[0])
        retained.extend(keep)
        review.extend(unknown)
    return {
        'ok': True, 'schema_version': 1, 'repo': str(root), 'config_sha256': sha256(json_text(config).encode()),
        'head': git(root, 'rev-parse', 'HEAD').stdout.strip(), 'local_base': state.local_base,
        'remote_base': state.remote_base, 'remote_error': state.remote_error,
        'remote_endpoint_sha256': state.endpoint_hash,
        'actions': actions, 'blocked': blocked, 'worktrees': observations, 'retained': retained, 'review': review,
    }


@contextmanager
def apply_lock(root: Path):
    common = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir').stdout.strip()).resolve(strict=True)
    lock = safe_path(common / 'doc-ops-apply.lock', common)
    with lock.open('a+b') as stream:
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def retire(root: Path, config: dict, action: dict, completed: list[dict]) -> None:
    proof = action['proof']
    path = tree_path(root, config, action['id'])
    branch = proof['branch']
    state = git_state(root, config['git'], tree_specs(config['closeout']))
    ref = f'refs/heads/{branch}' if branch else None
    tracking = f'refs/remotes/{state.remote}/{branch}' if branch else None
    if (state.local_base != action['local_base'] or state.remote_base != action['remote_base']
            or state.endpoint_hash != action['remote_endpoint_sha256']
            or state.local_refs.get(ref) != proof['local_branch_tip']
            or state.remote_refs.get(ref) != proof['remote_branch_tip']
            or state.local_refs.get(tracking) != proof['tracking_tip']
            or (str(state.bare_remote) if state.bare_remote else None) != action['bare_remote']):
        raise RuntimeError('mainline or branch changed before retirement')
    if proof['registered']:
        git(root, '-c', 'core.longpaths=true', 'worktree', 'remove', '--', str(path))
        if path.exists() or path in registered_trees(root):
            raise RuntimeError('worktree still present after removal')
        completed.append({'step': 'remove_worktree', 'path': str(path)})
    if branch is None:
        return
    head = proof['head']
    if proof['remote_branch_tip']:
        if state.bare_remote:
            git(state.bare_remote, 'update-ref', '--stdin',
                stdin=f'verify {state.base_ref} {state.remote_base}\ndelete {ref} {head}\n')
        else:
            git(root, 'push', f'--force-with-lease={ref}:{head}', '--', state.remote, f':{ref}')
        completed.append({'step': 'remove_remote_branch', 'ref': ref})
    if proof['local_branch_tip']:
        if any(record.get('branch') == ref for record in registered_trees(root).values()):
            raise RuntimeError('branch is checked out')
        git(root, 'update-ref', '--stdin',
            stdin=f'verify {state.base_ref} {state.local_base}\ndelete {ref} {head}\n')
        completed.append({'step': 'remove_local_branch', 'ref': ref})
    if proof['tracking_tip']:
        # Git push may already have removed the tracking ref.
        tracked_tip = git(root, 'show-ref', '--verify', '--hash', tracking, allowed=(0, 128))
        if tracked_tip.stdout.strip() not in ('', head):
            raise RuntimeError('tracking ref changed')
        if tracked_tip.returncode == 0:
            git(root, 'update-ref', '-d', tracking, head)
            completed.append({'step': 'remove_tracking_ref', 'ref': tracking})
    after = git_state(root, config['git'], tree_specs(config['closeout']))
    if after.remote_error or ref in after.local_refs or ref in after.remote_refs or tracking in after.local_refs:
        raise RuntimeError('branch exit could not be verified')


def apply(root: Path, config: dict, approved: dict) -> dict:
    applied = []
    with apply_lock(root):
        current = plan(root, config)
        if current != approved:
            return {'ok': False, 'diagnostics': [{'code': 'PLAN_STALE'}, *current.get('diagnostics', [])],
                    'applied': applied}
        if not current['ok']:
            return current
        for action in current['actions']:
            steps = []
            try:
                # Completed operations disappear from the next plan. Pending ones must still match.
                rechecked = plan(root, config)
                if not rechecked['ok'] or action not in rechecked['actions']:
                    return {'ok': False, 'diagnostics': [{'code': 'PLAN_STALE', 'id': action['id']}], 'applied': applied}
                if action['kind'] == 'retire_worktree':
                    retire(root, config, action, steps)
                elif action['kind'] == 'remove_stale_handoff':
                    path = relative_path(root, action['id'])
                    if sha256(path.read_bytes()) != action['sha256']:
                        raise RuntimeError('handoff content changed')
                    path.unlink()
                    steps.append({'step': 'unlink_handoff', 'path': str(path)})
                else:
                    observed = RunRecords(config['closeout']['runs']).close(root, action)
                    steps.append({'step': 'close_registered_run', **observed})
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
                return {'ok': False, 'applied': applied, 'partial': steps,
                        'diagnostics': [{'code': 'APPLY_STEP_FAILED', 'id': action['id'], 'detail': str(error)}]}
            applied.append({'kind': action['kind'], 'id': action['id'], 'steps': steps})
    return {'ok': True, 'applied': applied, 'blocked': current['blocked'], 'review': current['review']}
