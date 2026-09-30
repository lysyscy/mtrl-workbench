"""**总欠款表**导出 —— 每个项目一行：`集采 / 辅材 / 机械` 三列欠款（用户 2026-09-20 定）。

## 用户口径（原文）

> 「还需要一个**总欠款导出**功能，包含**集采、辅材、机械**，分别是 **C D E 列**，
>   **A 列序号，B 列项目展示名**，你看下放哪合适」

## 落点决策（⛔ 别再找第二个地方）

**放「付款流水与欠款」页（`mod05`）**，理由三条：
1. **欠款的家在那儿** —— 用户想看欠款，第一反应就是那一页；`debt_by_category` / `DEBT-001-*`
   这套口径的主人也在那儿（`mod05_flow/domain.py`）。
2. **那一页已经有同类入口**（「逐月欠款台账」整本导出 · `/api/m05/ledger/export`）⇒ 两个出口**并排**，
   ⛔ 不用让用户跑到别的页去找。
3. **它天然是跨域的** —— 集采来自 `mod11`、辅材/机械来自本域、机械结算将来来自 `mod06`；
   放在**消费侧**（看欠款的地方）比放在任一**生产侧**都合理。

## 表形态（⚠️ 列序是**用户指定**的，⛔ 别"优化"成别的顺序）

| 列 | A | B | C | D | E |
|---|---|---|---|---|---|
| 含义 | 序号 | 项目展示名 | 集采 | 辅材 | 机械 |

## ⚠️ 两条必须如实说明的（否则这张表就是"看着正常的错数"）

1. **机械欠款目前不含「机械费结算」** —— 那个来源在 `MOD-06`（过程资料），**还没接通**
   （`service.MECH_SETTLE_SOURCE_READY = False`）⇒ 现在机械欠款 = **期初 − Σ机械付款**。
   ⚠️ 这件事**页面上是显式标出来的** ⇒ 导出的文件里**也必须标**（⛔ 否则文件一旦离开页面，
   读到的人会以为那是完整口径 —— 那是本项目最忌的一类错）。⇒ 见 `FOOTNOTE`，**写在表尾**。
2. **只算「纳入台账」的集采行** —— 「待确认 / 不纳入」的不计（它们按定义就不进台账）；
   排除了几条**在回执里报出来**（⛔ 禁静默）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl
from app import export_registry as EXP   # ⭐ 包间只按名取（表见 `app/export_bindings.py`）

#: 表头（**列序由用户指定**：A 序号 · B 项目 · C 集采 · D 辅材 · E 机械）。
COLUMNS: tuple[str, ...] = ("序号", "项目", "集采", "辅材", "机械")

#: ⚠️ 机械口径**未接通**时写在表尾的说明（⛔ 别删 —— 见模块头第 1 条）。
FOOTNOTE = ("说明：①「机械」欠款未含「机械费结算」（该来源尚未接通）⇒ 现为「期初 − 已付款」；"
            "② 本表只计「纳入台账」的集采合同；③ 金额单位＝元；④ 本表为实时口径，不是某月账。")

FILE_PREFIX = "总欠款"


def file_name(today: date | None = None) -> str:
    """`总欠款_YYYYMMDD.xlsx`（⚠️ 不写"截至某月"—— 它是**实时**口径，不是某月账）。"""
    d = today or date.today()
    return f"{FILE_PREFIX}_{d.strftime('%Y%m%d')}.xlsx"


def build_xlsx(items: list[dict], out_dir: Path, *, mark_mech: bool = True,
               today: date | None = None) -> str:
    """写出一张总欠款表 ⇒ 返回**绝对路径**。

    `items` = `[{"index": 1, "project": "…展示名…", "jc": Decimal, "material": Decimal,
    "mech": Decimal}, …]`（⚠️ 顺序即行序 · ⛔ 本函数不排序、不筛选、不算钱）。
    `mark_mech` = 是否写那句机械说明（= `not MECH_SETTLE_SOURCE_READY`）。

    ⚠️ 金额**写成数值**（不是字符串）—— 这一列用户多半要自己再求和；
      字符串会让 Excel 的 `Σ` 静默变 0（本项目在别处踩过"文本数字"的坑）。
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "总欠款"
    ws.append(list(COLUMNS))
    for cell in ws[1]:
        cell.font = openpyxl.styles.Font(bold=True)

    total_jc = total_mat = total_mech = Decimal("0")
    for it in items:
        jc = Decimal(str(it.get("jc") or 0))
        mat = Decimal(str(it.get("material") or 0))
        mech = Decimal(str(it.get("mech") or 0))
        total_jc, total_mat, total_mech = total_jc + jc, total_mat + mat, total_mech + mech
        ws.append([int(it.get("index") or 0), str(it.get("project") or ""),
                   float(jc), float(mat), float(mech)])

    # ⭐ 合计行：**只对三列金额求和**（⛔ A/B 留空 —— 别写"合计"到项目列里）
    ws.append(["", "合计", float(total_jc), float(total_mat), float(total_mech)])
    for cell in ws[ws.max_row]:
        cell.font = openpyxl.styles.Font(bold=True)

    if mark_mech:
        ws.append([])
        ws.append([FOOTNOTE])
        ws.cell(row=ws.max_row, column=1).alignment = openpyxl.styles.Alignment(wrap_text=False)

    for col, width in zip("ABCDE", (6, 46, 16, 16, 16)):
        ws.column_dimensions[col].width = width

    save_workbook = EXP.get("save").save_workbook
    out = save_workbook(wb, Path(out_dir) / file_name(today))
    return str(out)


__all__ = ["COLUMNS", "FOOTNOTE", "FILE_PREFIX", "file_name", "build_xlsx"]
