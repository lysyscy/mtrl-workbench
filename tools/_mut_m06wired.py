"""**反向灵敏度**（`MOD-06` 机械源接线）：证明 `test_wired_m06.py` 的断言真有区分力。

同 `_mut_m08wired.py`：逐条改坏 → 确认对应断言变红 → 全部复原（**MD5 逐字节**）。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_wired_m06.py"

MUTS: list[tuple[str, str, str, str]] = [
    (
        "M1 机械演示数组复活（页面显示演示值 ⇒ 与后端 KPI 打架）",
        "let MACH6 = {};",
        "const MACH6 = {};",
        "test_机械演示数组已删",
    ),
    (
        "M2 `boot()` 不再拉机械值（MACH6 恒空 ⇒ 机械欠款恒 0）",
        "    await reloadMech();",
        "",
        "test_机械值来自后端且boot会拉",
    ),
    (
        "M3 机械派生函数被改写法（本轮只该换来源）",
        "const mach6Arr=(wh,ym)=>(MACH6[wh]||{})[ym]||MACH6_Z;",
        "const mach6Arr=(wh,ym)=>(MACH6[wh]||{})[ym];",
        "test_机械结构未变_引用面一行未改",
    ),
    (
        "M4 `m05` 的机械结算退回取零出口（临时态复活）",
        ": N2(machSettleOf(k)",
        ": N2(m05MechSettle(k)",
        "test_m05的机械结算改用真源_且不再是取零出口",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def main() -> int:
    before = (SHELL.read_bytes(), md5(SHELL))
    hit = 0
    for desc, old, new, case in MUTS:
        t = SHELL.read_text(encoding="utf-8")
        if t.count(old) != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {t.count(old)} 次（期望 1）⇒ **未验证**")
            continue
        SHELL.write_text(t.replace(old, new), encoding="utf-8", newline="\n")
        r = subprocess.run([str(PY), "-m", "pytest", "-q", f"{TEST}::{case}"],
                           cwd=str(ROOT / "backend"), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        red = r.returncode != 0
        SHELL.write_text(before[0].decode("utf-8"), encoding="utf-8", newline="\n")
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → `{case}` " + ("变红" if red else "**仍是绿的**"))
        hit += red

    ok = md5(SHELL) == before[1]
    print(f"\n  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 已复原' if ok else '❌ 没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
