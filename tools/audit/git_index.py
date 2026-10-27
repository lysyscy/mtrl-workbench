"""提交审计的Git原生输入：NUL路径、stage-0 blob，Git失败不得变成空扫描。"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True).stdout


def staged_changes(root: Path) -> dict[Path, str]:
    # 禁用rename折叠后，重命名就是D+A；两者仍是原生Git index语义。
    raw = _git(root, 'diff', '--cached', '--name-status', '-z', '--no-renames', '--no-ext-diff')
    fields = raw.split(b'\0')[:-1]
    return {root / os.fsdecode(name): status.decode('ascii')
            for status, name in zip(fields[::2], fields[1::2], strict=True)}


def index_bytes(root: Path, path: Path) -> bytes:
    return _git(root, 'cat-file', 'blob', ':' + path.relative_to(root).as_posix())


def index_paths(root: Path, prefix: str) -> list[Path]:
    return [root / os.fsdecode(name) for name in _git(root, 'ls-files', '-z', '--', prefix).split(b'\0') if name]
