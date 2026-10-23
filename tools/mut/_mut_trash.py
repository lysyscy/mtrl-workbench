'**反向灵敏度**：证明「回收站」那条断言（`ACC-USR-MGMT-001/001-09` 的界面那一半）**真有区分力**。\n\n用法：`backend/.venv/Scripts/python.exe tools/_mut_trash.py`\n'
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

CASE = "tests/test_acc_usr_mgmt.py::test_软删的账号仍带出到界面_且在回收站里单独可见可恢复"


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
    return None, None


MUTS = [
    ("M1 后端把已删账号**过滤掉**（回收站会永远空、计数恒 0）", API_PY,
     _b("    users = R.all_users(s)"),
     _b("    users = [x for x in R.all_users(s) if not D.is_deleted(x)]"),
     "① `_payload` 仍在带出已删账号"),
    ("M2 计数写死 0（列表里有已删行、数字却说没有）", API_PY,
     _b('            "deleted": sum(1 for u in users if D.is_deleted(u)),'),
     _b('            "deleted": 0,'),
     "① 计数与列表同源"),
    ("M3 不挂渲染后钩子（回收站**根本不会被调用**）", CORE_JS,
     _b("BIND.m15 = m15Trash;\n"),
     _b(""),
     "② 挂钩子 `BIND.m15`"),
    ("M4 搬行改成按**中文文本**匹配（壳里再造一份判据）", CORE_JS,
     _b("""  const rows = [...view.querySelectorAll('[data-act="userRestore"]')].map(b => b.closest('tr'));"""),
     _b("""  const rows = [...view.querySelectorAll('tr')].filter(tr => /已删除/.test(tr.textContent));"""),
     "② 按 `userRestore` 按钮选行"),
    ("M5 改原型切片：让主表**过滤**掉已删除（本该靠搬 DOM）", SHELL,
     _b("    ${USERS.map(u=>`<tr class="),
     _b("    ${USERS.filter(u=>u.status!=='已删除').map(u=>`<tr class="),
     "② `V.m15` 切片未被改"),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(case: str) -> bool:
    env = {**os.environ,
           "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), "-m", "pytest", "-q", case], cwd=str(BE),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return r.returncode == 0


def main() -> int:
    paths = {m[1] for m in MUTS}
    before = {p: (p.read_bytes(), md5(p)) for p in paths}
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
