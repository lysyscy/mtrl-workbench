#!/usr/bin/env python
"""`TAIL-173` **销号留痕**（用户裁定 `A` · 2026-09-29）—— 台账**三处一起动**。

**为什么用脚本**：那三行都**很长**（手抄必错），而 `T6` 认的是**编号与计数**（销号漏一处就红）。
⇒ 读盘 → 按前缀定位（⛔ 不用"第 N 行"）→ 改 → 写回 → **再读盘校验**（`A4` 的教训：编辑器旧副本会把改动盖回去）。

**动的三处 ＋ 计数两处**：
  1. `§三`（`C` 类）**移出**那一行（销号 ⇒ 不再挂着）；
  2. `§14.3` 那行改成 **✅ 已做（留痕，别删）**；
  3. `§四`（已销号）**补一行**；
  4. `C 类` **1 → 0** · `已销号` **170 → 171**（两处写法各一）。

用法：`… _tally_tail173.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"

ID = "`TAIL-173`"
P_C = f"| {ID} | "        # §三（C 类 · 待你裁定）那行：`| `TAIL-173` | …`
P_S = f"| {ID} ⭐ "     # §14.3 排期那行：`| `TAIL-173` ⭐ …`

NEW_SCHED = (
    f"| {ID} ⭐ **`A4` 报的两件**（`m06` 两枚导出按钮 · 差异表差额整列红） | ✅ **已做（2026-09-29 · 留痕，别删）** |"
    " 用户 2026-09-29 回 **`A`**（删按钮 ＋ 差额列只标方向）。① `m06` 卡头那枚「导出 Excel」**永远只会说"
    "「这一页还没有导出功能」**（`EXP_ROUTES` 里没有「过程资料」）而真入口就在同一张卡头 ⇒ 相似元素歧义"
    "（§4.4）⇒ **渲染后摘除**（⛔ `V.m06` 一行未改：切片逐行对位 ＋ `test_tail04_pages.py` 把 `data-act=\"exp\"` "
    "名单钉在源码上）；② 差异表**每行都是差异** ⇒ 差额列整列红没有区分度（§4.5）⇒ 改成**只靠符号**"
    "（`SIG` 已给正负号）＋ 该列一句悬停说明 | 备注：**别顺手删兜底那句**（`m08` 朴素那份 / 已取消的差异清单仍在用） |"
)

NEW_LEDGER = (
    f"| {ID} | 🧾 **`m06` 两件收口**（`A4` 顺手报 · 用户裁定 `A`）：① 卡头**摘掉那枚永不出结果的导出按钮**"
    "（点了必然空转 = 与真入口并排 ⇒ §4.4 相似元素歧义）—— ⚠️ 走**渲染后摘除**（`BIND.m06`），⛔ `V.m06` 一行未改"
    "（切片逐行对位会让「删一行」级联报漂移；且 `test_tail04_pages.py` 把 8 个 `exp` 的 `data-t` 名单**钉在源码上**）；"
    "② 差异表**差额列只标方向**（原先整列 `color:var(--dg)` —— 差异表里每行都是差异 ⇒ 红色没有区分度），"
    "方向由 `SIG` 的符号承载 ＋ 该列带一句悬停说明 | 判据 = 新判据 2 条（`ACC-RPT-EXP-001/001-09` · "
    "`ACC-RPT-PROC-001/001-10`）＋ 全套 pytest **100%** ＋ 四态 **629 → 631** ＋ `ui_parity` 登记 1 条 ＋ 消号 1 条幽灵 ＋ "
    "12 把尺子 rc=0 ＋ `doc_audit --ui` 必须修 0 ＋ **盖章** `20260929-0946` ＋ 真机 `_shell_smoke` rc=0（㉛ 全 ✅ · 无 console 错误）；"
    "**改前已备份交付面** ⇒ `.workbuddy/backups/交付面-20260929-0945-TAIL173/`；脚本 = `_doc_tail173.py` | 2026-09-29 |"
)

COUNTS = (("C 类 **1** · 已销号 **170**", "C 类 **0** · 已销号 **171**"),
          ("C 类 **1** 条 · 已销号 **170** 条", "C 类 **0** 条 · 已销号 **171** 条"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = PLAN.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    t = raw.replace("\r\n", "\n") if nl == "\r\n" else raw
    L = t.split("\n")

    c_hits = [i for i, l in enumerate(L) if l.startswith(P_C)]
    s_hits = [i for i, l in enumerate(L) if l.startswith(P_S)]
    assert len(c_hits) == 1, f"§三 那行命中 {len(c_hits)}（期望 1）"
    assert len(s_hits) == 1, f"§14.3 那行命中 {len(s_hits)}（期望 1）"
    li = [i for i, l in enumerate(L) if l.strip() == "| # | 事项 | 销号依据 | 日期 |"]
    assert len(li) == 1, f"§四 表头命中 {len(li)}（期望 1）"

    # ① §三 移出
    del L[c_hits[0]]
    s = s_hits[0] - 1 if s_hits[0] > c_hits[0] else s_hits[0]        # ⚠️ 删行后 §14.3 下标要挪
    assert L[s].startswith(P_S), "删行后 §14.3 那行下标算错了"
    # ② §14.3 改✅
    L[s] = NEW_SCHED
    # ③ §四 补行（⚠️ 这张表**没有分隔行** —— 表头后直接是数据行 ⇒ 有就插其后、没有就插表头后）
    hdr = li[0]
    at = hdr + 1 + (1 if L[hdr + 1].startswith("|---") else 0)
    assert L[at].startswith("| `TAIL-"), f"§四 表头下面不是台账行 ⇒ ⛔ 别插错位置：{L[at][:60]!r}"
    L.insert(at, NEW_LEDGER)
    out = "\n".join(L)
    # ④ 计数
    for old, new in COUNTS:
        n = out.count(old)
        assert n == 1, f"计数片段命中 {n} 次（期望 1）：{old!r}"
        out = out.replace(old, new, 1)
    print(f"§三 移出 1 行 · §14.3 改✅ · §四 补 1 行 · 计数 2 处 ⇒ {len(L)} 行（原 {len(t.splitlines())}）")

    if args.write:
        PLAN.write_text(out.replace("\n", nl) if nl == "\r\n" else out, encoding="utf-8", newline="")
        back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
        bl = back.split("\n")
        print("   回读校验：§三 残留", sum(1 for l in bl if l.startswith(P_C)),
              "· §14.3 已✅", sum(1 for l in bl if l.startswith(P_S) and "已做（2026-09-29" in l),
              "· §四 新行", sum(1 for l in bl if l.startswith(f"| {ID} | 🧾")),
              "· C 类 0", back.count("C 类 **0**"), "· 已销号 171", back.count("已销号 **171**"))
    else:
        print("（`--check`：⛔ 未写）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
