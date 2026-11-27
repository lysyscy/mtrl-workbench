"""Check repository directory ownership and report retention drift."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from importlib.util import source_from_cache
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == '__main__':
    sys.dont_write_bytecode = True

from tools.audit.git_index import _git, index_bytes, index_paths

MANIFEST = Path('tools/audit/directory_manifest.json')
RELEASES = PurePosixPath('var/frontend/releases')
RELEASE_RETENTION = Path('var/state/frontend-release/retention.json')
CACHE_RULE = PurePosixPath('**/__pycache__')
HARD_PROTECTED = tuple(map(PurePosixPath, (
    'data', 'exports', 'var/backups', '.artifacts/runs', 'var/frontend/releases',
)))
PROTECTED_CLASSES = {'business', 'backup', 'hold', 'permanent'}


@dataclass(frozen=True)
class DirectoryRule:
    owner: str
    category: str
    manager: str
    check_children: bool
    retention_groups: bool
    apply_eligible: bool
    soft_thresholds: dict | None

    @property
    def protected(self) -> bool:
        return self.manager != 'none' or self.category in PROTECTED_CLASSES or self.soft_thresholds is not None

    @property
    def guidance(self) -> str:
        if self.manager != 'none':
            return f'由 {self.owner} 核对，使用 {self.manager}'
        return f'由 {self.owner} 核对用途和保留记录'


def load_manifest(root: Path, *, staged: bool = False) -> dict[PurePosixPath, DirectoryRule]:
    path = root / MANIFEST
    raw = index_bytes(root, path) if staged else path.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or manifest.get('version') != 1 or not isinstance(manifest.get('directories'), list):
        raise ValueError('目录清单版本或 directories 不符')
    rules = {}
    spellings = set()
    for row in manifest['directories']:
        required = ('path', 'owner', 'class', 'git_policy', 'manager', 'retention', 'exit_condition')
        if not isinstance(row, dict) or not all(isinstance(row.get(key), str) and row[key].strip() for key in required):
            raise ValueError('目录清单缺少路径、归属、Git 策略或退出规则')
        name = row['path']
        relative = PurePosixPath(name)
        if (name.casefold() in spellings or not relative.parts or relative.is_absolute() or relative.as_posix() != name
                or any(part.endswith(('.', ' ')) for part in relative.parts)
                or any(char in name for char in '\\:\0?[]<>|')
                or ('*' in name and relative != CACHE_RULE)):
            raise ValueError(f'目录清单路径无效或重复：{name}')
        spellings.add(name.casefold())
        flags = (row.get('check_children', False), row.get('retention_groups', False), row.get('apply_eligible'))
        if any(type(value) is not bool for value in flags):
            raise ValueError(f'目录清单开关必须为布尔值：{name}')
        thresholds = row.get('soft_thresholds')
        if thresholds is not None and (
            not isinstance(thresholds, dict)
            or type(thresholds.get('max_files')) is not int or thresholds['max_files'] <= 0
            or type(thresholds.get('max_mb')) not in (int, float) or not 0 < thresholds['max_mb'] < float('inf')
            or not isinstance(thresholds.get('remediation_hint'), str) or not thresholds['remediation_hint'].strip()
        ):
            raise ValueError(f'目录清单容量阈值无效：{name}')
        rule = DirectoryRule(row['owner'], row['class'], row['manager'], *flags, thresholds)
        if rule.apply_eligible and (rule.protected or rule.category != 'residue' or rule.owner != 'none'):
            raise ValueError(f'通用清理仅接受无主残留：{name}')
        rules[relative] = rule
    for relative in rules:
        if relative != CACHE_RULE and len(relative.parts) > 1 and relative.parent not in rules:
            raise ValueError(f'目录清单缺少上级路径：{relative.parent}')
    return rules


def staged_check(root: Path, *, fallback: Path | None = None) -> int:
    raw = _git(root, 'diff', '--cached', '--name-only', '-z', '--diff-filter=ACMR', '--no-renames', '--no-ext-diff')
    files = [PurePosixPath(os.fsdecode(name)) for name in raw.split(b'\0') if name]
    if not files:
        print('OK 暂存目录检查')
        return 0
    # The installed hook is shared with worktrees that predate the manifest.
    if fallback is not None and not index_paths(root, MANIFEST.as_posix()):
        rules = load_manifest(fallback)
    else:
        rules = load_manifest(root, staged=True)
    unknown = sorted({path.parts[0] for path in files if len(path.parts) > 1
                      and ((rule := rules.get(PurePosixPath(path.parts[0]))) is None or rule.category == 'residue')})
    for name in unknown:
        print(f'ERROR {name} 未登记为仓库顶层目录。请选用现有目录或同时暂存目录清单。')
    if not unknown:
        print('OK 暂存目录检查')
    return int(bool(unknown))


def lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def plain_directory(root: Path, relative: PurePosixPath) -> Path | None:
    path = root
    for part in relative.parts:
        path = path / part
        info = lstat(path)
        if info is None or is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            return None
    return path


def child_directories(directory: Path) -> Iterator[tuple[Path, os.stat_result]]:
    for child in directory.iterdir():
        info = lstat(child)
        if info is not None and (stat.S_ISDIR(info.st_mode) or is_reparse(info)):
            yield child, info


def read_record(path: Path) -> dict | None:
    info = lstat(path)
    if info is None:
        return None
    if is_reparse(info) or not stat.S_ISREG(info.st_mode):
        raise ValueError('记录不是普通文件')
    record = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(record, dict):
        raise ValueError('记录不是 JSON 对象')
    return record


def on_hold(record: dict) -> bool:
    fields = {key.casefold(): value for key, value in record.items()}
    return (
        any(fields.get(key) for key in ('hold', 'permanent', 'hold_reason'))
        or any(str(fields.get(key, '')).casefold() in {'hold', 'held', 'permanent'}
               for key in ('kind', 'status', 'state', 'retention'))
    )


def expired_retention(record: dict, now: datetime) -> str | None:
    expiry = record.get('expires_on') or record.get('expires_at')
    if expiry is None or on_hold(record):
        return None
    if not isinstance(expiry, str):
        raise ValueError('保留期限不是 ISO 日期')
    if len(expiry) == 10:
        due = date.fromisoformat(expiry) <= now.date()
    else:
        due = datetime.fromisoformat(expiry).astimezone() <= now
    return expiry if due else None


def tree_bytes(path: Path) -> tuple[int, int]:
    count = size = 0
    pending = [path]
    while pending:
        for child in pending.pop().iterdir():
            info = lstat(child)
            if info is None or is_reparse(info):
                continue
            if stat.S_ISDIR(info.st_mode):
                pending.append(child)
            elif stat.S_ISREG(info.st_mode):
                count += 1
                size += info.st_size
    return count, size


def cache_sources(directory: Path) -> dict[Path, tuple[Path, os.stat_result]] | None:
    """Identify a cache that contains only Python bytecode with no source."""
    entries = {}
    for item in directory.iterdir():
        info = lstat(item)
        if (info is None or is_reparse(info) or not stat.S_ISREG(info.st_mode)
                or item.suffix != '.pyc'):
            return None
        try:
            source = Path(source_from_cache(str(item)))
        except ValueError:
            return None
        if lstat(source) is not None:
            return None
        entries[item] = (source, info)
    return entries


class WorkspaceAudit:
    def __init__(self, root: Path, rules: dict[PurePosixPath, DirectoryRule], *, apply: bool):
        self.root = root
        self.rules = rules
        self.apply = apply
        self.now = datetime.now().astimezone()
        self.errors = 0

    def error(self, path: PurePosixPath, message: str) -> None:
        self.errors += 1
        print(f'ERROR {path} {message}')

    def check_children(self, path: Path, relative: PurePosixPath, rule: DirectoryRule | None = None) -> None:
        for child, _ in sorted(child_directories(path)):
            name = relative / child.name
            if name not in self.rules and not (child.name == '__pycache__' and CACHE_RULE in self.rules
                                                and rule is not None and not rule.protected):
                guidance = rule.guidance if rule else '请选用现有目录或更新目录清单'
                self.error(name, f'未登记的目录。{guidance}。')

    def check_retention(self, path: Path, rule: DirectoryRule) -> None:
        relative = PurePosixPath(path.relative_to(self.root).as_posix())
        try:
            record = read_record(path)
            expiry = expired_retention(record, self.now) if record is not None else None
        except (OSError, ValueError):
            self.error(relative, f'无法核实保留记录。{rule.guidance}。')
        else:
            if expiry:
                self.error(relative, f'保留记录已于 {expiry} 到期。{rule.guidance}。')

    def check_releases(self, path: Path, rule: DirectoryRule) -> None:
        try:
            state = plain_directory(self.root, PurePosixPath(RELEASE_RETENTION.parent.as_posix()))
            if state is None and os.path.lexists(self.root / RELEASE_RETENTION.parent):
                raise ValueError
            record = read_record(state / RELEASE_RETENTION.name) if state else None
            releases = {} if record is None else record.get('releases')
            if not isinstance(releases, dict):
                raise ValueError
        except (OSError, ValueError):
            self.error(RELEASES, f'无法核实发布登记。{rule.guidance}。')
            return
        for directory, _ in sorted(child_directories(path)):
            if directory.name not in releases:
                self.error(RELEASES / directory.name, f'发布目录未登记。{rule.guidance}。')

    def eligible(self, relative: PurePosixPath, rule: DirectoryRule) -> bool:
        # A child exemption cannot grant a second owner cleanup rights.
        name = PurePosixPath(relative.as_posix().casefold())
        if not rule.apply_eligible or any(name.is_relative_to(path) for path in HARD_PROTECTED):
            return False
        for ancestor in (relative, *relative.parents):
            policy = self.rules.get(ancestor)
            if (policy is not None and policy.protected) or any(
                os.path.lexists(self.root / ancestor / filename) for filename in ('retention.json', 'run.json')
            ):
                return False
        return True

    def inspect_residue(self, path: Path, relative: PurePosixPath, rule: DirectoryRule, *, cache: bool = False) -> None:
        if not self.eligible(relative, rule):
            return
        candidates = cache_sources(path) if cache else ({} if not any(path.iterdir()) else None)
        if candidates is None:
            if not cache:
                self.error(relative, '已退役目录又有内容，需核对归属。')
            return
        if self.apply:
            tracked = index_paths(self.root, ':(literal)' + relative.as_posix())
            path = plain_directory(self.root, relative)
            if (tracked or path is None or path.resolve(strict=True) != path or not self.eligible(relative, rule)
                    or (cache_sources(path) != candidates if cache else any(path.iterdir()))):
                self.error(relative, '现场已变化或含 Git 索引内容，保留待核。')
                return
            for item, (source, info) in candidates.items():
                if lstat(source) is not None or lstat(item) != info:
                    self.error(relative, '缓存或源码已变化，保留待核。')
                    return
                item.unlink()
            path.rmdir()
            print(f'REMOVED {relative}')
        else:
            reason = '无源字节码缓存' if cache else '空退役目录'
            print(f'RESIDUE {relative} {reason}。可用 --apply 复核清理。')

    def inspect_caches(self, path: Path, relative: PurePosixPath, cache_rule: DirectoryRule) -> None:
        for child, info in child_directories(path):
            if is_reparse(info):
                continue
            name = relative / child.name
            rule = self.rules.get(name)
            if child.name == '__pycache__' and rule is None:
                self.inspect_residue(child, name, cache_rule, cache=True)
            elif self.eligible(name, cache_rule) and (rule is None or rule.category in {'source', 'legacy', 'residue'}):
                self.inspect_caches(child, name, cache_rule)

    def inspect(self, path: Path, relative: PurePosixPath, rule: DirectoryRule) -> None:
        if rule.check_children:
            self.check_children(path, relative, rule)
        if rule.category not in {'metadata', 'cache', 'business'}:
            self.check_retention(path / 'retention.json', rule)
        if rule.retention_groups:
            for child, info in sorted(child_directories(path)):
                if not is_reparse(info):
                    self.check_retention(child / 'retention.json', rule)
        if relative == RELEASES:
            self.check_releases(path, rule)
        if rule.soft_thresholds:
            limits = rule.soft_thresholds
            count, size = tree_bytes(path)
            mb = size / (1024 * 1024)
            if count > limits['max_files'] or mb > limits['max_mb']:
                print(f"WARN {relative} {count} 文件（阈值 {limits['max_files']}），"
                      f"{mb:.1f} MiB（阈值 {limits['max_mb']}）。{limits['remediation_hint']}")
        if rule.category == 'residue':
            self.inspect_residue(path, relative, rule)

    def run(self) -> int:
        self.check_children(self.root, PurePosixPath('.'))
        for relative, rule in self.rules.items():
            if relative == CACHE_RULE:
                continue
            try:
                path = plain_directory(self.root, relative)
                if path is not None:
                    self.inspect(path, relative, rule)
                elif (rule.check_children or rule.retention_groups or rule.soft_thresholds or relative == RELEASES
                      or rule.apply_eligible) and os.path.lexists(self.root / relative):
                    self.error(relative, f'无法检查目录，路径含链接或类型不符。{rule.guidance}。')
            except OSError as error:
                self.error(relative, f'目录检查或清理未完成（{type(error).__name__}）。{rule.guidance}。')
        cache_rule = self.rules.get(CACHE_RULE)
        if cache_rule is not None:
            for relative, rule in self.rules.items():
                if len(relative.parts) == 1 and rule.category == 'source' and not rule.protected:
                    try:
                        path = plain_directory(self.root, relative)
                        if path is not None:
                            self.inspect_caches(path, relative, cache_rule)
                    except OSError as error:
                        self.error(relative, f'缓存检查或清理未完成（{type(error).__name__}）。')
        if not self.errors:
            print('OK 目录审计')
        return int(bool(self.errors))


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--staged', action='store_true', help='只检查 Git 暂存文件的顶层目录')
    modes.add_argument('--dry-run', action='store_true', help='只读检查，与默认模式相同')
    modes.add_argument('--apply', action='store_true', help='清理清单明确允许的无主残留')
    parser.add_argument('--worktree', type=Path, help='共享提交钩子检查尚未接入目录清单的工作树')
    args = parser.parse_args(argv)
    if args.worktree is not None and not args.staged:
        parser.error('--worktree 仅用于 --staged')
    try:
        if args.staged:
            if args.worktree is not None:
                return staged_check(args.worktree.resolve(strict=True), fallback=root)
            return staged_check(root)
        return WorkspaceAudit(root, load_manifest(root), apply=args.apply).run()
    except subprocess.CalledProcessError:
        print('ERROR 无法读取 Git 暂存区。请核对 Git 状态及索引中的目录清单。', file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(f'ERROR 目录审计未完成（{error}）', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
