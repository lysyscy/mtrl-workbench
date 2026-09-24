"""**反向灵敏度**（`MOD-06` 机械源接线）：证明 `test_wired_m06.py` 的断言真有区分力。

同 `_mut_m08wired.py`：逐条改坏 → 确认对应断言变红 → 全部复原（**MD5 逐字节**）。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH as SHELL, pick  # noqa: F401  ← `P4`① 读取点收敛
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
        # ⚠️ 2026-09-19（性能 `P3` 主体）：`boot()` **不再逐路拉**（改成"进哪页拉哪页"）⇒ 原锚点
        #    （`boot()` 里那句 `await reloadMech();`）**已不存在**（脚本会报 SKIP＝未验证）。
        #    改指**取数表**里的同一意图：`LOADERS` 里没有「机械 6 列」这一路 ⇒ MACH6 恒空 ⇒ 机械欠款恒 0。
        "M2 `boot()` 不再拉机械值（MACH6 恒空 ⇒ 机械欠款恒 0）",
        "  '机械 6 列': reloadMech,",
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
    # ⭐ 2026-09-23（`TAIL-76`）：补两条**壳侧** —— 这两条 claim 的原靶（`mech_ui._value_of` /
    #    `block_html`）随旧页 2026-09-18 删除 ⇒ 一度"改坏了也没人知道"。
    (
        "M5 录机械费不再回填该月现值（第二次打开变空盒 ⇒ 保存会把其余列清成 0）",
        "const vals=((MACH6[wh]||{})[ym]||[]);",
        "const vals=[];",
        "test_录机械费第二次打开要回填该月现值",
    ),
    (
        "M6 机械区块混进材料列输入面（§5.2.3 单向流被破）",
        '<div class="grid2">${MECH_LABELS.map((nm,i)=>`',
        '<div class="grid2"><input class="inp" id="in_0">${MECH_LABELS.map((nm,i)=>`',
        "test_机械录入口只送mech键_材料列没有输入面",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def main() -> int:
    before = (SHELL.read_bytes(), md5(SHELL))
    hit = 0
    for desc, old, new, case in MUTS:
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳已拆成多件（`web/shell/*.js`）⇒ **锚点在哪件就改哪件**；
        #    ⛔ 复原用**那一件的**原字节（`before[0]` 是 `index.html` 的 —— 写进 js 件会把件写坏）。
        sh = pick(SHELL, old, new)
        sh0 = sh.read_bytes()
        t = sh.read_text(encoding="utf-8")
        if t.count(old) != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {t.count(old)} 次（期望 1）⇒ **未验证**")
            continue
        sh.write_text(t.replace(old, new), encoding="utf-8", newline="\n")
        r = subprocess.run([str(PY), "-m", "pytest", "-q", f"{TEST}::{case}"],
                           cwd=str(ROOT / "backend"), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        red = r.returncode != 0
        sh.write_text(sh0.decode("utf-8"), encoding="utf-8", newline="\n")
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → `{case}` " + ("变红" if red else "**仍是绿的**"))
        hit += red

    ok = md5(SHELL) == before[1]
    print(f"\n  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 已复原' if ok else '❌ 没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
