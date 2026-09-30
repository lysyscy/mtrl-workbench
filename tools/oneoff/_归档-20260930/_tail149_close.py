"""销号 `TAIL-149`（`ui_parity` 登记簿幽灵登记）—— 一次性脚本，带 `--check`。

跑法：`backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_tail149_close.py --check`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"

ROW = (
    "| `TAIL-149` | 🧹 **`ui_parity` 登记簿的「幽灵登记」**（`P0-c` 的副产品 · `TAIL-148` 起的账）："
    "登记了、当前却**没有对应漂移**的死条目 ⇒ 登记簿腐化（「已登记放行 N 行」会变成自我安慰）。"
    "实测已累到 **504 条**（条目 1112 · 活 608）⇒ 一次性脚本 `tools/oneoff/_prune_ghosts.py`："
    "⭐ **不另写判定** —— 直接 `import ui_parity` 用它的原语（`PROTO`/`read_lines`/`slices`/`read_shell`/"
    "`load_expected`/`fp`）复现它那 5 行幽灵判定；⛔ **只删条目行**、**注释 100 行一行未动**（本仓规矩："
    "别冲掉旁边的理由注释）；⛔ 不整份重写。登记簿 **1294 → 790 行**。 "
    "| 判据 = 复跑 `ui_parity` **rc=0** · **幽灵 0** · `U1` **无未登记漂移**（已登记放行 **608** 行 —— "
    "与删后条目数**正好对上**）· `U5` 43 件仍逐字一致 | 2026-09-29 |"
)

OPS: list[tuple] = [
    (PLAN, "rep", "| **随时**（⚠️ 5 分钟的人工活 —— 脚本**不替人删**，怕冲掉旁边的理由注释）",
     "| ✅ **已做（2026-09-29 · 留痕，别删）**—— 实测不是 23 条而是 **504 条**；"
     "一次性脚本 `tools/oneoff/_prune_ghosts.py`（判定与 `ui_parity` **同源** · **只删条目行** · 注释 100 行未动）："
     "登记簿 **1294 → 790 行**（条目 1112 → **608**） + 复跑 `ui_parity` **rc=0 / 幽灵 0 / U1 无未登记漂移** |"),
    (PLAN, "drop", ["| `TAIL-149` | 🧹 **`ui_parity` 登记簿 23 条幽灵登记**"], None),
    (PLAN, "ins_before", "| `TAIL-156` | 🧩 **`P2-c` 走查发现④", [ROW]),
    (PLAN, "rep", "A 类 **9** 条 · B 类 0 · C 类 **0** · 已销号 **158**",
     "A 类 **8** 条 · B 类 0 · C 类 **0** · 已销号 **159**"),
    (PLAN, "rep", "A 类 **9** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **158** 条",
     "A 类 **8** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **159** 条"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="销号 TAIL-149")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    t = PLAN.read_text(encoding="utf-8", newline="")
    crlf = "\r\n" in t
    lines = t.split("\n")
    bad = 0
    for _path, op, key, val in OPS:
        ln_all = "\n".join(lines)
        if op == "rep":
            idx = [i for i, ln in enumerate(lines) if key in ln]
            if val.rstrip("\r") in ln_all:
                print(f"  ⚠️ 已应用  {key[:44]}…")
                continue
            if len(idx) != 1:
                print(f"  ⛔ 命中 {len(idx)} 行  {key[:44]}…")
                bad += 1
                continue
            lines[idx[0]] = val + ("\r" if crlf else "")
            print(f"  ✅ 替换    {key[:40]}…")
        elif op == "drop":
            idx = [i for i, ln in enumerate(lines) if any(ln.startswith(p) for p in key)]
            if not idx:
                print(f"  ⚠️ 已应用  删 {key[0][:40]}…")
                continue
            for i in reversed(idx):
                del lines[i]
            print(f"  ✅ 删除 {len(idx)} 行")
        else:                                            # ins_before
            if val[-1].rstrip("\r") in ln_all:
                print(f"  ⚠️ 已应用  插入 {val[0][:36]}…")
                continue
            idx = [i for i, ln in enumerate(lines) if key in ln]
            if len(idx) != 1:
                print(f"  ⛔ 锚点命中 {len(idx)} 行  {key[:36]}…")
                bad += 1
                continue
            lines[idx[0]:idx[0]] = [x + ("\r" if crlf else "") for x in val]
            print(f"  ✅ 插入 {len(val)} 行")
    if bad:
        print(f"\n⛔ 有 {bad} 条没命中 ⇒ 别硬改")
        return 1
    if a.check:
        print("\n✅ dry-run 通过")
        return 0
    out = "\n".join(lines).replace("\r\n", "\n")
    if crlf:
        out = out.replace("\n", "\r\n")
    PLAN.write_text(out, encoding="utf-8", newline="")
    print(f"⇒ 已写入 {PLAN.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
