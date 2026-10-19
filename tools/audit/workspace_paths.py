"""开发运行输出：每进程一轮；子进程沿用父轮，结束归档有限证据。"""
from __future__ import annotations

import atexit
from datetime import date, timedelta, datetime
import os
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'var/state/verification'
_owned: dict[Path, Path] = {}
_owns_run = False


def _no_links(path: Path, root: Path) -> None:
    for parent in [path, *path.parents]:
        if parent.is_symlink() or parent.is_junction():
            raise ValueError('输出路径含链接')
        if parent == root:
            break


def output_dir(kind: str = 'reports', *, root: Path = ROOT) -> Path:
    global _owns_run
    if kind not in {'reports', 'logs', 'screenshots', 'traces', 'exports', 'work', 'recovery'}:
        raise ValueError('未知开发输出类型')
    effort = os.environ.get('MTRL_EFFORT', 'checks-' + date.today().strftime('%Y%m%d'))
    run = os.environ.get('MTRL_RUN_ID')
    if run is None:
        run = datetime.now().strftime('%H%M%S-%f') + '-' + str(os.getpid())
        os.environ['MTRL_RUN_ID'] = run
        _owns_run = True
    for value in (effort, run):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', value):
            raise ValueError('effort/run 必须是安全的短标识')
    base = root / '.artifacts/active' / effort / run
    _no_links(base, root)
    if _owns_run:
        _owned[base] = root
    target = base / kind
    target.mkdir(parents=True, exist_ok=True)
    return target


def output(name: str, *, kind: str = 'reports', root: Path = ROOT) -> Path:
    rel = Path(name)
    if rel.is_absolute() or '..' in rel.parts or ':' in name or '\\' in name:
        raise ValueError('输出名不得越界')
    target = output_dir(kind, root=root) / rel
    _no_links(target, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def close_runs() -> None:
    """只收本进程创建的轮次；临时 work 释放，实际结果保留最多30天。"""
    import json
    for base, root in list(_owned.items()):
        if not base.exists():
            _owned.pop(base)
            continue
        if any(p.is_symlink() or p.is_junction() for p in [base, *base.rglob('*')]):
            raise ValueError('输出含链接，保留现场待查')
        if (base / 'work').exists():
            shutil.rmtree(base / 'work')
        for p in sorted(base.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if p.is_dir() and not any(p.iterdir()):
                p.rmdir()
        if any(base.iterdir()):
            archive = root / '.artifacts/archive' / base.parent.name
            _no_links(archive, root)
            archive.mkdir(parents=True, exist_ok=True)
            retention = archive / 'retention.json'
            if not retention.exists():
                retention.write_text(json.dumps({
                    'reason': '开发工具生成的核验输出，供近期验收与失败复查；不含运行凭据或源码现场',
                    'expires_on': (date.today() + timedelta(days=30)).isoformat(),
                }, ensure_ascii=False, indent=2), encoding='utf-8')
            destination = archive / base.name
            if destination.exists():
                raise FileExistsError(destination)
            base.rename(destination)
        else:
            base.rmdir()
        if not any(base.parent.iterdir()):
            base.parent.rmdir()
        _owned.pop(base)


atexit.register(close_runs)
