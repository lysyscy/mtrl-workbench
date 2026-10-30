"""开发运行输出：每进程一轮；子进程沿用父轮，结束归档有限证据。"""
from __future__ import annotations

import atexit
from datetime import date, timedelta, datetime
import os
from pathlib import Path
import re
import shutil
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'var/state/verification'
_owned: dict[Path, Path] = {}
_owns_run = False
_managed = {}


def _lifecycle():
    source = Path.home() / '.skills-manager/skills/setup-solo-workflow/scripts/artifact_lifecycle.py'
    spec = importlib.util.spec_from_file_location('mtrl_artifact_lifecycle', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = Path(os.environ.get('MTRL_LIFECYCLE_ROOT', str(Path.home() / 'AppData/Local/AgentArtifacts/projects/mtrl-workbench')))
    module.enrolled(target)
    return module, target


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
    inherited = os.environ.get('MTRL_LIFECYCLE_OUTPUT')
    if root == ROOT and (inherited or _owns_run):
        module, managed_root = _lifecycle()
        if inherited:
            base = Path(inherited)
            expected = managed_root / 'groups' / run / 'files'
            if base != expected:
                raise ValueError('继承的生命周期输出身份不符')
            module.safe(base)
            _, _, record = module.load(managed_root, run)
            if record['state'] != 'active' or record['hold']:
                raise ValueError('输出轮次已结束或暂缓，不能继续写入')
        else:
            base = Path(module.register(managed_root, run, effort, '开发工具运行证据；用途结束后复查', 'evidence'))
            lease = module.lock(managed_root)
            lease.__enter__()
            os.environ['MTRL_LIFECYCLE_OUTPUT'] = str(base)
            _managed[base] = (module, managed_root, run, lease)
        target = base / kind
        module.safe(target)
        target.mkdir(parents=True, exist_ok=True)
        return target
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


def close_runs(*, success: bool = True) -> None:
    """只收本进程创建的轮次；临时 work 释放，实际结果保留最多30天。"""
    import json
    global _owns_run
    managed_ids = [entry[2] for entry in _managed.values()]
    for base, (module, managed_root, run, lease) in list(_managed.items()):
        module.inventory(base)
        if success and (base / 'work').exists():
            shutil.rmtree(base / 'work')
        # The group is still active when the write lease is released. A concurrent
        # sweeper cannot delete it before the atomic close/hold below.
        lease.__exit__(None, None, None)
        if not success:
            _, _, record = module.load(managed_root, run)
            if not record['hold']:
                module.hold(managed_root, run, '生产者失败或未明确结束；保留现场', '核实运行结果、活动消费者及永久依据后结项')
        else:
            # Only the owning producer calls this after its consumers have exited.
            module.close(managed_root, run)
        _managed.pop(base)
    if os.environ.get('MTRL_RUN_ID') in managed_ids:
        os.environ.pop('MTRL_RUN_ID', None)
        os.environ.pop('MTRL_LIFECYCLE_OUTPUT', None)
        _owns_run = False
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


def finish_run(code=0):
    """Seal an explicitly finished CLI run while preserving its original exit code."""
    close_runs(success=code in (None, 0))
    return code


def _exit_runs():
    # Process exit alone is not evidence that a business/verification run finished.
    close_runs(success=False)


atexit.register(_exit_runs)
