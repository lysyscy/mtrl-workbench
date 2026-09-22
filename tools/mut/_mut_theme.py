"""**反向灵敏度**：证明 2026-09-21 那批主题断言（规范表 / 对比度 AA / 侧栏角色）**真有区分力**。

做法：逐条把实现**改坏** → 确认对应断言变红 → 全部复原（**MD5 逐字节校验**）。
⚠️ 一律走 bytes（`index.html` 是 CRLF、`.py` 是 LF）；还原用**原 bytes**（`write_text` 会把 CRLF 悄悄换成 LF ⇒ 假 BAD）。
⚠️ 子进程必须设 `ACC_RESULTS_PATH`，跑完**必须再跑一次全套 pytest**。

用法：`backend/.venv/Scripts/python.exe tools/_mut_theme.py`
"""
from __future__ import annotations

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
PAGE_PY = ROOT / "backend" / "app" / "mod03_notice" / "page.py"
SHELL = SHELL_PATH

T_CONTRAST = "tests/test_theme.py::test_每套主题的关键配对都过对比度AA"
T_SPEC = "tests/test_theme.py::test_主题清单恰好十套且每套都有适用场景与设计风格"
T_ROLE = "tests/test_theme.py::test_侧栏不借用与本角色无关的变量"


def _b(s: str) -> bytes:
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


def _locate(src: bytes, frag_lf: bytes):
    for cand in (frag_lf, _fit(frag_lf, src)):
        n = src.count(cand)
        if n >= 1:
            return n, cand
    return None


MUTS = [
    ("M1 ⭐ 选中项底改回「更暗的面板色」（深色套会变成黑字压近黑底 = 用户报的那个 bug）", PAGE_PY,
     _b('    v["--sb-on"] = pri'),
     _b('    v["--sb-on"] = _mix(sb, "#000000", 0.35)'),
     T_CONTRAST, "⭐侧栏-选中项"),
    ("M2 品牌/悬停项的字改暗（侧栏最亮那档塌掉）", PAGE_PY,
     _b('    v["--sb-hd"] = _mix(sb, "#ffffff", 0.94)'),
     _b('    v["--sb-hd"] = _mix(sb, "#3a3a3a", 0.5)'),
     T_CONTRAST, "⭐侧栏-品牌/悬停项"),
    ("M3 弱化文字退回 0.55（空态/提示又变成 2.8~3.0）", PAGE_PY,
     _b('        "--mut": _mix(tx, bg, 0.34),'),
     _b('        "--mut": _mix(tx, bg, 0.55),'),
     T_CONTRAST, "弱化文字"),
    ("M4 状态浅底改回朝 `bg` 混（浅色套的浅底偏暗 ⇒ 标签字读不清）", PAGE_PY,
     _b('        v[f"--{k}-l"] = _mix(c, face, 0.90 if not dark else 0.84)'),
     _b('        v[f"--{k}-l"] = _mix(c, bg, 0.90 if not dark else 0.84)'),
     T_CONTRAST, "标签-成功/提醒"),
    ("M5 只删规范表里的一条（场景/风格缺一套）", PAGE_PY,
     _b('    "高对比": {"scene": "弱视 / 强光环境 / 投影演示", "style": "纯黑白 ＋ 高饱和蓝主色，对比拉满"},\n'),
     _b(''),
     T_SPEC, "键集必须与种子表相同"),
    ("M6 清单多一套（11 套 ⇒ 违反「恰好 10 个独立方案」）", PAGE_PY,
     _b('    "靛青": {"bg": "#f2f3fb", "sf": "#ffffff", "tx": "#1b1830", "pri": "#4338ca"},\n'),
     _b('    "靛青": {"bg": "#f2f3fb", "sf": "#ffffff", "tx": "#1b1830", "pri": "#4338ca"},\n'
        '    "自检·第十一": {"bg": "#f0f0f0", "sf": "#ffffff", "tx": "#222222", "pri": "#334455"},\n'),
     T_SPEC, "恰好 10 套"),
    ("M7 ⭐ 壳里把侧栏品牌名改回借 `--on`（= 用户报的那个 bug 的原始写法）", SHELL,
     _b(".sb-brand b{display:block;color:var(--sb-hd);"),
     _b(".sb-brand b{display:block;color:var(--on);"),
     T_ROLE, "侧栏不许借 `--on`"),
    ("M8 壳里把侧栏编号改回借 `--in`（状态档的中性色，语义无关）", SHELL,
     _b(".sb-i .c{font-family:var(--fm);font-size:10.5px;color:var(--sb-mut);"),
     _b(".sb-i .c{font-family:var(--fm);font-size:10.5px;color:var(--in);"),
     T_ROLE, "侧栏不许借 `--in`"),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(case: str) -> bool:
    env = {**os.environ, "ACC_RESULTS_PATH": "../artifacts/_mut_acc_results.json",
           "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), "-m", "pytest", "-q", case], cwd=str(BE),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return r.returncode == 0


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old_lf, new_lf, case, which in MUTS:
        first = old_lf.decode("utf-8").strip().split("\n")[0].strip()
        path = pick(path, first, old_lf.decode("utf-8"), new_lf.decode("utf-8"))
        before.setdefault(path, (path.read_bytes(), md5(path)))
        src = path.read_bytes()
        found = _locate(src, old_lf)
        if found is None or found[0] != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {0 if found is None else found[0]} 次（期望 1）⇒ **未验证**")
            continue
        old = found[1]
        new = new_lf if old == old_lf else _fit(new_lf, src)
        path.write_bytes(src.replace(old, new, 1))
        red = not run_one(case)
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
