"""Check staged Python and frontend content with the repository's linters."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

if __package__:
    from .git_index import index_bytes, staged_changes
else:
    from git_index import index_bytes, staged_changes


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = Path('apps/frontend')
OX_CONFIG = FRONTEND / '.oxlintrc.json'
OX_PLUGIN = FRONTEND / 'scripts/anti-slop.mjs'
RUFF_CONFIG = Path('backend/pyproject.toml')
PYTHON_ROOTS = (Path('backend/app'), Path('tools/audit'))


def staged_copy(target: Path, files: list[Path]) -> None:
    for rel in files:
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(index_bytes(ROOT, ROOT / rel))


def main() -> int:
    files = [path.relative_to(ROOT) for path, status in staged_changes(ROOT).items() if status != 'D']
    py = [path for path in files if path.suffix == '.py' and any(path.is_relative_to(d) for d in PYTHON_ROOTS)]
    ts = [path for path in files if path.suffix in {'.ts', '.tsx'} and path.is_relative_to(FRONTEND)]
    if not py and not ts:
        return 0
    failed = False
    with TemporaryDirectory(prefix='mtrl-staged-lint-') as directory:
        target = Path(directory)
        if py:
            staged_copy(target, [RUFF_CONFIG, *py])
            ruff = Path(sys.executable).with_name('ruff.exe' if os.name == 'nt' else 'ruff')
            failed |= subprocess.run(
                [str(ruff), 'check', '--no-cache', '--ignore-noqa', '--config', str(RUFF_CONFIG), '--',
                 *(str(path) for path in py)], cwd=target, check=False,
            ).returncode != 0
        if ts:
            staged_copy(target, [OX_CONFIG, OX_PLUGIN, *ts])
            entry = ROOT / FRONTEND / 'node_modules/oxlint/bin/oxlint'
            failed |= subprocess.run(
                ['node', str(entry), '--deny-warnings', '--config', '.oxlintrc.json',
                 '--', *(str(path.relative_to(FRONTEND)) for path in ts)], cwd=target / FRONTEND, check=False,
            ).returncode != 0
    return int(failed)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'Staged lint could not finish: {exc}', file=sys.stderr)
        raise SystemExit(2) from None
