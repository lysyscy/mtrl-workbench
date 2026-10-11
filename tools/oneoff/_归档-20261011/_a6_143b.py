#!/usr/bin/env python
"""`TAIL-177` 的 §14.3 排期行**补事实**（2026-09-29 · 一次性）。

**为什么补**：用户问「`m01` 的删除，能改成真删除么？什么时机合适？」⇒ 我当场把后端挖了一遍，
挖到三件**下次不用再查**的硬事实（⛔ 不补进去就会再查一遍）：
  ① 真删**本来就该硬删**（《说明书》§9.4 的分档判据 = 按"删掉之后能不能凭源数据复原"分；项目档案
     `重抓重导即回` ⇒ 硬删那一档）；
  ② ⚠️ **库里有硬约束**：`mod11_jc` 的集采合同外键是 **`RESTRICT`**（有合同 ⇒ **库直接拒删**，
     这是故意的："要删项目得先处置合同，别让删项目把台账悄悄带走"）；而 **`mod09_fee`（特殊费用月报）
     与 `mod05_flow.LedgerRemark`（台账备注）是 `CASCADE`** ⇒ 删项目会**真的把它们一起删掉**
     ⇒ 这两件必须**提前**告诉用户（否则是"看不见的连带删除"）；
  ③ 房内**已有两个能跑的先例**：`m14` 规则配置 `DELETE /api/m14/rules/{id}`（配置类真硬删 ＋ 人话回执）；
     `m03` 手动行 `manual-delete-impact`（**影响范围由后端算**，⛔ 前端不自己拼）→ 确认框 → `manual-delete` 真删。
  ⇒ 真删**不是从零**，缺的只有那一层"**跨模块计数**"，而 `mod13_cross`（跨域能力那个包）现在是**空包**
     （只有 `__init__.py`）⇒ 它属 **M6 计划内的最后一块**（导出/规则配置/用户管理/主题都已落地）
     ⇒ ⛔ **不进 §15 尾巴台账**（本仓口径：「计划内的活不进本节」）。

用法：`… _a6_143b.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

PLAN = pathlib.Path(__file__).resolve().parents[2] / ".workbuddy" / "plans" / "开发计划-主文档.md"

OLD = "| 触发 = 用户回一句（`A`/`B`/`C`）；**真接通的前置** = `MOD-13` 跨域能力能把"
NEW = (
    "| 触发 = 用户回一句（`A`/`B`/`C`）；**「真删」的落点与时机（2026-09-29 挖清，⛔ 别当成尾巴）**："
    "它**属 `M6` 计划内的最后一块**（本仓口径「计划内的活不进 §15 尾巴台账」）—— ★ 真删**本来就该硬删**"
    "（《说明书》§9.4 的分档 = 按「删掉之后能不能凭源数据复原」分；项目档案 `重抓重导即回` ⇒ 硬删档）；"
    "★ 房内**已有两个能跑的先例**：`m14` 规则配置 `DELETE /api/m14/rules/{id}`（配置类真硬删 ＋ 人话回执）· "
    "`m03` 手动行 `manual-delete-impact`（**影响范围由后端算**，⛔ 前端不自己拼）→ 确认框 → `manual-delete` 真删；"
    "★ ⚠️ **库里有硬约束**：`mod11_jc` 集采合同外键 = **`RESTRICT`**（有合同 ⇒ **库直接拒删**，故意如此："
    "「要删项目得先处置合同，别让删项目把台账悄悄带走」）；而 `mod09_fee`（特殊费用月报）与 "
    "`mod05_flow.LedgerRemark`（台账备注）= **`CASCADE`** ⇒ 删项目会**真的把它们一起删掉**"
    "（必须提前报数，否则是「看不见的连带删除」）；其余（付款通知书/计划/流水/过程资料/库存单据/大表手填）"
    "= `SET NULL` ⇒ 行留着、显示为「未建档」；★ 缺的只有那层「**跨模块计数**」，而 `mod13_cross` 现在是"
    "**空包**（只有 `__init__.py`）⇒ **建议时机 = `M6` 那一轮做**，最早也别早于 **`m11` 集采台账扫完**"
    "（`RESTRICT` 那个挡路项正是 m11 要处置的合同，两件互相印证）；⛔ **不推荐现在硬做**：只能列出 1/4 项"
    "⇒ 用户看到的是**半真的影响范围**，而 §7.2/§9.4 的判据 `ACC-X-DEL-001/001-01` 明写「**真实计数，不是占位**」；"
    "**真接通的前置** = `MOD-13` 跨域能力能把"
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = PLAN.read_text(encoding="utf-8", newline="")
    if "★ 真删**本来就该硬删**" in raw:
        print("⏭ 已应用（§14.3 那行已含 2026-09-29 挖清的事实）⇒ 无事可做")
        return 0
    n = raw.count(OLD)
    assert n == 1, f"锚点命中 {n} 次（要**恰好 1 次**）—— 先核再改"
    print("  ✅ 锚点唯一：§14.3 的「触发 / 前置」那格")
    if not args.write:
        print("\n（`--check`：⛔ 未写）")
        return 0
    PLAN.write_text(raw.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    back = PLAN.read_text(encoding="utf-8", newline="")
    assert "★ 真删**本来就该硬删**" in back, "写回自校验不过"
    print("✅ 已写：§14.3 的 `TAIL-177` 行补上「真删」的落点/时机/硬约束/先例")
    print("   接着：`doc_audit` ＋ `audit_meta`（`T6` 核台账计数与排期仍在位）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
