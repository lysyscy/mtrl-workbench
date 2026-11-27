"""Read Git state and keep filesystem access within declared roots."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile


def git(root: Path, *args: str, allowed=(0,), stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    # Do not update the index while inspecting a checkout or prompt for remote credentials.
    env = {**os.environ, 'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0'}
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'):
        env.pop(key, None)
    result = subprocess.run(
        ['git', '--no-optional-locks', *args], cwd=root, env=env,
        # The ref transaction protocol requires LF even on Windows.
        input=stdin.encode('utf-8') if stdin is not None else None,
        capture_output=True, check=False, timeout=45,
    )
    if result.returncode not in allowed:
        raise RuntimeError(f'git {args[0]} failed (exit {result.returncode})')
    return subprocess.CompletedProcess(result.args, result.returncode, result.stdout.decode('utf-8'),
                                       result.stderr.decode('utf-8', errors='replace'))


def checkout(path: Path) -> Path:
    root = path.resolve(strict=True)
    actual = Path(git(root, 'rev-parse', '--show-toplevel').stdout.strip()).resolve()
    if actual != root:
        raise ValueError(f'expected a checkout root: {path}')
    return root


def safe_path(path: Path, boundary: Path) -> Path:
    """Reject path escape, symlink and junction traversal, including dangling links."""
    path = Path(os.path.abspath(path))
    if not path.is_relative_to(boundary):
        raise ValueError(f'path outside declared root: {path}')
    for entry in (path, *path.parents):
        if entry.is_symlink() or entry.is_junction():
            raise ValueError(f'linked path: {entry}')
        if entry == boundary:
            break
    if not path.resolve().is_relative_to(boundary):
        raise ValueError(f'path outside declared root: {path}')
    return path


def relative_path(root: Path, name: str) -> Path:
    value = Path(name)
    if not value.parts or value.anchor or '..' in value.parts:
        raise ValueError(f'expected a repository-relative path: {name}')
    return safe_path(root / value, root)


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError(f'expected a JSON object: {path}')
    return data


def json_text(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def tracked_paths(root: Path) -> set[str]:
    return set(git(root, 'ls-files', '--cached', '-z').stdout.rstrip('\0').split('\0')) - {''}


def atomic_write(path: Path, new: bytes, *, previous: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f'.{path.name}.', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(new)
    try:
        if path.read_bytes() != previous:
            raise RuntimeError(f'document changed during refresh: {path}')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
