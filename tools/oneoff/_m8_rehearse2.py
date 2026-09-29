"""M8 本机预演 **第 2 步**：临时在 **8001** 起第二实例（指向**刚建好的测试库**）⇒ 跑 `selfcheck` ⇒ **当场拆掉**。

⭐ 验的是什么：**落地后头一件事**就是这个 ——「在一个刚迁完的空库上，`ops/selfcheck.ps1` 五项能不能全过」。

⚠️ 安全（三条，缺一条都不做）：
  ① 只指向 `TEST_DATABASE_URL`（库名必须含 `_test`，否则**停手**）；
  ② **不碰** 8000 上的现役服务（那是 NSSM 服务 `mtrl-workbench-server`，只在 8001 另起一个临时进程）；
  ③ 验完**一定杀**（`terminate` ＋ `taskkill /F` 兜底）并确认 8001 已释放。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_m8_rehearse2.py`
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
ENV = ROOT / ".env"
PORT = 8001
BASE = f"http://127.0.0.1:{PORT}"


def read_env() -> dict[str, str]:
    d: dict[str, str] = {}
    for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
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
    env = read_env()
    url = env.get("TEST_DATABASE_URL", "")
    if not url:
        print("⛔ 根 `.env` 没有 `TEST_DATABASE_URL` ⇒ 停手"); return 2
    dbname = url.rsplit("/", 1)[-1].split("?")[0]
    print(f"=== 预演第 2 步 · 8001 第二实例（库 = {dbname}，口令已遮）===")
    if "_test" not in dbname:
        print(f"⛔ 安全闸：库名 `{dbname}` 不含 `_test` ⇒ **停手**"); return 2
    if probe(f"http://127.0.0.1:8000/app") != 200:
        print("⚠️ 注意：8000 上的现役服务当前没在 200（本步不依赖它，只作参照）")

    e2 = dict(os.environ, DATABASE_URL=url, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    log = ROOT / "logs" / "rehearsal-8001.log"
    log.parent.mkdir(exist_ok=True)
    print(f"  起：uvicorn {BASE}（日志 → logs/{log.name}）")
    proc = subprocess.Popen(                                                     # noqa: S603
        [str(PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT),
         "--log-level", "warning"],
        cwd=str(ROOT / "backend"), env=e2, stdout=log.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT)
    try:
        ok = False
        for _ in range(40):                       # 最多等 ~40s（首次 import 慢）
            if probe(f"{BASE}/app") == 200:
                ok = True; break
            if proc.poll() is not None:
                break
            time.sleep(1)
        if not ok:
            print("  ⛔ 8001 没起来（/app 不是 200）⇒ 看 logs/rehearsal-8001.log")
            print("     " + (log.read_text(encoding='utf-8', errors='replace').strip().splitlines() or ['（无输出）'])[-1][:160])
            return 1
        print("  ✅ 8001 起来了（/app 200）")
        print("\n--- ops/selfcheck.ps1 -Base " + BASE + " ---")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(ROOT / "ops" / "selfcheck.ps1"), "-Base", BASE],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=str(ROOT))
        print(r.stdout or "")
        rc = r.returncode
        print(f"--- selfcheck rc = {rc} ---")
        return 0 if rc == 0 else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True)  # noqa: S603,S607
        time.sleep(2)
        print(f"  🧹 已拆：8001 现在 {'还占着 ⛔' if probe(BASE, 2) else '已释放 ✓'}"
              f"（⚠️ 8000 上的现役服务全程未碰）")


if __name__ == "__main__":
    sys.exit(main())
