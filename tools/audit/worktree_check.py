"""Read-only worktree exit evidence; a complete scan is never deletion approval."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def git(root: Path, *args: str, allowed=(0,)):
    result = subprocess.run(
        ['git', '--no-optional-locks', *args], cwd=root, capture_output=True,
        env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, check=False,
    )
    if result.returncode not in allowed:
        raise RuntimeError(f'git {args[0]} failed ({result.returncode})')
    return result


def text(root: Path, *args: str) -> str:
    return git(root, *args).stdout.decode('utf-8').strip()


def worktrees(root: Path) -> list[dict]:
    records = []
    for block in git(root, 'worktree', 'list', '--porcelain', '-z').stdout.split(b'\0\0'):
        record = {}
        for field in block.split(b'\0'):
            if field:
                key, _, value = field.decode('utf-8').partition(' ')
                record[key] = value
        if record:
            records.append(record)
    return records


def changes(root: Path) -> list[dict]:
    fields = iter(git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all').stdout.split(b'\0'))
    result = []
    for raw in fields:
        if not raw:
            continue
        item = {'status': raw[:2].decode('ascii'), 'path': raw[3:].decode('utf-8')}
        if 'R' in item['status'] or 'C' in item['status']:
            item['source'] = next(fields).decode('utf-8')
        result.append(item)
    return result


def inventory(path: Path) -> dict:
    """Count every entry without following any symlink/junction/reparse point."""
    result = {'path': str(path), 'files': 0, 'bytes': 0, 'links': [], 'errors': []}
    pending = [path]
    while pending:
        current = pending.pop()
        try:
            # Literal Windows names such as a legacy "nul" must not resolve to devices.
            native = str(current.absolute())
            if os.name == 'nt' and not native.startswith('\\\\?\\'):
                native = '\\\\?\\UNC\\' + native[2:] if native.startswith('\\\\') else '\\\\?\\' + native
            info = os.lstat(native)
            is_link = stat.S_ISLNK(info.st_mode) or bool(
                getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)
            )
            if is_link:
                result['links'].append({'path': str(current), 'target': os.readlink(native)})
            elif stat.S_ISDIR(info.st_mode):
                with os.scandir(native) as entries:
                    pending.extend(current / entry.name for entry in entries)
            elif stat.S_ISREG(info.st_mode):
                result['files'] += 1
                result['bytes'] += info.st_size
            else:
                result['errors'].append({'path': str(current), 'error': 'special_file'})
        except OSError as error:
            result['errors'].append({'path': str(current), 'error': type(error).__name__})
    return result


def process_references(paths: list[Path]) -> dict:
    """Command-line evidence only: cannot establish absence of other consumers."""
    if sys.platform != 'win32':
        return {'checked': False, 'error': 'process inspection requires Windows; check consumers separately'}
    script = (
        "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
        "@(Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine) | ConvertTo-Json -Compress"
    )
    try:
        output = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command', script], capture_output=True,
            encoding='utf-8', check=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout
        processes = json.loads(output)
        matches = []
        for process in processes:
            command = (process.get('CommandLine') or '').replace('\\', '/').casefold()
            for path in paths:
                if str(path).replace('\\', '/').casefold() in command:
                    matches.append({'worktree': str(path), 'pid': process['ProcessId'], 'name': process['Name']})
        # Do not expose command lines: they may contain credentials.
        return {'checked': True, 'matches': matches,
                'without_command_line': sum(not p.get('CommandLine') for p in processes)}
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError) as error:
        return {'checked': False, 'error': type(error).__name__}


def preview_registration(common: Path) -> dict:
    pointer = common.parent / 'var/state/react-writable-preview/current.json'
    try:
        if not pointer.exists():
            return {'path': str(pointer), 'present': False}
        value = json.loads(pointer.read_text(encoding='utf-8-sig'))
        # Presence always needs the preview owner's identity/use check, even if stale.
        return {'path': str(pointer), 'present': True, 'owner_path': value['owner_path']}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'path': str(pointer), 'error': type(error).__name__}


def inspect_tree(root: Path, record: dict, base: str) -> dict:
    path = Path(record['worktree'])
    item = {'path': str(path), 'head': record.get('HEAD'), 'branch': record.get('branch'),
            'locked': 'locked' in record, 'prunable': 'prunable' in record, 'errors': []}
    try:
        ancestor = git(root, 'merge-base', '--is-ancestor', record['HEAD'], base, allowed=(0, 1))
        item['head_in_base'] = ancestor.returncode == 0
        item['changes'] = changes(path)
        flags = git(path, 'ls-files', '-v', '-z').stdout.split(b'\0')
        item['hidden_index_flags'] = [value.decode('utf-8') for value in flags
                                      if value and (value[:1].islower() or value[:1] == b'S')]
        # Include all ignored groups. A directory count is evidence, not classification.
        ignored = git(path, 'ls-files', '--others', '--ignored', '--exclude-standard', '--directory', '-z')
        item['ignored'] = [inventory(path / value.decode('utf-8'))
                           for value in ignored.stdout.split(b'\0') if value]
        # Inventory changed/untracked entries too, so links and unreadable content are visible.
        item['local_entries'] = [inventory(path / entry['path']) for entry in item['changes']
                                 if not (entry['status'][1] == 'D' or entry['status'] == 'D ')]
        for group in item['ignored'] + item['local_entries']:
            item['errors'].extend(group['errors'])
    except (OSError, RuntimeError, UnicodeError, KeyError) as error:
        item['errors'].append(str(error))
    return item


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='repository checkout (read only)')
    parser.add_argument('--base', default='master', help='local integration ref; not live remote proof')
    parser.add_argument('--worktree', type=Path, action='append', help='registered absolute path; repeatable; default all additional worktrees')
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        common = Path(text(root, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
        records = worktrees(root)
        selected = records[1:]
        if args.worktree:
            requested = {os.path.normcase(os.path.abspath(p)) for p in args.worktree}
            selected = [r for r in records if os.path.normcase(os.path.abspath(r['worktree'])) in requested]
            if len(selected) != len(requested):
                raise ValueError('requested path is not a registered worktree')
            if records[0] in selected:
                raise ValueError('primary worktree is not an exit candidate')
        base = text(root, 'rev-parse', '--verify', args.base + '^{commit}')
        entries = [inspect_tree(root, record, base) for record in selected]
        consumers = process_references([Path(e['path']) for e in entries]) if entries else {'checked': True, 'matches': []}
        preview = preview_registration(common)
        complete = all(not e['errors'] for e in entries) and consumers['checked'] and 'error' not in preview
        result = {'scan_complete': complete, 'base': {'ref': args.base, 'sha': base, 'remote_verified': False},
                  'worktrees': entries, 'process_commands': consumers, 'preview_registration': preview,
                  'limits': ['No deletion eligibility or authorization is inferred.',
                             'Review ignored content, saved remote commits, task ownership and recovery/acceptance uses.',
                             'Process command matches do not inspect working directories, open handles, services or scheduled tasks.',
                             'Recheck files, links and consumers immediately before authorized removal.']}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if complete else 2
    except (OSError, RuntimeError, UnicodeError, ValueError) as error:
        print(json.dumps({'scan_complete': False, 'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
