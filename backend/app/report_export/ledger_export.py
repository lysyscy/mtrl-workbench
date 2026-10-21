# -*- coding: utf-8 -*-
"""台账成品（`TAIL-04` 路径① 片 2＋3）—— **一本工作簿 / 三个 sheet**。

## 形态（唯一登记处 = 交付面 `docs/requirements/report-templates.md` §二 / §5.1 / §5.2）

| sheet | 列 | 行 | 尾块 |
|---|---|---|---|
| `辅材` | 序号 ｜ 月份 ｜ 其他支出金额 ｜ 付款 ｜ 欠款 ｜ 备注 | 期初占位行 ＋ 逐月行（空月也出行） | R19「合计：」＋ C/D/E（**以数值覆盖**） |
| `机械` | 同上 | 同上 | 同上 |
| `特殊费用月报表` | 数据项 ｜ `<M>月份` ｜ 合计 | 1 自动项 ＋ N 手填项（行数可变） | **无**（列先压成一列，见下） |

## 四处口径（都有现成主人，⛔ 不在此另立）

1. **标题**：`{展示名}` ＋ 模板后缀（`辅材欠款` / `机械费欠款` / `费用汇总表`）——
   用户 **2026-09-18 裁定**：用**展示名**、**不带「项目」二字**（模板那句 `龙源纸业项目辅材欠款` 里的
   「项目」二字属于示例项目名本身）⇒ `德州热电辅材欠款`。
   ⚠️ 模板标题里写着**别的项目名** ⇒ 一律**整格替换**，⛔ 不许原样带走（`TAIL-43` 同族）。
2. **月份列**＝**页面文本**（`模板清单` §四-4 裁定「按页面文本」）：期初行沿用API的截止月标签，旧调用者兼容`截止 YYYY 年 M 月底`、
   其余 = `YYYY-MM`；⚠️ 写前把该格**数字格式设为文本**（模板那列原本是日期/数值格式）。
3. **合计 / 小计一律以数值覆盖**（§四-2 / §六-2）：模板里的 `=SUM(...)` 不进成品。
4. **`特殊费用月报表` 的月份列按「当前核算月」生成**（§5.2 裁定①丙）：模板的 `3月份`…`8月份`
   只是示例 ⇒ 先把多月**压成一列**（`tpl_fill.keep_only_columns`，认「N月份」表头、⛔ 不抄列字母），
   **再**走行维度的 `fill_sheet`。

⛔ 本模块只做**列映射 / 标题 / 数字格式**：不算金额、不筛项目、不拼路径
（金额与行集合的主人分别是 `mod05_flow` 与 `mod09_fee`；路径唯一出口 = `resources`）。
"""

from __future__ import annotations

import re
import zipfile
from decimal import Decimal
from pathlib import Path

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter

from app.core.errors import MustReportError
from app.core.money import sum_money
from app.mod07_setl.domain import period_label
from app.report_export import resources, tpl_fill
from app.report_export.save import save_workbook

#: 类别（**内部值 = 英文**，见 `mod05_flow.models`：`material` / `mechanical`）→ 模板里的 sheet 名
#: （`模板清单` §二 登记；⛔ 不在这里另起名字。⚠️ 别把「显示名（辅材/机械）」当键 —— 那是 `label`）
SHEET_OF_CATEGORY: dict[str, str] = {"material": "辅材", "mechanical": "机械"}
SHEET_FEE = "特殊费用月报表"

#: 标题后缀（**照模板**；前缀 = 项目**展示名**）
TITLE_SUFFIX: dict[str, str] = {"辅材": "辅材欠款", "机械": "机械费欠款", SHEET_FEE: "费用汇总表"}

#: 成品命名（**唯一出口**）：`{展示名}欠款台账_{期间标签}.xlsx`（原型：文件名含项目展示名与当前年月）
FILE_SUFFIX = "欠款台账"

#: 台账列映射（`模板清单` §5.1：模板 6 列 = 页面 7 列去掉「操作」）
LEDGER_COL = {"seq": "A", "month": "B", "other": "C", "pay": "D", "debt": "E", "remark": "F"}
#: 特殊费用月报表列映射（`模板清单` §5.2：数据项 ＋ 单月列 ＋ 合计）
FEE_COL = {"item": "A", "month": "B", "total": "C"}

#: 期初占位行的月份文本（**照原型** `ledCutLabel`：空格与「年月」写法一字不差）
CUT_MONTH_FMT = "截止 {y} 年 {m} 月底"
#: 写文本前先设的**数字格式**（唯一主人 = 引擎 `tpl_fill.TEXT_FMT`；此处只为兼容既有引用而转发）
TEXT_FMT = tpl_fill.TEXT_FMT

#: 月份表头的识别（`3月份` / `9月份` …）—— 认**结构**，⛔ 不抄列字母
_MONTH_HEADER = re.compile(r"^\d+月份$")


def money(value) -> Decimal | None:
    """金额列的值：**空 ⇒ `None`**（留白），其余归一到 `Decimal`（2 位小数口径 = `core.money`）。

    ⚠️ 台账的 `0` 是**合法值**（空月记 0，§4.5.4）⇒ **照写 0**，⛔ 不按"焊材结余"那套留空。
    """
    if value in (None, ""):
        return None
    return sum_money([value])


# ---------------------------------------------------------------- 台账两 sheet


def title_of(display: str, sheet: str) -> str:
    """标题 = **展示名 ＋ 模板后缀**（用户 2026-09-18 裁：不带「项目」二字）。"""
    return f"{display or ''}{TITLE_SUFFIX[sheet]}"


def month_text(row: dict) -> str:
    """「月份」列的**页面文本**：期初占位行 = `截止 YYYY 年 M 月底`，其余 = `YYYY-MM`。"""
    ym = str(row.get("month") or "")
    if row.get("month_label"):
        return str(row["month_label"])
    if row.get("is_opening") and len(ym) >= 7 and ym[4] == "-":
        return CUT_MONTH_FMT.format(y=int(ym[:4]), m=int(ym[5:7]))
    return ym


def ledger_spec(sheet: str, side: dict, *, display: str) -> dict:
    """一侧台账 → 引擎 `spec`（`label` = 序号；「合计行」进 `tail` 的偏移 0）。"""
    rows = list(side.get("display_rows", side.get("rows")) or ())
    data = [
        (r.get("seq"), {
            LEDGER_COL["month"]: month_text(r),
            LEDGER_COL["other"]: money(r.get("other_expense")),
            LEDGER_COL["pay"]: money(r.get("payment")),
            LEDGER_COL["debt"]: money(r.get("debt")),
            # ⚠️ 空备注给 `None`（⛔ 不给 `""`）：空串存回 Excel 会变成"有格无值"，
            #    与 `verify_filled` 期望的 `None` 不符 ⇒ 对账会**误报**（实测踩到，8 条）。
            LEDGER_COL["remark"]: (str(r.get("remark") or "").strip() or None),
        })
        for r in rows
    ]
    tail = {0: (None, {
        LEDGER_COL["other"]: sum_money([r.get("other_expense") for r in rows]),
        LEDGER_COL["pay"]: sum_money([r.get("payment") for r in rows]),
        LEDGER_COL["debt"]: sum_money([r.get("debt") for r in rows]),
    })}
    return {"sheet": sheet, "rows": data, "tail": tail, "title": title_of(display, sheet),
            "months_col": LEDGER_COL["month"]}


# ---------------------------------------------------------------- 特殊费用月报表


def fee_spec(fee: dict, *, display: str, ym: str) -> dict:
    """特殊费用月报表 → 引擎 `spec`（**单月列**；「合计」列 = 该月值，§5.2 标注）。"""
    items = [fee.get("auto") or {}] + list(fee.get("manuals") or [])
    data = [
        (str(it.get("item") or "").strip() or None, {      # ⚠️ 同上：空项名给 `None`，不给 `""`
            FEE_COL["month"]: money(it.get("amount")),
            FEE_COL["total"]: money(it.get("amount")),      # 单月列 ⇒ 合计 = 该月值
        })
        for it in items
    ]
    return {"sheet": SHEET_FEE, "rows": data, "tail": {}, "title": title_of(display, SHEET_FEE),
            "months_col": FEE_COL["month"]}


def month_header_text(ym: str) -> str:
    """单月列的表头（`3月份` → `9月份`）。"""
    return "%d月份" % int(str(ym)[5:7])


def collapse_months(ws, ym: str) -> dict:
    """把模板的多个月份列**压成一列**并改写表头（`模板清单` §5.2 裁定①丙）。

    ⚠️ 必须在 `fill_sheet` **之前**调用（数据区/尾块定位都基于列）。
    """
    cols = [c for c in range(1, ws.max_column + 1)
            if _MONTH_HEADER.match(str(ws.cell(row=2, column=c).value or "").strip())]
    if not cols:
        raise MustReportError("模板的 `特殊费用月报表` 第 2 行找不到「N月份」列 ⇒ 形态不认识，拒绝产出。")
    keep = get_column_letter(cols[0])
    info = tpl_fill.keep_only_columns(
        ws, keep=keep, drop=[get_column_letter(c) for c in cols[1:]])
    ws.cell(row=2, column=column_index_from_string(keep)).value = month_header_text(ym)
    return info


# ---------------------------------------------------------------- 组装


def file_name(display: str, ym: str) -> str:
    """成品文件名（**唯一出口**）。"""
    return "%s%s_%s.xlsx" % (display or "", FILE_SUFFIX, period_label(str(ym or "").strip()))


def _set_text_fmt(ws, plan: dict, months_col: str) -> None:
    """把「月份」列的**数据行**格设为文本格式（`模板清单` §四-4）。

    ⚠️ 本条实现在 `TAIL-04` 片 4a 时**提到了引擎**（`tpl_fill.set_text_format`）—— 那是同一个坑的
       **第二次**出现（台账「月份」列 ＋ 过程资料「时间」列）⇒ 口径归引擎，这里只做转发。
    ⚠️ `months_col` 从 **spec** 传进来（`fill_sheet` 返回的对账计划里**没有**它 ——
       它只回引擎自己认得的键）。
    """
    tpl_fill.set_text_format(ws, plan, months_col)


def build_xlsx(sections: dict, out_dir, *, display: str, ym: str) -> str:
    """三个 sheet → 一本 xlsx ⇒ 返回**成品绝对路径**。

    `sections` = `{"material": side, "mechanical": side, "特殊费用月报表": fee}`
    （`side` 由 `mod05_flow.service.build_ledger` 给、`fee` 由 `mod09_fee.service.build_page_data` 给）。

    - 模板走 `resources.require_template`（缺失 / 被回退 ⇒ **显式拒做**）；
    - ⚠️ 三个 sheet **要么都填、要么不产出** —— 只填两个就交付，第三张会把模板里**别的项目**的
      示例数据整张留给用户（`TAIL-43` 同族）；
    - 产物一律过 `tpl_fill.verify_filled`（逐格 / 尾块以下残留 / 值覆盖不彻底）。
    """
    ym = str(ym or "").strip()
    if len(ym) != 7 or ym[4] != "-":
        raise MustReportError("导出台账：拿不到**报告月**（当前筛选下没有可导出的数据）——"
                              "请先在页面上把项目 / 止月选到有数据的那一档。")
    template = resources.require_template(resources.LEDGER_TEMPLATE)
    out = Path(out_dir) / file_name(display, ym)
    wb = openpyxl.load_workbook(str(template))
    try:
        fee_ws = wb[SHEET_FEE]
        collapse_months(fee_ws, ym)                       # ⚠️ 先压列、再填行
        for sheet in (SHEET_FEE, *SHEET_OF_CATEGORY.values()):
            wb[sheet]["A1"] = title_of(display, sheet)    # 标题里写着别的项目名 ⇒ 整格替换
        specs = [ledger_spec(sheet, sections.get(cat) or {}, display=display)
                 for cat, sheet in SHEET_OF_CATEGORY.items()]
        specs.append(fee_spec(sections.get(SHEET_FEE) or {}, display=display, ym=ym))
        plan = []
        for sp in specs:
            ws = wb[sp["sheet"]]
            sheet_plan = tpl_fill.fill_sheet(ws, sp)
            _set_text_fmt(ws, sheet_plan, sp["months_col"])
            plan.append(sheet_plan)
        save_workbook(wb, out)
    finally:
        wb.close()
    problems = tpl_fill.verify_filled(out, {"path": str(out), "sheets": plan})
    if problems:
        raise MustReportError(
            "台账成品**显示区对账未通过** ⇒ 已中止，未交付："
            + "；".join(problems[:5]) + ("" if len(problems) <= 5 else "（等共 %d 条）" % len(problems)))
    return str(out)


def build_zip(paths, out_dir, name: str) -> str:
    """把**每个项目一本**的工作簿打成一个 zip（≥2 个项目时的交付形态）⇒ 返回 zip 路径。"""
    out = Path(out_dir) / name
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(str(p), Path(p).name)
    return str(out)


__all__ = ["SHEET_OF_CATEGORY", "SHEET_FEE", "TITLE_SUFFIX", "FILE_SUFFIX", "LEDGER_COL", "FEE_COL",
           "CUT_MONTH_FMT", "TEXT_FMT", "money", "title_of", "month_text", "ledger_spec",
           "fee_spec", "month_header_text", "collapse_months", "file_name", "build_xlsx",
           "build_zip"]
