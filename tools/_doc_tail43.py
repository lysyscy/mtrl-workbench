# -*- coding: utf-8 -*-
"""落账：新增 TAIL-43（模板法成品的两张透视「显示区」未重建）+ 更新计数行 + TAIL-04 进度。

用户 2026-09-18 打开真机成品发现：「安全文明施工费」透视**有数据**，而该月 i8 源里没有该 cbs
⇒ 实测确认：成品 `过程资料`(12 行) / `安全文明施工费`(8 行) **逐字等于模板里的旧值**（8 月），
只有 `报表1` 换成了本月。⇒ 模板法只重建数据 sheet 与缓存，**没重建透视的显示区**。
"""
from __future__ import annotations

import pathlib

P = pathlib.Path(r"D:\dev\mtrl-workbench\.workbuddy\plans\开发计划-主文档.md")
lines = P.read_text(encoding="utf-8").split("\n")
orig = list(lines)


def find_one(needle: str) -> int:
    hits = [i for i, ln in enumerate(lines) if needle in ln]
    if len(hits) != 1:
        raise SystemExit("⛔ 锚命中 %d 次（要 1 次）：%s" % (len(hits), needle[:60]))
    return hits[0]


# ---------- ① 详表：在 TAIL-42 行之后插 TAIL-43 ----------
i42 = find_one("| `TAIL-42` | ⚠️ **「全名回查命中 ≥2 条」时")
detail = (
    "| `TAIL-43` | ⚠️⚠️ **模板法成品的两张透视「显示区」未重建 —— 打开看到的是模板月份的旧数** —— "
    "模板法只重建 `sharedStrings` / 数据 sheet / `pivotCache` 两件 / `pivotTable` 的行项与 `location`，"
    "**没有重建透视的「显示区」**（`xl/worksheets/sheet1.xml`、`sheet2.xml` 里的**静态单元格值**，"
    "那是 Excel 保存下来的渲染结果）⇒ 打开成品时，明细（`报表1`）是本月、两张透视却还是**模板那个月**的数 | "
    "用户 2026-09-18 打开真机成品发现（原话：安全文明施工费里有数据，我猜测是模板里的数据，实际应该为 0 才对） | "
    "**报表数报错**（用户可能照透视报数）· 本片已实证：成品 `过程资料` 12 行 / `安全文明施工费` 8 行"
    "**逐字等于** `模板_库存单据明细表.xlsx` 里的旧值，而本月 i8 源里**没有**任何 `cbs名称=安全文明施工费` 的行 | "
    "① 验「打开即刷新」是否真生效（`refreshOnLoad` 位置已实测纠正到 `pivotCacheDefinition`，但 WPS/Excel 是否认待验）；"
    "② 清空 / 重建显示区静态值；③ 按新数据重算渲染值 —— ⚠️ **需新立判据**（成品透视显示区 == 本月重算结果，或如实为空） | "
    "立刻（用户 2026-09-18 决定**换成单个专家专办**此事） | 待做 |"
)
lines.insert(i42 + 1, detail)

# ---------- ② 简表：在 TAIL-41 行之后插一行 ----------
i41s = find_one("| `TAIL-41` ⚠️ **「未命中清单」在抓取成功后不清空**")
brief = (
    "| `TAIL-43` ⚠️⚠️ **模板法成品的两张透视「显示区」未重建**（打开看到模板月份的旧数） | "
    "**立刻**（用户决定换单个专家专办） | "
    "① **数是错的**（用户可能照透视报数）—— 比「拿不到文件」更坏；② 它是 `TAIL-04` 那个方法的**共同缺陷**"
    "（收发结存那份同理，需一并复核） | 见 §15 详表"
)
lines.insert(i41s + 1, brief)

# ---------- ③ 计数行：A 类 12 → 13 ----------
icnt = find_one("> **当前状态（2026-09-18 09:52）**")
old_cnt = lines[icnt]
lines[icnt] = old_cnt.replace("A 类 **12** 条", "A 类 **13** 条")
if lines[icnt] == old_cnt:
    raise SystemExit("⛔ 计数行没改到：%s" % old_cnt[:80])

# ---------- ④ TAIL-04 详表：进度追加 ----------
i04 = find_one("| `TAIL-04` | 两个材料报表（收发结存 / 库存单据明细表）的**成品文件写出**")
tail = "⏭️ **余下**：① 库存单据明细表（`kcdj`，引擎已同步修好、只差接）② 其余页面的路径①模板填充 ｜"
new_tail = (
    "⏭️ **余下**：① 其余页面的路径①模板填充 ｜ "
    "✅ **2026-09-18 第二片「库存单据明细表」已落地并真机验收**（移植 `kcdj_process` ＋ `kcdj_export.py` ＋ "
    "`GET /api/m08/inventory/export` ＋ 壳侧 `expPivot` 真下载；真机 **560 行 / 8 仓 → xlsx 136,656 B**；"
    "⭐ 顺带补 **i8 cookie 磁盘缓存复用**（`cookie_store.py`）⇒ 导出**不再顶号**）｜ "
    "⚠️ **新暴露一个共同缺陷 → `TAIL-43`**（两张透视的显示区是模板旧值）｜"
)
if lines[i04].count(tail) != 1:
    raise SystemExit("⛔ TAIL-04 行尾锚命中 %d 次" % lines[i04].count(tail))
lines[i04] = lines[i04].replace(tail, new_tail)

if lines == orig:
    raise SystemExit("⛔ 什么都没改")

P.write_text("\n".join(lines), encoding="utf-8")
print("✅ 已落账：TAIL-43（简表 + 详表）· 计数 A 类 12→13 · TAIL-04 进度追加")
