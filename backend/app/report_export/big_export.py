# -*- coding: utf-8 -*-
"""活动大表成品（`TAIL-04` 路径① **片 4b**）—— 模板 `模板-开会大表.xlsx` 的 `Sheet1`（20 列）。

## 形态（唯一登记处 = 交付面 `demo/模板/模板清单.md` §5.5 ＋ §二-7 ＋ §四-5）

| 行 | 内容 |
|---|---|
| R1 | 标题（`A1:S1` 合并）＋ `T1` = `单位：元` —— ⚠️ 标题里**写死的日期**由系统按核算月重写（§六-3） |
| R2~R4 | **三级表头**（模板自带；⛔ 不动） |
| R5 起 | **数据行**：`DATA_START` = **A5** ⇒ 一行一个项目（顺序 = 大表自己的顺序，§5.7.3） |
| 末行 | **合计行**（`A:C` 合并放 `合计：`；**可合计的列**给数值 —— `TOTAL_KEYS`；比率 / 开工时间 / 备注留空） |

⭐ **20 列全 A 类、同名同序**（§5.5 唯一完全一致的表）⇒ 列映射 = **恒等**：
  第 i 列 ↔ `big_domain.BIG_COLUMNS[i]`（⛔ 不手抄 20 个列字母 —— 抄了就会漂）。

⚠️⚠️ **四处公式必须「以数值覆盖」**（清单 §六-2）：数据行 `L = H+J`（外租使用合计）·
   `N = L/M`（使用率）· `O = Q/P`（产值完成率）＋ 合计行的 14 个 `=SUM(...)` ⇒ ⛔ 不留公式。
   且**分母为空 / 为 0 的比率列给 `None`**（页面显「—」）—— 域内核 `cell_value` 的出口，⛔ 不写 0。

⛔ 本模块只做**列映射 / 标题 / 数字格式**：不算金额、不筛项目、不拼路径
（行装配的主人 = `mod07_setl.big_service.build_big_data`，**与页面同一份**）。
"""

from __future__ import annotations

import calendar
import re
from decimal import Decimal
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from app.core.errors import MustReportError
from app.mod07_setl import big_domain as B
from app.report_export import resources, tpl_fill

#: 该模板的 sheet（`模板清单` §二-7）
SHEET = "Sheet1"

#: ⭐ 列映射（§5.5：**同名同序** ⇒ 恒等）——`{列 key: 列字母}`，第 i 列 ↔ `BIG_COLUMNS[i]`。
#: ⛔ 不写死 20 个字母：列结构的主人 = `big_domain.BIG_COLUMNS`（改了它这里跟着改）。
COL_OF_KEY: dict[str, str] = {c["key"]: get_column_letter(i + 1)
                              for i, c in enumerate(B.BIG_COLUMNS)}

#: 序号列（第一列）—— 走引擎的 `label`（这样它也会被**对账**读到，见 `verify_filled`）
SEQ_KEY: str = B.BIG_COLUMNS[0]["key"]

#: 「开工时间」列（写文本前要设文本格式的那一列，清单 §四-4 同款坑）
YM_COL: str = COL_OF_KEY[B.BIG_COLUMNS[2]["key"]]

#: 合计行首格（模板里 `合计：` 写在**合并区 A:C 的锚点 A** 上）
TOTAL_LABEL = "合计："

#: 标题里那两个**写死的日期括注**（`（数据截止8月31日）` / `（8月份数据）`）⇒ 系统重写（§六-3）。
_CUT = re.compile(r"（\s*数据截止[^）]*）")
_MON = re.compile(r"（\s*\d+\s*月份数据）")

#: 成品落盘目录名（`<root>/<报表名>/<期间标签>/…`）
FILE_SUFFIX = "活动大表"


def title_of(template_title, ym: str) -> str:
    """标题：把模板里那两个**写死的日期括注**换成核算月的（清单 §六-3：写死的日期由系统替换）。

    - `（数据截止8月31日）` ⇒ `（数据截止{M}月{当月末日}日）`（**当月末日按日历算**，⛔ 不写死 31）；
    - `（8月份数据）` ⇒ `（{M}月份数据）`；
    ⚠️ 认的是**那个括注的形态**（⛔ 不抄模板里的具体日期）；两个都找不到 ⇒ **拒做**（形态不认识）。
    """
    text = str(template_title or "")
    m = int(str(ym)[5:7])
    last = calendar.monthrange(int(str(ym)[:4]), m)[1]
    if not _CUT.search(text) or not _MON.search(text):
        raise MustReportError(
            "活动大表成品：模板标题里找不到那两个**日期括注**（`（数据截止…）` / `（…月份数据）`）"
            "⇒ 形态不认识，本引擎拒绝据此产出文件（清单 §六-3 登记了这两处由系统替换）。")
    return _MON.sub(f"（{m}月份数据）", _CUT.sub(f"（数据截止{m}月{last}日）", text))


def _value(row: dict, key: str):
    """该行该列的**成品值** —— 唯一出口 = `big_domain.cell_value`（⛔ 不在这里另算）。"""
    v = B.cell_value(row, key)[0]
    if v is None or v == "":
        return None
    return str(v) if key == B.BIG_COLUMNS[2]["key"] else v     # 开工时间 ⇒ 页面文本 `YYYY-MM`


def body_spec(data: dict) -> dict:
    """`build_big_data` 的结果 → 引擎 `spec`（数据行 ＋ **合计行**）。

    - 数据行的 `label` = **序号**（第一列）⇒ 它也会被对账读到（引擎只对账 `label` 列 ＋ 其余各列）；
    - 合计行只给**可合计的列**（`TOTAL_KEYS`）—— 其余列模板里本来就空，且比率列**不许合计**。
    """
    rows = list(data.get("rows") or ())
    body: list[tuple] = []
    for row in rows:
        cells = {COL_OF_KEY[c["key"]]: _value(row, c["key"])
                 for c in B.BIG_COLUMNS if c["key"] != SEQ_KEY}
        body.append((_value(row, SEQ_KEY), {k: v for k, v in cells.items() if v is not None}))
    totals = dict(data.get("totals") or {})
    # ⚠️ **不可得的总额给空串 = 显式留空**（清掉模板那格的 `=SUM(...)`）——
    #    清单 §六-2「算不出来 ⇒ 留空，⛔ 不写 0」；页面那一列显「—」，成品里就是**空**
    #    （典型：主材累计的取数口未接入 ⇒ `None`）。
    tail_cells = {COL_OF_KEY[k]: (totals[k] if totals.get(k) is not None else "")
                  for k in B.TOTAL_KEYS}
    return {"sheet": SHEET, "rows": body, "tail": {0: (TOTAL_LABEL, tail_cells)}}


def build_xlsx(data: dict, out_dir, *, name: str) -> str:
    """`build_big_data` 的结果 → **一本 xlsx** ⇒ 返回成品绝对路径。

    - 模板走 `resources.require_template`（缺失 / 被回退 ⇒ **显式拒做**）；
    - 产物一律过 `tpl_fill.verify_filled`（逐格 / 尾块以下残留 / 值覆盖不彻底 / 空行壳）。
    """
    template = resources.require_template(resources.BIG_TEMPLATE)
    out = Path(out_dir) / name
    wb = openpyxl.load_workbook(str(template))
    try:
        ws = wb[SHEET]
        ws["A1"] = title_of(ws["A1"].value, data["month"])     # ⚠️ 写死的日期由系统替换（§六-3）
        spec = body_spec(data)
        sheet_plan = tpl_fill.fill_sheet(ws, spec)
        tpl_fill.set_text_format(ws, sheet_plan, YM_COL)        # 「开工时间」列：写文本前先设文本格式
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(out))
    finally:
        wb.close()

    problems = tpl_fill.verify_filled(out, {"path": str(out), "sheets": [sheet_plan]})
    if problems:
        raise MustReportError(
            "活动大表成品**显示区对账未通过** ⇒ 已中止，未交付："
            + "；".join(problems[:5]) + ("" if len(problems) <= 5 else "（等共 %d 条）" % len(problems)))
    return str(out)


def file_name(ym: str) -> str:
    """成品文件名（**唯一出口**）：`经济活动分析大表_{期间标签}.xlsx`。

    ⚠️ 报表名取**页面/预览页**的 `big_view.TITLE`（「经济活动分析大表」）—— 那是它唯一的出处，
       ⛔ 不在这里再写一遍字面量；期间标签主人 = `mod07_setl.domain.period_label`。
    """
    from app.mod07_setl.domain import period_label
    from app.mod07_setl.big_view import TITLE

    return f"{TITLE}_{period_label(str(ym))}.xlsx"


__all__ = ["SHEET", "COL_OF_KEY", "SEQ_KEY", "YM_COL", "TOTAL_LABEL", "FILE_SUFFIX",
           "title_of", "body_spec", "build_xlsx", "file_name"]
