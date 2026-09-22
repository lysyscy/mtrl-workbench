"""`MOD-05` 付款流水的 **Excel 导出**（`TAIL-04` · `REQ-R1` · §7.1）。

⭐ `TAIL-04` 的第 2 张页（第 1 张是 `report_export/pj_export.py`）—— 同样走**朴素导出**那一档。

**口径（§7.1）**：

- **行** = **页面上当前看到的那些**（调用方传 id 列表，**按传入顺序**出）⇒
  前端筛选（年月 / 多选项目 / 付款方式 / 状态 / 关键词）与后端 **100% 一致**。
  ⭐ **为什么不传"筛选条件"**：页面的筛选是**前端**算的 ⇒ 传条件就得在后端**再实现一遍**
  ⇒ **两套口径必打架**（本项目的旧账）。⭐ 传 id 还顺带把**顺序**带上了。
- **列** = **页面表头 `FL_THEAD` 去掉「操作」那一列**（操作是"撤销"按钮，不是数据）⇒ 9 列。
- **取值** = **页面显示的那个值**：
  · 「状态」页面渲染的是 `enumTag('flowState', …)`（**中文**：生效 / 已撤销 ＋ 撤销原因）
    ⇒ ⭐ 用后端的 `status_label`（`_flow_dict` 已经给了中文），⛔ 不导 `effective`/`revoked` 原文；
  · 「实际付款方式」页面渲染 `enumTag('payMethod', …)` —— 但该字段本身**存的就是中文**
    （默认兜底「现汇」）⇒ 原样导 ✓
  · 「付款项目」= **展示名**（`project_display`，⛔ 不是仓库名那个"键"、更不是 `project_id`）。

⚠️ **不做"看起来像个表"的假合计以外的东西**：本表**只有 1 个金额列**（付款金额）
⇒ ⭐ **合计行有意义**（与 `jc_export` 同类）⇒ 写它，但**只合金额列**，
材料名 / 备注那些**不合计**（对文本求和没有意义，硬凑只会让人以为那是业务指标）。

⚠️ ⛔ **不导「撤销原因」为单独一列**：页面把它**并进「状态」那格**（`已撤销 ＋ 原因`）
⇒ 导出也**并进去**（列数与页面一致 = 9 列）。⭐ 想让人一眼看出"为什么撤的"，
就写在同一个格里 —— 另开一列会让表与屏幕**对不上号**。
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

#: 导出的列（**顺序 = 页面表头顺序**去掉「操作」）⇒ 导出的表与屏幕**并排看能对上**。
COLUMNS: tuple[tuple[str, str], ...] = (
    ("流水号", "id"),
    ("单据编码", "doc_no"),
    ("付款项目", "project_display"),
    ("付款日期", "pay_date"),
    ("付款金额", "amount"),
    ("实际付款方式", "pay_method"),
    ("备注", "remark"),
    ("操作人", "created_by"),
    ("状态", "status_text"),
)

#: 金额列（**只对这些列合计**）。
MONEY_KEYS: frozenset[str] = frozenset({"amount"})

SHEET_NAME = "付款流水"


def _money(v) -> float | None:
    """金额 ⇒ `float`（⛔ 空的**留空**，不写 0 —— "没这个数"与"是 0"是两件事）。"""
    if v in (None, ""):
        return None
    try:
        return float(Decimal(str(v)))
    except Exception:                       # noqa: BLE001 —— 认不出就当空（⛔ 不抛，别为一行毁整表）
        return None


def build_xlsx(rows: list[dict]) -> bytes:
    """行字典列表 ⇒ 一本 xlsx 的**字节**（不落盘：调用方决定给谁）。

    ⭐ `TAIL-62`（2026-09-21）：**实现已下沉到 `naive_export`**（本件是它的前身之一）⇒
      这里只留一层**薄委托**。⛔ 列定义 / 金额键**仍在本件**（那是**付款流水页的口径**），
      下沉的只有"怎么写成 xlsx"这一件事 ⇒ 现在**只有一个主人**。

    ⚠️ 表头**加粗**＋**冻结首行**：几十行的表滚起来没有冻结行，人对不上哪列是哪列。
    ⚠️ 金额列写**数字**（⛔ 不写字符串）：这样用户在 Excel 里能直接求和/排序。
    """
    from app.report_export import naive_export as N
    return N.build_xlsx(rows, columns=COLUMNS, sheet_name=SHEET_NAME,
                        money_keys=MONEY_KEYS, total_keys=MONEY_KEYS)


__all__ = ["COLUMNS", "MONEY_KEYS", "SHEET_NAME", "build_xlsx"]
