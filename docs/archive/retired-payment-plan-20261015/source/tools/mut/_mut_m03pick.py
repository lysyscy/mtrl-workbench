"""**反向灵敏度**：证明 `test_wired_m03_pick.py`（`§19` 批 4 小轮④a 搬的 7 条壳侧断言）**真有区分力**。

做法：逐条把实现**改坏** → 确认**对应的那条断言变红** → 全部复原（**MD5 逐字节校验**）。
⚠️ 子进程必须设 `ACC_RESULTS_PATH`（否则每处变异把权威 `acc_results.json` 冲成单条）
   与 `PYTHONIOENCODING=utf-8`（否则 Windows 上 GBK 解码假红）—— 见 `_mut_m03list.py` 的说明。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH as SHELL, pick  # noqa: F401  ← `P4`① 读取点收敛
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_wired_m03_pick.py"

# (说明, 文件, 原文, 改成, 应变红的断言名)
MUTS: list[tuple[str, Path, str, str, str]] = [
    (
        "M1 命中判据丢掉 `ntPayCand`（剔除/撤单行也会被勾上）",
        SHELL,
        "NO.find(x=>x.code===c&&ntPayCand(x))",
        "NO.find(x=>x.code===c)",
        "test_壳里计划命中的行被预勾选",
    ),
    (
        "M2 单据年月不放宽（跨月单据勾不上）",
        SHELL,
        # ⚠️ 必须**替换**那一行，不能只在后面追加 —— 追加一行时原放宽行还在，断言仍然绿
        #    （2026-09-19 实测：这类"变异选错"会被脚本如实报成"未命中"，别误读成断言弱）。
        "fNt.month='全部'; fNt.cat='全部';",
        "fNt.month=ym; fNt.cat='全部';",
        "test_壳里跨月单据也能勾上",
    ),
    (
        "M3 被「项目」筛挡掉的行不报数",
        SHELL,
        "const cut=before-pickSet.size;",
        "const cut=0;",
        "test_壳里项目筛选不动且被挡的行要报数",
    ),
    (
        "M4 空单据号也去查（把「空号」当命中）",
        SHELL,
        "const n=c?NO.find(x=>x.code===c&&ntPayCand(x)):null;",
        "const n=NO.find(x=>x.code===c)||null;",
        "test_壳里空单据号不参与勾选",
    ),
    (
        "M5 按钮不再按窗口置灰（点了才拦）",
        SHELL,
        "data-act=\"planPick\" ${win.open?'':'disabled'}",
        "data-act=\"planPick\"",
        "test_壳里窗口外先禁用且点不了",
    ),
    (
        "M6 窗口外不再提前返回（会继续往下勾）",
        SHELL,
        # ⚠️ 这条守的是 001-06（「**不执行**」）⇒ 变异要拿掉 `return;`；
        #    "把 `if(!win.open)` 改名"属于 001-05（「先禁用」）那条，改错了会"未命中"（实测）。
        "暂不可勾选`,4800); return; }",
        "暂不可勾选`,4800); }",
        "test_壳里窗口外不执行并说明原因",
    ),
    (
        "M7 月份写死（不再取窗口算出的当月）",
        SHELL,
        "const ym=win.ym;",
        "const ym='2026-09';",
        "test_壳里计划单据号来自当月且月份不可自选",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(case: str) -> bool:
    env = {**os.environ,
           "ACC_RESULTS_PATH": "../artifacts/_mut_acc_results.json",
           "PYTHONIOENCODING": "utf-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", f"{TEST}::{case}"],
        cwd=str(ROOT / "backend"), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env,
    )
    return r.returncode == 0


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old, new, case in MUTS:
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳已拆成多件（`web/shell/*.js`）⇒ 锚点在哪件就改哪件。
        path = pick(path, old, new)
        before.setdefault(path, (path.read_bytes(), hashlib.md5(path.read_bytes()).hexdigest()))
        t = path.read_text(encoding="utf-8")
        if t.count(old) != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {t.count(old)} 次（期望 1）⇒ **未验证**")
            continue
        path.write_text(t.replace(old, new), encoding="utf-8", newline="\n")
        red = not run_one(case)
        path.write_text(before[path][0].decode("utf-8"), encoding="utf-8", newline="\n")
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → `{case}` " + ("变红" if red else "**仍是绿的**"))
        hit += red

    print()
    ok = all(md5(p) == h for p, (_, h) in before.items())
    print(f"  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
