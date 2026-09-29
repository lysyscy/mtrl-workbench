"""给用户开一个**留着不拆**的 8001 实例（指向**空库**＝测试库），用来点预演第 3 步的四个入口。

⚠️ 与 `_m8_rehearse2.py` 的区别：那个是"起了就拆"（自动化验证）；这个是**留给人在浏览器里点**的 ⇒ 不拆 ✓。
   停法：`… _m8_serve8001.py --stop`（读 `logs/rehearsal-8001.pid` 杀）。

安全：① 只连 `TEST_DATABASE_URL`（库名必须含 `_test`，否则停手）；② ⛔ **不碰** 8000 上的现役服务；
     ③ 进程**独立于本命令**（`DETACHED_PROCESS`），命令返回后它仍在跑 ✓ —— 所以**必须记 PID** 才能收掉。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
PORT = 8001
BASE = f"http://127.0.0.1:{PORT}"
LOG = ROOT / "logs" / "rehearsal-8001.log"
PID = ROOT / "logs" / "rehearsal-8001.pid"
DETACHED = 0x00000008 | 0x00000200          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def read_env() -> dict[str, str]:
    d: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def probe(url: str, timeout: float = 3.0) -> int:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:      # noqa: S310
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main() -> int:
    if "--stop" in sys.argv:
        if not PID.exists():
            print("（没有 PID 文件 ⇒ 可能已经不在跑）"); return 0
        pid = PID.read_text().strip()
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)   # noqa: S603,S607
        PID.unlink(missing_ok=True)
        time.sleep(2)
        print(f"已停 PID {pid} ⇒ 8001 {'仍被占 ⛔' if probe(BASE, 2) else '已释放 ✓'}")
        return 0

    env = read_env()
    url = env.get("TEST_DATABASE_URL", "")
    dbname = url.rsplit("/", 1)[-1].split("?")[0] if url else ""
    print("=== 开一个留给浏览器点的 8001 实例（指向**空库**）===")
    if not url or "_test" not in dbname:
        print(f"⛔ 安全闸：`TEST_DATABASE_URL` 缺失或库名不含 `_test`（当前 `{dbname}`）⇒ 停手"); return 2
    if probe(f"{BASE}/app") == 200:
        print(f"   ℹ️ 8001 上**已经有**一个在跑（可能是上一次留的）⇒ 直接用 {BASE}/app"); return 0
    print(f"  库 = {dbname}（口令已遮）⛔ 不碰 8000 现役服务")

    LOG.parent.mkdir(exist_ok=True)
    e2 = dict(os.environ, DATABASE_URL=url, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    with LOG.open("w", encoding="utf-8") as f:
        proc = subprocess.Popen(                                                     # noqa: S603
            [str(PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT),
             "--log-level", "warning"],
            cwd=str(ROOT / "backend"), env=e2, stdout=f, stderr=subprocess.STDOUT,
            creationflags=DETACHED)
    PID.write_text(str(proc.pid), encoding="utf-8")
    for _ in range(40):
        if probe(f"{BASE}/app") == 200:
            print("\n  ✅ 起来了 · 留着不拆（命令返回后它仍在跑）")
            print(f"     ⭐ 用浏览器开：{BASE}/app")
            print(f"     PID = {proc.pid} · 日志 = logs/{LOG.name}")
            print(f"     停法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_m8_serve8001.py --stop`")
            print("     ⛔ 它只写**测试库**（空库）；⛔ 8000 上的现役服务没动")
            return 0
        time.sleep(1)
    print("  ⛔ 40s 内没起来 ⇒ 看 logs/rehearsal-8001.log")
    print("     " + ((LOG.read_text(encoding='utf-8', errors='replace').strip().splitlines() or ['（无输出）'])[-1])[:200])
    return 1


if __name__ == "__main__":
    sys.exit(main())
