"""One registered local real-copy preview across worktrees and ports."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def state_dir():
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=ROOT, capture_output=True, encoding="utf-8", check=True).stdout.strip()
    return Path(common).parent / "var/state/react-writable-preview"


def process_identity(pid):
    if sys.platform == "win32":
        script = (f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}'; "
                  "if($p){@{pid=$p.ProcessId;created=$p.CreationDate.ToFileTimeUtc().ToString();command=$p.CommandLine}|ConvertTo-Json -Compress}")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True, encoding="utf-8", check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return json.loads(result.stdout) if result.stdout.strip() else None
    try:
        base = Path("/proc") / str(int(pid))
        stat = (base / "stat").read_text().rsplit(")", 1)[1].split()
        return dict(pid=int(pid), created=stat[19], command=(base / "cmdline").read_bytes().replace(b"\0", b" ").decode())
    except FileNotFoundError:
        return None


def live_process(owner):
    expected = owner.get("process")
    if not expected:
        return False
    actual = process_identity(expected["pid"])
    return bool(actual and actual == expected)


def listening(port):
    with socket.socket() as probe:
        probe.settimeout(.5)
        return probe.connect_ex(("127.0.0.1", int(port))) == 0


@contextmanager
def exclusive_preview():
    """Acquire before any persistent preview preparation; OS releases on exit/crash."""
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "instance.lock").open("a+b") as lock:
        try:
            if os.fstat(lock.fileno()).st_size == 0:
                lock.write(b"0"); lock.flush()
            lock.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("已有预览或副本操作占用唯一实例；先核身份并退出原实例") from None
        try:
            pointer = directory / "current.json"
            if pointer.exists():
                owner_path = Path(read_json(pointer)["owner_path"])
                if owner_path.exists() and live_process(read_json(owner_path)):
                    raise RuntimeError("登记预览进程仍存活，拒绝额外启动或副本写入")
            yield
        finally:
            lock.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_UN)


def product_sources(*, frontend_only=False):
    roots = ["apps/frontend/src", "apps/frontend/public"]
    files = ["apps/frontend/index.html", "apps/frontend/package.json", "pnpm-lock.yaml", "apps/frontend/pnpm-lock.yaml", "apps/frontend/vite.config.ts", "apps/frontend/tsconfig.json"]
    if not frontend_only:
        roots += ["backend/app", "backend/alembic"]
        files += ["tools/dev/frontend_preview.py", "tools/dev/frontend_preview_copy.py", "tools/dev/frontend_preview_runtime.py", "tools/dev/frontend_preview_server.py", "backend/pyproject.toml", "backend/uv.lock"]
    paths = {ROOT / name for name in files if (ROOT / name).is_file()}
    for name in roots:
        paths.update(p for p in (ROOT / name).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"})
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def verify_build(version, *, check_sources=True):
    build = Path(version["build_path"]).resolve()
    if not build.is_relative_to(ROOT / ".artifacts/active"):
        raise RuntimeError("构建不属于当前工作树活动运行")
    if check_sources and version.get("frontend_sources") != product_sources(frontend_only=True):
        raise RuntimeError("构建的前端输入已变化，须离线重新构建")
    for name, digest in version["files"].items():
        asset = (build / name).resolve()
        if not asset.is_relative_to(build) or hashlib.sha256(asset.read_bytes()).hexdigest() != digest:
            raise RuntimeError("构建资源散列不符")
    return build


def active_preview():
    """Verify immutable live ownership, independent of a prepared replacement build."""
    import httpx
    pointer = state_dir() / "current.json"
    if not pointer.exists():
        raise RuntimeError("没有登记的真实副本预览；先按预览指南准备唯一实例")
    path = Path(read_json(pointer)["owner_path"])
    owner = read_json(path)
    if (owner.get("status") != "ready" or owner.get("synthetic") is not False
            or owner.get("host") != "127.0.0.1" or owner.get("database") != "mtrl_workbench_test"
            or owner.get("schema") == "public" or not live_process(owner)):
        raise RuntimeError("预览身份、真实副本来源或进程不符")
    base = f"http://127.0.0.1:{owner['port']}"
    response = httpx.get(base + "/visual-version", timeout=10)
    response.raise_for_status()
    live = response.json()
    for key in ["schema", "revision", "cookie_name", "index_sha256", "product_digest"]:
        if live.get(key) != owner.get(key):
            raise RuntimeError("HTTP实例与登记owner不符：" + key)
    if live.get("synthetic") is not False:
        raise RuntimeError("浏览器只能使用真实数据库副本")
    return path, owner, base


def registered_preview(*, require_latest=True):
    """Tests attach to the same verified current product/build, never create a server."""
    import httpx
    path,owner,base=active_preview()
    version=read_json(path.parent / "version.json")
    verify_build(version,check_sources=require_latest)
    if require_latest and owner.get("product_sources") != product_sources():
        raise RuntimeError("运行后端产品输入已变化，须更新唯一实例")
    html=httpx.get(base+"/preview",timeout=10)
    if hashlib.sha256(html.content).hexdigest()!=version["files"]["index.html"]:
        raise RuntimeError("实际HTML与完整构建不符")
    return path,owner,base


def request_stop():
    path, owner, base = active_preview()
    write_json(path.parent / "stop-request.json", {"process": owner["process"]})
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if not live_process(owner) and not listening(owner["port"]):
            return
        time.sleep(.2)
    raise RuntimeError("预览未按时退出；保留数据与现场，拒绝启动另一实例")


def assert_same_preview(expected, current, *, disposable=False):
    keys=['process','schema','database','revision','cookie_name','product_digest','index_sha256']
    if any(expected.get(key)!=current.get(key) for key in keys):
        raise RuntimeError('预览实例已切换，拒绝把旧验证授权用于新实例')
    if disposable and not (current.get('disposable') is True and current.get('preserve_schema_on_stop') is False
                           and current.get('synthetic') is False and current.get('schema','').startswith('frontend_rewrite_397_')):
        raise RuntimeError('写入验证只允许同一已核可丢弃真实副本，用户试用数据保持受保护')
