#!/usr/bin/env python
"""`ui_parity` 登记簿**消号**（`TAIL-170`/`TAIL-171` 同批 · 2026-09-29）。

**为什么要有它**：那轮改了 `V.*` 切片里几行（导出按钮加 `title` / 勾选表行首格加 `fl` / 合计行加 `leadCls`），
**指纹（fp = f(原型行 ＋ 壳行)）随之改变** ⇒ ① 新漂移由 `ui_parity --write-expected` **追加**登记 ✓；
② 旧的那几条**已无对应漂移**（工具报「幽灵登记 ⇒ 可消号」）。⚠️ 本仓规矩：**消号必须人工删行**
（工具⛔ 不自动删 —— 自动删会连带冲掉旁边的理由注释）。

**它做什么**：逐条核（**必须命中恰好一行**）后删除这些**已知**的幽灵行；⛔ 只删列出来的那些，不多删一行。

用法：`… _prune_ui_expected.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
EXPECTED = REPO / "tools" / "ui_parity_expected.txt"

#: 本轮改过那几行 ⇒ 旧指纹成了幽灵（逐条来自 `ui_parity` 的「幽灵登记」提示）
GHOSTS: tuple[str, ...] = (
    "m04 d5e79abd",   # m04 导出按钮（加了 title ⇒ 真导出的范围说明）
    "m01 8c86cae7",   # m01 导出按钮
    "m05 0bcf119e",   # m05 导出按钮
    "m08 f1de8b73",   # m08 导出按钮
    "m06 1e1957a7",   # m06 那一片的对齐项（导出按钮加 title 后行对齐变了）
    "m11 0a3cc978",   # m11 同上
    "m11 b25bc49a",   # m11 数据行首格（加了 fl）
    "m04 b1669443",   # m04 合计行（加了 leadCls:'fl'）
    "m15 118d0ddb",   # m15 账号列表那两枚按钮（加了置灰说明）
    "m06 623bf917",   # m06 卡头那枚「批量导出」（`A4` 改了 title 措辞 ⇒ 旧指纹作废）
    "m06 3f85a8c5",   # m06 差异表差额格（`TAIL-173` 去掉整列红 ⇒ 旧指纹作废）
    "m01 d9af3257",   # ⭐ `A6`：m01 空态指路改成点名真实入口（行内容变了 ⇒ 旧指纹作废）
    "m14 12f16b82",   # ⭐ `A6b`：m14「硬规矩」表第 6 条改 §9.4 定案口径（同上）
    "m11 0037ab97",   # ⭐ `A7`：m11 卡头「抓取采购合同信息」补后果提示（同上）
    "m14 8bee3f11",   # ⭐ `A10`：m14「分类只有三类」那句从危险红降为普通 `tip`（同上）
    "home 570f3553",  # ⭐ `A11`：home 那段「保留 4 项」注释订正为「4 项 ＋ 随后又加 2 项」（同上）
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    # ⚠️⚠️ 读写**都必须锁 `newline=""`**（2026-09-29 `A6b` 修）：登记簿是 **CRLF**，而
    #    `write_text(..., encoding="utf-8")`（默认 `newline=None`）会把内容里的 `\n` 再翻成 `\r\n`
    #    ⇒ 每行变成 **`\r\r\n`**（仓里 `归档-历史单元条目.md` 那 6681 处就是这个坑的产物）。
    lines = EXPECTED.read_text(encoding="utf-8", newline="").splitlines(keepends=True)
    drop: set[int] = set()
    done = 0
    for g in GHOSTS:                       # ⚠️ 幂等：已删过的（0 命中）算"已消号"，**不多删**
        hits = [i for i, l in enumerate(lines) if l.startswith(g + " ")]
        if len(hits) > 1:
            print(f"  ⛔ {g}  命中 {len(hits)} 行（⛔ 有重复 ⇒ 别写）")
            return 1
        if len(hits) == 1:
            drop.add(hits[0])
            print(f"  ✅ {g}  待消号")
        else:
            done += 1
            print(f"  · {g}  已消号过（跳过）")
    print(f"\n本次消号 {len(drop)} 条 · 此前已消号 {done} 条")
    kept = [l for i, l in enumerate(lines) if i not in drop]
    print(f"\n登记簿 {len(lines)} 行 ⇒ 去掉 {len(drop)} 条幽灵 ⇒ {len(kept)} 行")
    if args.write:
        EXPECTED.write_text("".join(kept), encoding="utf-8", newline="")   # ⚠️ 见上方 `\r\r\n` 的坑
        print(f"✅ 已写回 {EXPECTED}")
        print("   ⚠️ 接着复跑 `tools/audit/ui_parity.py`（期望「必须修 0」且幽灵清零）")
    else:
        print("\n（`--check`：⛔ 未写）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
