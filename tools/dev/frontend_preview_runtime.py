"""Register and verify local real-copy previews across worktrees."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_PREVIEW_PORTS = (8065, 8066, 8067)
MAX_CONCURRENT_PREVIEWS = 3
DISPOSABLE_SCHEMA_PREFIX = 'frontend_rewrite_397_'


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def state_dir(root=None):
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root or ROOT, capture_output=True, encoding="utf-8", check=True).stdout.strip()
    return Path(common).parent / "var/state/react-writable-preview"


def _registry_directory(root):
    return state_dir() if root is None else state_dir(root)


def process_identity(pid):
    if sys.platform == "win32":
        script = ("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
                  f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}'; "
                  "if($p){@{pid=$p.ProcessId;created=$p.CreationDate.ToFileTimeUtc().ToString();command=$p.CommandLine}|ConvertTo-Json -Compress}")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True, encoding="utf-8", check=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        return json.loads(result.stdout) if result.stdout.strip() else None
    try:
        base = Path("/proc") / str(int(pid))
        stat = (base / "stat").read_text().rsplit(")", 1)[1].split()
        if stat[0] == 'Z':
            return None
        return dict(pid=int(pid), created=stat[19], command=(base / "cmdline").read_bytes().replace(b"\0", b" ").decode())
    except FileNotFoundError:
        return None


def live_process(owner):
    expected = owner.get("process")
    if not expected:
        return False
    actual = process_identity(expected["pid"])
    if actual and actual['created'] == expected['created'] and actual != expected:
        raise RuntimeError(f"无法核实预览进程 {expected['pid']} 的命令身份")
    return bool(actual and actual == expected)


def listening(port):
    with socket.socket() as probe:
        probe.settimeout(.5)
        return probe.connect_ex(("127.0.0.1", int(port))) == 0


def validate_port(port):
    if port not in ALLOWED_PREVIEW_PORTS:
        raise ValueError(f'预览端口须为 8065、8066 或 8067，收到 {port}')
    return port


def root_key(root):
    return Path(root).resolve().as_posix().casefold()


def slot_key(root):
    name = re.sub(r'[^a-z0-9-]+', '-', Path(root).resolve().name.casefold()).strip('-') or 'worktree'
    digest = hashlib.sha256(root_key(root).encode('utf-8')).hexdigest()[:16]
    return f'{name[:48]}-{digest}'


@contextmanager
def _file_lock(path, *, wait=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait
    with path.open('a+b') as lock:
        while True:
            lock.seek(0)
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f'预览锁已被占用：{path.name}') from None
                time.sleep(.02)
        try:
            yield
        finally:
            lock.seek(0)
            if sys.platform == 'win32':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def _read_optional(path):
    try:
        return read_json(path)
    except FileNotFoundError:
        return None


@dataclass(frozen=True)
class PreviewRegistration:
    pointer: Path
    path: Path
    owner: dict

    @property
    def legacy(self):
        return self.pointer.name == 'current.json'

    def matches_root(self, root, *, allow_unspecified=False):
        source = self.owner.get('source_root')
        return root_key(source) == root_key(root) if source else self.legacy and allow_unspecified

    def summary(self):
        owner = self.owner
        return dict(slot=owner.get('slot') or 'legacy', worktree=owner.get('source_root'),
                    port=owner.get('port'), pid=(owner.get('process') or {}).get('pid'),
                    run=self.path.parent.parent.name, schema=owner.get('schema'),
                    started_at=owner.get('started_at'), owner_path=str(self.path),
                    kind='disposable' if owner.get('disposable') is True else 'existing',
                    status=owner.get('status'))


def _registration(pointer):
    saved = _read_optional(pointer)
    if saved is None:
        return None
    path = Path(saved['owner_path'])
    owner = _read_optional(path) or {}
    process = saved.get('process')
    if pointer.name == 'current.json' and process is None:
        process = owner.get('process')
    if not process or not process.get('pid') or not process.get('created'):
        raise RuntimeError(f'无法确认预览登记的进程身份：{pointer}')
    if owner.get('process') != process:
        owner = {'status': 'starting'}
    return PreviewRegistration(pointer, path, {**owner, **saved, 'process': process})


def _registrations(directory):
    paths = [*sorted((directory / 'instances').glob('*.json')), directory / 'current.json']
    return [entry for path in paths if (entry := _registration(path)) is not None]


def _partition(entries):
    live, stale, processes = [], [], set()
    for entry in entries:
        process = entry.owner['process']
        if not live_process(entry.owner):
            stale.append(entry)
            continue
        key = (process['pid'], process['created'])
        # The legacy pointer and a slot can refer to the same server. A reused
        # owner path alone cannot disqualify a separately confirmed live PID.
        if key not in processes:
            live.append(entry)
            processes.add(key)
    return live, stale


def preview_inventory(*, root=None):
    """Read-only inventory. A pending startup counts against the same cap."""
    return _partition(_registrations(_registry_directory(root)))


@contextmanager
def _checked_registry(directory):
    # CIM lookups on Windows can take seconds. Check the snapshot outside the
    # mutex and retry if a reservation or owner changed before the update.
    for _ in range(8):
        entries = _registrations(directory)
        live, stale = _partition(entries)
        with _file_lock(directory / 'registry.lock', wait=3):
            if entries == _registrations(directory):
                yield live, stale
                return
    raise RuntimeError('预览登记持续变化，请重试')


def describe_preview(entry):
    item = entry.summary()
    return (f"{item['slot']} | worktree={item['worktree']} | port={item['port']} | PID={item['pid']} | "
            f"run={item['run']} | {item['kind']} | schema={item['schema']} | "
            f"started_at={item['started_at']} | {item['status']} | owner_path={item['owner_path']}")


def _reap(stale, *, legacy=False):
    removed = []
    for entry in stale:
        if legacy or not entry.legacy:
            entry.pointer.unlink(missing_ok=True)
            removed.append(entry.pointer.name)
    return removed


@contextmanager
def reserve_preview(port, path, *, schema, disposable, root=None):
    """Reserve the worktree, port and schema before preparing the database."""
    validate_port(port)
    directory = _registry_directory(root)
    root = Path(root or ROOT).resolve()
    slot = slot_key(root)
    path = Path(path).resolve()
    pointer = directory / 'instances' / f'{slot}.json'
    process = process_identity(os.getpid())
    if not process:
        raise RuntimeError('无法确认当前预览进程身份')
    saved = dict(owner_path=str(path), process=process, source_root=str(root), port=port, slot=slot,
                 schema=schema, disposable=disposable, preserve_schema_on_stop=not disposable,
                 started_at=datetime.now(timezone.utc).isoformat())
    stop = path.parent / 'stop-request.json'
    with _file_lock(directory / 'slots' / f'{slot}.lock'):
        with _checked_registry(directory) as (live, stale):
            _reap(stale)
            if len(live) >= MAX_CONCURRENT_PREVIEWS:
                raise RuntimeError(f'全仓预览已达 {MAX_CONCURRENT_PREVIEWS} 个上限：\n' +
                                   '\n'.join(map(describe_preview, live)))
            for entry in live:
                if entry.matches_root(root, allow_unspecified=True):
                    raise RuntimeError('本工作树登记预览进程仍存活：' + describe_preview(entry))
                if entry.owner.get('port') == port:
                    raise RuntimeError('预览端口已被占用：' + describe_preview(entry))
            stop.unlink(missing_ok=True)
            write_json(pointer, saved)
        try:
            yield saved
        finally:
            with _file_lock(directory / 'registry.lock', wait=3):
                if _read_optional(pointer) == saved:
                    pointer.unlink()
                if (_read_optional(stop) or {}).get('process') == process:
                    stop.unlink()


def prune_registrations(*, root=None):
    with _checked_registry(_registry_directory(root)) as (live, stale):
        return _reap(stale, legacy=True), live


def product_inputs(*, frontend_only=False):
    """Declared input paths, including currently absent files and tracked deletions."""
    roots = ["apps/frontend/src", "apps/frontend/public", "apps/frontend/patches"]
    files = [
        "apps/frontend/index.html", "apps/frontend/package.json", "pnpm-lock.yaml",
        "apps/frontend/pnpm-lock.yaml", "apps/frontend/pnpm-workspace.yaml",
        "apps/frontend/vite.config.ts", "apps/frontend/tsconfig.json",
    ]
    if not frontend_only:
        roots += ["backend/app", "backend/alembic"]
        files += [
            "tools/dev/frontend_preview.py", "tools/dev/frontend_preview_browser_check.py",
            "tools/dev/frontend_preview_copy.py", "tools/dev/frontend_preview_runtime.py",
            "tools/dev/frontend_preview_server.py", "backend/pyproject.toml", "backend/uv.lock",
            "tools/audit/workspace_paths.py", "tools/artifact_lifecycle.py",
            "tools/_vendor/setup_solo_workflow/artifact_lifecycle.py",
            "tools/_vendor/setup_solo_workflow/deployment.json", "ops/frontend_release.py",
        ]
    return roots, files


def product_sources(*, frontend_only=False, root=None):
    root = Path(root or ROOT).resolve()
    roots, files = product_inputs(frontend_only=frontend_only)
    paths = {root / name for name in files if (root / name).is_file()}
    for name in roots:
        paths.update(p for p in (root / name).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"})
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def verify_build(version, *, check_sources=True, root=None):
    from tools.audit.workspace_paths import owned_work
    source_root = Path(root or ROOT).resolve()
    build = owned_work(Path(version["build_path"]), root=source_root)
    if check_sources and version.get("frontend_sources") != product_sources(frontend_only=True, root=source_root):
        raise RuntimeError("构建的前端输入已变化，须离线重新构建")
    for name, digest in version["files"].items():
        asset = owned_work(build / name, root=source_root)
        if not asset.is_relative_to(build) or hashlib.sha256(asset.read_bytes()).hexdigest() != digest:
            raise RuntimeError("构建资源散列不符")
    return build


def _select_preview(*, port=None, root=None, allow_unspecified=False):
    if port is not None:
        validate_port(port)
        live, _ = preview_inventory(root=root)
        for entry in live:
            if entry.owner.get('port') == port:
                return entry
    else:
        directory = _registry_directory(root)
        source = Path(root or ROOT).resolve()
        for pointer in (directory / 'instances' / f'{slot_key(source)}.json', directory / 'current.json'):
            entry = _registration(pointer)
            if (entry and entry.matches_root(source, allow_unspecified=allow_unspecified)
                    and live_process(entry.owner)):
                return entry
    selected = f'端口 {port}' if port is not None else str(Path(root or ROOT).resolve())
    raise RuntimeError(f'没有登记的真实副本预览：{selected}')


def _verify_active(owner):
    import httpx
    if (owner.get("status") != "ready" or owner.get("synthetic") is not False
            or owner.get("host") != "127.0.0.1" or owner.get("database") != "mtrl_workbench_test"
            or not owner.get("schema") or owner["schema"] == "public"):
        raise RuntimeError("预览身份、真实副本来源或进程不符")
    base = f"http://127.0.0.1:{validate_port(owner['port'])}"
    response = httpx.get(base + "/visual-version", timeout=10, trust_env=False)
    response.raise_for_status()
    live = response.json()
    for key in ["schema", "revision", "cookie_name", "index_sha256", "product_digest"]:
        if live.get(key) != owner.get(key):
            raise RuntimeError("HTTP实例与登记owner不符：" + key)
    if live.get("synthetic") is not False:
        raise RuntimeError("浏览器只能使用真实数据库副本")
    return base


def active_preview(*, port=None, root=None):
    """Verify immutable live ownership, independent of a prepared replacement build."""
    entry = _select_preview(port=port, root=root, allow_unspecified=True)
    return entry.path, entry.owner, _verify_active(entry.owner)


def registered_preview(*, require_latest=True, port=None, root=None):
    """Tests attach to the same verified current product/build, never create a server."""
    import httpx
    path, owner, base = active_preview(port=port, root=root)
    source_root = Path(owner.get('source_root') or root or ROOT).resolve()
    version = read_json(path.parent / 'version.json')
    verify_build(version, check_sources=require_latest, root=source_root)
    if require_latest and owner.get('product_sources') != product_sources(root=source_root):
        raise RuntimeError('运行后端产品输入已变化，须更新本工作树预览')
    html = httpx.get(base + '/preview', timeout=10, trust_env=False)
    if hashlib.sha256(html.content).hexdigest() != version['files']['index.html']:
        raise RuntimeError("实际HTML与完整构建不符")
    return path, owner, base


def request_stop(*, port=None, root=None, target=None):
    entry = target if target is not None else _select_preview(port=port, root=root)
    owner = entry.owner
    port = validate_port(owner['port'])
    if owner.get('status') == 'ready':
        _verify_active(owner)
    elif owner.get('status') != 'starting' or entry.legacy:
        raise RuntimeError('无法确认预览处于可停止状态')
    directory = entry.pointer.parent if entry.legacy else entry.pointer.parent.parent
    with _file_lock(directory / 'registry.lock', wait=3):
        current = _registration(entry.pointer)
        if current is None or current.path != entry.path or current.owner['process'] != owner['process']:
            raise RuntimeError('预览实例已切换，未发送停止请求')
        write_json(entry.path.parent / 'stop-request.json', {'process': owner['process']})
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if not live_process(owner) and not listening(port):
            return
        time.sleep(.2)
    raise RuntimeError(f'端口 {port} 的预览未按时退出')


def assert_same_preview(expected, current, *, disposable=False):
    keys=['process','schema','database','revision','cookie_name','product_digest','index_sha256']
    if any(expected.get(key)!=current.get(key) for key in keys):
        raise RuntimeError('预览实例已切换，拒绝把旧验证授权用于新实例')
    if disposable and not (current.get('disposable') is True and current.get('preserve_schema_on_stop') is False
                           and current.get('synthetic') is False and current.get('schema','').startswith('frontend_rewrite_397_')):
        raise RuntimeError('写入验证只允许同一已核可丢弃真实副本，用户试用数据保持受保护')
