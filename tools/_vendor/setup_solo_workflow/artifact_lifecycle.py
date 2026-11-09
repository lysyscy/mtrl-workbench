"""Opt-in artifact lifecycle. No scheduler, database access or recursive discovery.

Each --root is a dedicated, explicitly enrolled output area, never a project root.
All writers/readers must use `lease` around active consumption. check is read-only.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

VERSION = 1
PROJECT_VERSION = 2
PROTECTED = {'.git', '.env', 'data', 'source', 'src', 'backups', 'credentials'}

def stamp(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('timestamp must include timezone')
    return result.astimezone(timezone.utc)

def safe(path):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if item.is_symlink() or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError('linked/reparse path refused')
    return path

def atomic(path, data):
    temp = safe(path.with_suffix('.tmp'))
    with temp.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)

def configuration(root):
    root = safe(root)
    config = json.loads(safe(root / '.lifecycle.json').read_text(encoding='utf-8'))
    if config == {'version': VERSION, 'root': str(root)}:
        return config
    if (set(config) != {'version', 'root', 'layout', 'project'} or
            config['version'] != PROJECT_VERSION or config['layout'] != 'runs' or
            not safe(config['root']).samefile(root) or not safe(config['project']).is_dir()):
        raise ValueError('invalid enrollment')
    return config

def enrolled(root):
    root = safe(root)
    configuration(root)
    return root

def enroll(root, project=None):
    root = safe(root)
    if root.parent == root or root.name.lower() in PROTECTED:
        raise ValueError('protected root')
    if project is not None:
        project = safe(project)
        if not project.is_dir() or root == project or root in project.parents:
            raise ValueError('dedicated output area must not contain the project')
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError('enrollment requires an empty dedicated output directory')
    config = {'version': VERSION, 'root': str(root)}
    if project is not None:
        config = dict(version=PROJECT_VERSION, root=str(root), layout='runs', project=str(project))
    atomic(root / '.lifecycle.json', config)
    (root / '.lock').touch()
    if project is None:
        (root / 'groups').mkdir()

@contextmanager
def lock(root):
    root = enrolled(root)
    with safe(root / '.lock').open('r+b') as stream:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield root
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)

def group(root, name):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', name):
        raise ValueError('invalid group id')
    if configuration(root).get('layout') == 'runs':
        folder = safe(root / name)
        return folder, safe(folder / 'run.json'), folder
    folder = safe(root / 'groups' / name)
    return folder, safe(folder / 'record.json'), safe(folder / 'files')

def inventory(folder, *, exclude=()):
    result = {}
    for item in sorted(folder.iterdir()):
        if item.name in exclude:
            continue
        safe(item)
        if item.is_dir():
            for key, value in inventory(item).items():
                result[item.name + '/' + key] = value
        elif item.is_file() and item.name.lower() not in PROTECTED:
            result[item.name] = hashlib.sha256(item.read_bytes()).hexdigest()
        else:
            raise ValueError('special or protected file refused')
    return result

def data_inventory(files, value):
    return inventory(files, exclude=('run.json',) if value.get('layout') == 'runs' else ())

def process_identity(pid=None):
    """PID plus OS creation identity; unavailable identity never authorizes cleanup."""
    pid = os.getpid() if pid is None else int(pid)
    if pid <= 0:
        raise ValueError('invalid producer pid')
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                raise ProcessLookupError(pid)
            raise PermissionError('producer identity unavailable')
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not api.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                raise OSError('producer creation time unavailable')
            start = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return {'pid': pid, 'platform': 'windows', 'start': str(start)}
        finally:
            api.CloseHandle(handle)
    if sys.platform.startswith('linux'):
        try:
            fields = Path(f'/proc/{pid}/stat').read_text(encoding='utf-8').rpartition(')')[2].split()
        except FileNotFoundError:
            raise ProcessLookupError(pid) from None
        if fields[0] == 'Z':
            raise ProcessLookupError(pid)
        boot = Path('/proc/sys/kernel/random/boot_id').read_text(encoding='ascii').strip()
        return {'pid': pid, 'platform': 'linux', 'start': boot + ':' + fields[19]}
    raise OSError('producer identity unsupported on this platform')

def producer_state(identity):
    if not isinstance(identity, dict) or set(identity) != {'pid', 'platform', 'start'}:
        return 'unknown'
    if not isinstance(identity['pid'], int) or identity['pid'] <= 0 or not identity['start']:
        return 'unknown'
    expected_platform = 'windows' if os.name == 'nt' else 'linux' if sys.platform.startswith('linux') else None
    if identity['platform'] != expected_platform:
        return 'unknown'
    try:
        actual = process_identity(identity['pid'])
    except ProcessLookupError:
        return 'ended'
    except (OSError, ValueError, IndexError):
        return 'unknown'
    return 'running' if actual == identity else 'ended'

def register(root, name, owner, reason, kind='evidence', *, development=False, workspace=None):
    if kind not in {'evidence', 'work', 'permanent'} or not owner.strip() or not reason.strip():
        raise ValueError('owner, purpose and valid kind required')
    if development and kind != 'evidence':
        raise ValueError('automatic development retention requires evidence')
    if development and configuration(root).get('layout') != 'runs':
        raise ValueError('development policy requires an explicitly adopted project area')
    producer = process_identity() if development else None
    with lock(root) as root:
        folder, record, files = group(root, name)
        folder.mkdir()
        if files != folder:
            files.mkdir()
        value = dict(version=VERSION, id=name, owner=owner, reason=reason,
                     kind=kind, state='active', closed_at=None, expires_at=None,
                     hold=None, inventory=None)
        if record.name == 'run.json':
            value.update(layout='runs', consumers=[])
        if development:
            value.update(development=True, producer=producer)
        if workspace is not None:
            value['workspace'] = str(safe(workspace))
        atomic(record, value)
        return str(files)

def load(root, name):
    folder, record, files = group(root, name)
    value = json.loads(record.read_text(encoding='utf-8'))
    if value.get('version') != VERSION or value.get('id') != name:
        raise ValueError('invalid group record')
    if value.get('kind') not in {'evidence', 'work', 'permanent'} or value.get('state') not in {'active', 'closed', 'deleting', 'deleted'}:
        raise ValueError('invalid kind/state')
    if (record.name == 'run.json') != (value.get('layout') == 'runs'):
        raise ValueError('run layout mismatch')
    return record, files, value

def consumption_state(value):
    consumers = value.get('consumers', [])
    if not isinstance(consumers, list):
        return 'unknown'
    states = []
    for entry in consumers:
        if not isinstance(entry, dict) or not isinstance(entry.get('count'), int) or entry['count'] < 1:
            return 'unknown'
        states.append(producer_state(entry.get('identity')))
    if 'unknown' in states:
        return 'unknown'
    return 'running' if 'running' in states else 'ended'

@contextmanager
def consume(root, name, *, writing=True):
    """Register every cooperating process before it touches a project run.

    The root mutex serializes membership and deletion. Creation identities keep
    live consumers protected after the original producer exits or a PID is reused.
    Legacy areas retain their original lifetime-wide OS lease.
    """
    if configuration(root).get('layout') != 'runs':
        with lock(root):
            yield
        return
    identity = process_identity()
    with lock(root) as root:
        record, _, value = load(root, name)
        if value['state'] not in {'active', 'closed'} or (writing and (value['state'] != 'active' or value['hold'])):
            raise ValueError('run unavailable for requested consumption')
        if consumption_state(value) == 'unknown':
            raise ValueError('invalid consumer registration')
        consumers = value['consumers']
        entry = next((entry for entry in consumers if entry['identity'] == identity), None)
        if entry is None:
            consumers.append({'identity': identity, 'count': 1})
        else:
            entry['count'] += 1
        atomic(record, value)
    try:
        yield
    finally:
        with lock(root) as root:
            record, _, value = load(root, name)
            entry = next((entry for entry in value['consumers'] if entry['identity'] == identity), None)
            if entry is None:
                raise ValueError('consumer registration disappeared')
            entry['count'] -= 1
            if entry['count'] == 0:
                value['consumers'].remove(entry)
            atomic(record, value)

def seal(record, files, value, now, days=30, deadline=None, result=None):
    if value['state'] != 'active' or value['hold']:
        raise ValueError('close requires active, resolved group')
    adapter_record = safe(files / 'impeccable.json')
    if adapter_record.exists() and json.loads(adapter_record.read_text(encoding='utf-8')).get('phase') != 'collected':
        raise ValueError('Impeccable outputs must finish collection before closure')
    value.update(state='closed', closed_at=now.isoformat(), inventory=data_inventory(files, value))
    value['expires_at'] = None if value['kind'] == 'permanent' else (now + timedelta(days=0 if value['kind'] == 'work' else days)).isoformat()
    if deadline is not None:
        if value['kind'] != 'evidence' or stamp(deadline) <= now:
            raise ValueError('explicit deadline requires evidence and future timestamp')
        value['expires_at'] = stamp(deadline).isoformat()
    value['days'] = days
    if result is not None:
        if result not in {'success', 'failure', 'abandoned'}:
            raise ValueError('invalid operation result')
        value['operation_result'] = result
    atomic(record, value)

def close(root, name, days=30, now=None, deadline=None, *, result=None):
    now = stamp(now)
    if days not in (30, 60):
        raise ValueError('supported retention is 30 or 60 days')
    with lock(root) as root:
        record, files, value = load(root, name)
        if consumption_state(value) != 'ended':
            raise ValueError('active or unknown consumer prevents closure')
        seal(record, files, value, now, days, deadline, result)

def hold(root, name, reason, condition, now=None):
    now = stamp(now)
    if not reason.strip() or not condition.strip():
        raise ValueError('hold reason and release condition required')
    with lock(root) as root:
        record, files, value = load(root, name)
        if value['state'] not in {'active', 'closed'}:
            raise ValueError('cannot hold deletion already started')
        if value['hold']:
            raise ValueError('existing hold must be reviewed explicitly')
        value['hold'] = dict(reason=reason, condition=condition, review_at=(now + timedelta(days=30)).isoformat())
        atomic(record, value)

def review(root, name, reason, condition, now=None):
    now = stamp(now)
    if not reason.strip() or not condition.strip(): raise ValueError('review reason and condition required')
    with lock(root) as root:
        record, files, value = load(root, name)
        if not value['hold']: raise ValueError('no hold to review')
        value['hold'] = dict(reason=reason, condition=condition, review_at=(now + timedelta(days=30)).isoformat())
        atomic(record, value)

def release(root, name, now=None):
    now = stamp(now)
    with lock(root) as root:
        record, files, value = load(root, name)
        if not value['hold']:
            raise ValueError('no hold')
        value['hold'] = None
        if value['expires_at']:
            value['expires_at'] = max(stamp(value['expires_at']), now + timedelta(days=7)).isoformat()
        atomic(record, value)

def evaluate(value, files, now):
    if value['kind'] == 'permanent':
        return 'permanent'
    if value['hold']:
        return 'review-due' if now >= stamp(value['hold']['review_at']) else 'held'
    if value['state'] == 'active':
        return 'active'
    if value['state'] == 'deleted':
        return 'deleted'
    if not value['closed_at'] or not value['expires_at'] or not isinstance(value['inventory'], dict):
        raise ValueError('incomplete closure')
    actual = data_inventory(files, value)
    expected = value['inventory']
    if value['state'] == 'deleting':
        if any(expected.get(key) != digest for key, digest in actual.items()):
            return 'changed'
    elif actual != expected:
        return 'changed'
    return 'due' if now >= stamp(value['expires_at']) else 'retained'

def sweep(root, apply=False, now=None):
    now = stamp(now)
    results = []
    with lock(root) as root:
        project_layout = configuration(root).get('layout') == 'runs'
        container = root if project_layout else safe(root / 'groups')
        for folder in sorted(container.iterdir()):
            if project_layout and folder.name in {'.lifecycle.json', '.lock', '.notices.json'}:
                continue
            try:
                record, files, value = load(root, folder.name)
                status = evaluate(value, files, now)
                consumption = consumption_state(value)
                if consumption != 'ended':
                    results.append({'id': folder.name, 'status': 'busy' if consumption == 'running' else 'activity-unknown'})
                    continue
                if status == 'active' and value.get('development') is True and value['kind'] == 'evidence':
                    activity = producer_state(value.get('producer'))
                    if activity == 'ended':
                        status = 'abandoned-ready'
                        if apply:
                            seal(record, files, value, now, result='abandoned')
                            status = 'abandoned-closed'
                    elif activity == 'unknown':
                        status = 'activity-unknown'
                if apply and status == 'deleted' and now >= stamp(value['deleted_at']) + timedelta(days=30):
                    expected_entries = {'run.json'} if project_layout else {'files', 'record.json'}
                    if set(x.name for x in folder.iterdir()) != expected_entries or data_inventory(files, value):
                        raise ValueError('unexpected receipt contents')
                    if files != folder:
                        files.rmdir()
                    record.unlink()
                    folder.rmdir()
                    results.append({'id': folder.name, 'status': 'receipt-expired'})
                    continue
                if apply and status == 'due':
                    value['state'] = 'deleting'
                    atomic(record, value)
                    # No recursive delete: remove only sealed members. Recheck each file.
                    for rel, digest in value['inventory'].items():
                        item = safe(files / rel)
                        if not item.is_relative_to(files) or '..' in Path(rel).parts:
                            raise ValueError('inventory path escape')
                        if item.exists():
                            if hashlib.sha256(item.read_bytes()).hexdigest() != digest:
                                raise ValueError('content changed during deletion')
                            item.unlink()
                    for item in sorted(files.rglob('*'), key=lambda p: len(p.parts), reverse=True):
                        safe(item)
                        if item.is_dir():
                            item.rmdir()
                    if data_inventory(files, value):
                        raise ValueError('unexpected remaining content')
                    value.update(state='deleted', deleted_at=now.isoformat(), inventory={})
                    atomic(record, value)
                    status = 'deleted'
                results.append({'id': folder.name, 'status': status})
            except (OSError, ValueError, KeyError, TypeError) as exc:
                results.append({'id': folder.name, 'status': 'error', 'error': str(exc)})
    return results

def notices(root, results):
    # Delivery is an adapter concern. Only emit newly actionable or changed events.
    with lock(root) as root:
        path = safe(root / '.notices.json')
        old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        current = {v['id']: v for v in results if v['status'] in {'error', 'changed', 'review-due', 'activity-unknown', 'abandoned-closed'}}
        changed = [v for key,v in current.items() if old.get(key) != v]
        atomic(path, current)
        return changed

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['enroll','register','close','hold','review','release','check','sweep','lease'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--group')
    p.add_argument('--owner', default='')
    p.add_argument('--reason', default='')
    p.add_argument('--condition', default='')
    p.add_argument('--kind', default='evidence')
    p.add_argument('--days', type=int, default=30)
    p.add_argument('--deadline')
    p.add_argument('--project', type=Path)
    p.add_argument('--development', action='store_true')
    p.add_argument('--workspace', type=Path)
    a, command = p.parse_known_args(argv)
    if command and a.action != 'lease': p.error('unexpected arguments')
    if a.action == 'enroll': result = enroll(a.root, project=a.project)
    elif a.action == 'register': result = register(a.root,a.group,a.owner,a.reason,a.kind,development=a.development,workspace=a.workspace)
    elif a.action == 'close': result = close(a.root,a.group,a.days,deadline=a.deadline)
    elif a.action == 'hold': result = hold(a.root,a.group,a.reason,a.condition)
    elif a.action == 'review': result = review(a.root,a.group,a.reason,a.condition)
    elif a.action == 'release': result = release(a.root,a.group)
    elif a.action == 'lease':
        command = command[1:] if command[:1] == ['--'] else command
        if not command: raise ValueError('lease requires command')
        if a.group:
            with consume(a.root, a.group): return subprocess.run(command, check=False).returncode
        with lock(a.root): return subprocess.run(command, check=False).returncode
    else: result = sweep(a.root, apply=a.action == 'sweep')
    if a.action == 'sweep':
        events = notices(a.root, result)
        print(json.dumps({'results': result, 'notifications': events}, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 1 if isinstance(result,list) and any(r['status'] in {'error','changed','review-due','activity-unknown'} for r in result) else 0

if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
