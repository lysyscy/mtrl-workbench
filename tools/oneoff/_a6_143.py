#!/usr/bin/env python
"""`A6` 补 `§14.3` 排期行（`T6` 当场抓到：新立的 `TAIL-177` **只登记、没排期**） · 一次性（2026-09-29）。

**为什么必须补**：`§15` 管清点、`§14.3` 管"什么时候做" —— 本仓铁律「**尾巴不许"只登记、不排期"**」
（`audit_meta` 的 `T6` 就是这条的机器眼；本次它当场报红 ⇒ 已修）。

用法：`… _a6_143.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

PLAN = pathlib.Path(__file__).resolve().parents[2] / ".workbuddy" / "plans" / "开发计划-主文档.md"

HDR = "| 尾巴 | 建议时机 | 理由（四问） | 前置 / 触发 |"
SEP = "|---|---|---|---|"
ROW = (
    "| `TAIL-177` ⭐ **`m01` 的「删除」点得到、却永远删不了**（`A6` 顺手查出 · 属**用户可见的交互变化** ⇒ 没擅自改） "
    "| ⏳ **待用户一句话**（先别动） | **四问逐条**：① **不是别人的前置**（`DELETE /api/m01/projects` 与「列影响范围」"
    "都不在别的链路上）；② **成本不随时间变贵**（只动一枚按钮的态 ＋ 一句说明）；③ **同域 = `m01` / `MOD-13`**"
    "（真接通要等 `MOD-13` 跨域把「影响范围」列全 ⇒ 属**同域的下一轮**，⛔ 别单独起轮）；④ ⚠️ **前置没到位**"
    "（影响范围那三项还是「待接通」）⇒ **硬等 `MOD-13`**；⇒ 所以本轮**只等用户选一个当下形态**"
    "（`A` 确认删除置灰并说明 / `B` 整枚藏起来 / `C` 保持现状），⛔ 不去动「接通」本身 "
    "| 触发 = 用户回一句（`A`/`B`/`C`）；**真接通的前置** = `MOD-13` 跨域能力能把"
    "「关联付款流水 / 库存单据 / 集采合同」列得出来（§7.2 那道闸） |"
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = PLAN.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    if "`TAIL-177`" in raw and "`TAIL-177` ⭐ **`m01` 的「删除」点得到" in raw:
        print("⏭ 已应用（§14.3 里有 `TAIL-177` 那行）⇒ 无事可做")
        return 0
    assert HDR in raw and SEP in raw, "找不到 §14.3 的表头/分隔行 ⇒ 表结构变了"
    assert raw.count(HDR) == 1 and raw.count(nl + SEP + nl) >= 1, "§14.3 表头不唯一"
    old = HDR + nl + SEP + nl
    assert raw.count(old) == 1, f"§14.3 表头＋分隔行命中 {raw.count(old)} 次（要 1 次）"
    print("  ✅ 锚点唯一：§14.3 表头 ＋ 分隔行")
    if not args.write:
        print("\n（`--check`：⛔ 未写）")
        return 0
    PLAN.write_text(raw.replace(old, old + ROW + nl, 1), encoding="utf-8", newline="")
    back = PLAN.read_text(encoding="utf-8", newline="")
    assert "`TAIL-177` ⭐ **`m01` 的「删除」点得到" in back, "写回自校验不过"
    print("✅ 已写：§14.3 加 `TAIL-177` 一行（四问 ＋ 前置）")
    print("   接着：`audit_meta` 复核（`T6` 期望 0）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
