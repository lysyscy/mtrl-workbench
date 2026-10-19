"""**反向灵敏度**：证明「未登录 ⇒ 无身份」那条断言（`ACC-USR-MGMT-001/001-01`）**真有区分力**。

做法：逐条把实现**改坏** → 确认对应断言变红 → 全部复原（**MD5 逐字节校验**）。
⚠️ 一律走 bytes（`index.html` 是 CRLF、`.py` 是 LF）；还原用**原 bytes**。
⚠️ 子进程必须设 `ACC_RESULTS_PATH`，跑完**必须再跑一次全套 pytest**。

用法：`backend/.venv/Scripts/python.exe tools/_mut_auth.py`
"""
from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
sys.path.insert(0, str(ROOT / "tools"))
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH, pick  # noqa: E402

PY = BE / ".venv" / "Scripts" / "python.exe"
API_PY = ROOT / "backend" / "app" / "mod15_user" / "api.py"
CORE_JS = ROOT / "backend" / "app" / "web" / "shell" / "core.js"
SHELL = SHELL_PATH

CASE = "tests/test_acc_usr_login.py::test_当前登录用户是管理员且管理员恒一个"


def _b(s: str) -> bytes:
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


def _locate(src: bytes, frag_lf: bytes):
    for cand in (frag_lf, _fit(frag_lf, src)):
        if src.count(cand) >= 1:
            return src.count(cand), cand
    return 0, None


MUTS = [
    ("M1 ⭐ 把「回落到首个在用管理员」加回去（= 未登录的人自动变管理员）", API_PY,
     _b("""    who = current_name()  # 保留账号/旧标签类型；直接strip会丢掉新票的账号语义。
    if not who:
        return None
"""),
     _b("""    who = current_name()  # 保留账号/旧标签类型；直接strip会丢掉新票的账号语义。
    if not who:
        return D.active_admins(R.all_users(s))[0]
"""),
     "⓪ 没有会话 ⇒ `_me` 必须是 None"),
    ("M2 壳不再记录「后端答了但没身份」（两种情形显示同一句假话）", CORE_JS,
     _b("  WHO_STATE = me.id ? 'in' : 'none';\n"),
     _b(""),
     "④ 顶栏必须区分「未登录」与「取数失败」"),
    ("M3 顶栏不再按 `WHO_STATE` 分叉（同上，另一半）", SHELL,
     _b("    : (WHO_STATE==='none'\n"),
     _b("    : (false\n"),
     "④ 顶栏分叉"),
    ("M4 「没身份」时不给「去登录」的出口", SHELL,
     _b("""       ? `<span class="dot"></span>未登录 · <a class="link" href="/login">去登录</a>`"""),
     _b("""       ? `<span class="dot"></span>未登录`"""),
     "④ 有去登录的出口"),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(case: str) -> bool:
    env = {**os.environ, "ACC_RESULTS_PATH": str(_run_output('_mut_acc_results.json')),
           "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
           "PLAYWRIGHT_BROWSERS_PATH": r"C:\ProgramData\ms-playwright"}
    r = subprocess.run([str(PY), "-m", "pytest", "-q", case], cwd=str(BE),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return r.returncode == 0


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old_lf, new_lf, which in MUTS:
        first = old_lf.decode("utf-8").strip().split("\n")[0].strip()
        path = pick(path, first, old_lf.decode("utf-8"), new_lf.decode("utf-8"))
        src = path.read_bytes()
        n, cand = _locate(src, old_lf)
        if n != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {n} 次（期望 1）⇒ **未验证**")
            continue
        new = new_lf if cand == old_lf else _fit(new_lf, src)
        path.write_bytes(src.replace(cand, new, 1))
        red = not run_one(CASE)
        path.write_bytes(src)
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → {which} " + ("变红" if red else "**仍是绿的**"))
        hit += red
    print()
    ok = all(md5(p) == h for p, (_, h) in before.items())
    print(f"  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
