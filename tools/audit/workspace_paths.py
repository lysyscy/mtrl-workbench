"""开发运行输出：每进程一轮；子进程沿用父轮，结束归档有限证据。"""
from __future__ import annotations

import atexit
from datetime import date, timedelta, datetime
import os
from pathlib import Path
import re
import shutil
import importlib.util
import json
import sys
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SOURCE = ROOT / 'tools/_vendor/setup_solo_workflow/artifact_lifecycle.py'
STATE = ROOT / 'var/state/verification'
_owned: dict[Path, Path] = {}
_owns_run = False
_managed = {}
_borrowed = {}
_development = False
_abandonment_safe = False
_protection = None


def _lifecycle():
    source = RUNTIME_SOURCE
    if not source.is_file():
        raise RuntimeError('项目产物工具尚未部署，请通过setup部署固定版本')
    spec = importlib.util.spec_from_file_location('mtrl_artifact_lifecycle', source)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    target = Path(os.environ.get('MTRL_LIFECYCLE_ROOT', str(ROOT / '.artifacts/runs')))
    module.enrolled(target)
    config = module.configuration(target)
    if config.get('layout') == 'runs' and not Path(config['project']).samefile(ROOT):
        raise RuntimeError('产物区属于另一项目或工作树')
    return module, target


def development_run(*, abandonment_safe=False):
    """Opt in only at a verified disposable development entry, before output starts."""
    global _development, _abandonment_safe
    if _managed:
        raise RuntimeError('运行已经开始，不能补认可弃声明')
    _development = True
    # External subprocesses that do not join consume() cannot be proven finished
    # after their launcher dies. Only fully cooperating producers opt into this.
    _abandonment_safe = bool(abandonment_safe)


def protect_run(reason, condition):
    """A disposable test may still discover an unresolved resource/recovery outcome."""
    global _protection
    if not str(reason).strip() or not str(condition).strip():
        raise ValueError('须明确保护原因与解除条件')
    _protection = (str(reason), str(condition))


def _binding(module, managed_root, run, *, workspace=ROOT):
    config = module.configuration(managed_root)
    project_layout = config.get('layout') == 'runs'
    if project_layout:
        if not Path(config['project']).samefile(workspace):
            raise ValueError('产物区项目归属不符')
        name = run.name
    else:
        if run.name != 'files' or run.parent.parent.name != 'groups':
            raise ValueError('不是已登记运行的files目录')
        name = run.parent.name
    _, files, record = module.load(managed_root, name)
    if not files.samefile(run) or record['state'] not in {'active', 'closed'}:
        raise ValueError('运行归属或状态不符')
    if record.get('workspace') and not Path(record['workspace']).samefile(workspace):
        raise ValueError('运行属于另一工作树')
    return name, files, record


@contextmanager
def consume_run(path, *, root=None, writing=True):
    """Keep a build/preview consumer registered for its actual lifetime."""
    root = ROOT if root is None else root
    run = owned_run(path, root=root, writing=writing)
    if run.is_relative_to(root / '.artifacts/active'):
        yield run
        return
    module, managed_root = _lifecycle()
    name, files, _ = _binding(module, managed_root, run, workspace=root)
    if module.configuration(managed_root).get('layout') != 'runs':
        yield files
        return
    with module.consume(managed_root, name, writing=writing):
        yield files


def attach_run(path, *, root=None):
    """Bind an explicitly passed run in a child process without taking closure ownership."""
    root = ROOT if root is None else root
    run = owned_run(path, root=root, writing=True)
    if run.is_relative_to(root / '.artifacts/active'):
        os.environ.pop('MTRL_LIFECYCLE_OUTPUT', None)
        os.environ.update(MTRL_EFFORT=run.parent.name, MTRL_RUN_ID=run.name)
        return run
    module, managed_root = _lifecycle()
    name, files, _ = _binding(module, managed_root, run, workspace=root)
    os.environ.update(MTRL_RUN_ID=name, MTRL_LIFECYCLE_OUTPUT=str(files))
    if files not in _managed and files not in _borrowed and module.configuration(managed_root).get('layout') == 'runs':
        lease = module.consume(managed_root, name)
        lease.__enter__()
        _borrowed[files] = lease
    return files


def _no_links(path: Path, root: Path) -> None:
    for parent in [path, *path.parents]:
        if parent.is_symlink() or parent.is_junction():
            raise ValueError('输出路径含链接')
        if parent == root:
            break


def _checked_path(path: Path, root: Path) -> Path:
    path = Path(path)
    if '..' in path.parts:
        raise ValueError('运行路径不得包含父目录跳转')
    # Inspect the original spelling before resolve() removes junction/symlink evidence.
    absolute = Path(os.path.abspath(path))
    _no_links(absolute, Path(root).absolute())
    return absolute.resolve()


def owned_run(path: Path, *, root: Path = ROOT, writing: bool = False) -> Path:
    """Validate a legacy active run or a registered run in this project's output area.

    Enrollment and records remain owned by the installed lifecycle implementation.
    Held/closed evidence can be read, but cannot be reused for new output.
    """
    if path is None:
        raise RuntimeError('须指定已有运行归属 --run')
    run = _checked_path(path, root)
    if run.is_relative_to(Path(root).resolve() / '.artifacts/active'):
        return run
    try:
        module, managed_root = _lifecycle()
        managed_root = module.enrolled(managed_root)
        _, files, record = _binding(module, managed_root, run, workspace=root)
        if writing and (record['state'] != 'active' or record['hold']):
            raise ValueError('运行已结束或暂缓，不能继续写入')
    except (OSError, ValueError) as error:
        raise RuntimeError('运行未登记在本项目产物区，或归属/状态不可用') from error
    return files


def owned_work(path: Path, *, root: Path = ROOT, writing: bool = False) -> Path:
    """Validate a work descendant through the same run identity as its producer."""
    work = _checked_path(path, root)
    for parent in work.parents:
        if parent.name != 'work':
            continue
        try:
            run = owned_run(parent.parent, root=root, writing=writing)
        except RuntimeError:
            continue
        return run / 'work' / work.relative_to(parent)
    raise RuntimeError('构建不属于本项目已登记运行的work目录')


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
            name, base, record = _binding(module, managed_root, Path(inherited), workspace=root)
            if name != run:
                raise ValueError('继承的生命周期输出身份不符')
            module.safe(base)
            if record['state'] != 'active' or record['hold']:
                raise ValueError('输出轮次已结束或暂缓，不能继续写入')
            if base not in _managed and base not in _borrowed and module.configuration(managed_root).get('layout') == 'runs':
                lease = module.consume(managed_root, run)
                lease.__enter__()
                _borrowed[base] = lease
        else:
            development = _development and _abandonment_safe and module.configuration(managed_root).get('layout') == 'runs'
            base = Path(module.register(managed_root, run, effort, '开发工具运行证据', 'evidence',
                                        development=development, workspace=ROOT))
            lease = module.consume(managed_root, run)
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


def _cleanup_warning(base, error):
    value = {'ok': False, 'run': str(base), 'error': type(error).__name__,
             'message': '运行产物清理未完成，文件保留待重试；原操作结果保持不变'}
    print(json.dumps(value, ensure_ascii=False), file=sys.stderr)
    try:
        metadata = base / 'run.json' if (base / 'run.json').exists() else base.parent / 'record.json'
        if base not in _owned:
            _no_links(metadata, metadata.parent)
            if json.loads(metadata.read_text(encoding='utf-8')).get('state') != 'active':
                return value
        report = base / 'reports/cleanup.json'
        _no_links(report, base)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    except (OSError, ValueError):
        pass  # stderr remains the receipt if the output directory itself is unavailable.
    return value


def close_runs(*, success: bool = True):
    """Close owned runs; cleanup failure never rewrites the producer's outcome."""
    global _owns_run, _development, _abandonment_safe, _protection
    results = []
    for base, lease in list(_borrowed.items()):
        try:
            lease.__exit__(None, None, None)
        except (OSError, ValueError, RuntimeError) as error:
            results.append(_cleanup_warning(base, error))
        _borrowed.pop(base)
    managed_ids = [entry[2] for entry in _managed.values()]
    for base, (module, managed_root, run, lease) in list(_managed.items()):
        try:
            lease.__exit__(None, None, None)
            # Membership and deletion use one mutex; another consumer cannot join
            # between this idle check and work release/closure.
            with module.lock(managed_root):
                record_path, files, record = module.load(managed_root, run)
                if record['state'] != 'active':
                    raise RuntimeError('运行已关闭，保留现有文件')
                if _protection and not record['hold']:
                    record['hold'] = {'reason': _protection[0], 'condition': _protection[1],
                                      'review_at': (module.stamp() + timedelta(days=30)).isoformat()}
                    module.atomic(record_path, record)
                if record['hold']:
                    results.append({'ok': True, 'run': str(base), 'protected': True})
                    continue
                if module.consumption_state(record) != 'ended':
                    raise RuntimeError('运行仍有活动或无法核实的消费者')
                module.data_inventory(files, record)
                if success and (base / 'work').exists():
                    work = _checked_path(base / 'work', base)
                    if not work.is_relative_to(base.resolve()) or work == base.resolve():
                        raise ValueError('work目录越界')
                    shutil.rmtree(work)
                if success or _development or record.get('development') is True:
                    module.seal(record_path, files, record, module.stamp(),
                                result='success' if success else 'failure')
                elif not record['hold']:
                    record['hold'] = {'reason': '生产者失败或未明确结束；保留现场',
                                      'condition': '核实运行结果、活动消费者及永久依据后结项',
                                      'review_at': (module.stamp() + timedelta(days=30)).isoformat()}
                    module.atomic(record_path, record)
            results.append({'ok': True, 'run': str(base)})
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            results.append(_cleanup_warning(base, error))
        finally:
            _managed.pop(base)
    if os.environ.get('MTRL_RUN_ID') in managed_ids:
        os.environ.pop('MTRL_RUN_ID', None)
        os.environ.pop('MTRL_LIFECYCLE_OUTPUT', None)
        _owns_run = False
        _development = False
        _abandonment_safe = False
        _protection = None
    try:
        _close_legacy_runs()
    except (OSError, ValueError, RuntimeError) as error:
        for base in list(_owned):
            results.append(_cleanup_warning(base, error))
    return results


def _close_legacy_runs():
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
    if _managed and _development and not _abandonment_safe:
        protect_run('生产者未明确结束，外部消费者状态未核实', '确认所有外部进程与恢复用途已结束')
    close_runs(success=False)


atexit.register(_exit_runs)
