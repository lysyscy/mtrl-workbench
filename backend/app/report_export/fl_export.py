"""`MOD-05` 付款流水的 **Excel 导出**（`TAIL-04` · `REQ-R1` · §7.1）。
⭐ `TAIL-04` 的第 2 张页（第 1 张是 `report_export/pj_export.py`）—— 同样走**朴素导出**那一档。

**口径（§7.1）**：

- **行** = **页面上当前看到的那些**（调用方传 id 列表，**按传入顺序**出）⇒
  前端筛选（年月 / 多选项目 / 付款方式 / 状态 / 关键词）与后端 **100% 一致**。
  ⭐ **为什么不传"筛选条件"**：页面的筛选是**前端**算的 ⇒ 传条件就得在后端**再实现一遍**
  ⇒ **两套口径必打架**（本项目的旧账）。⭐ 传 id 还顺带把**顺序**带上了。
- **列** = **页面表头 `FL_THEAD` 去掉「操作」那一列**（操作是"撤销"按钮，不是数据）⇒ **14 列**。
- **取值** = **页面显示的那个值**：
  · 「状态」页面渲染的是 `enumTag('flowState', …)`（**中文**：生效 / 已撤销 ＋ 撤销原因）
    ⇒ ⭐ 用后端的 `status_label`（`_flow_dict` 已经给了中文），⛔ 不导 `effective`/`revoked` 原文；
  · 「实际付款方式」页面渲染 `enumTag('payMethod', …)` —— 但该字段本身**存的就是中文**
    （默认兜底「现汇」）⇒ 原样导 ✓
  · 「付款项目」= **展示名**（`project_display`，⛔ 不是仓库名那个"键"、更不是 `project_id`）。

⭐⭐ `TAIL-283`（2026-10-11）**列义修正**（这一版的两处"说错话"，用户报障的根）：
  · 首列「流水号」原先导的是**数据库行主键 `id`** —— 那是"撤销 / 导出定位"用的技术键，
    和业务流水号 `flow_no` 是**两个东西** ⇒ 改为真 `flow_no`；
    ⚠️ `id` **不再出现在导出列里**（它只服务撤销按钮与 `export_flows(ids)` 的入参）。
  · 「操作人」原先取的是**创建时间**（`adaptFlow` 的旧账）⇒ 本件一直导 `created_by` ✓，
    壳侧同批改成显示 `created_by`（页面与 Excel 同义）。
  · 新增通知书五项（日期 / 名称 / 收款单位 / 审批金额 / 分类）—— 与页面一一对应。

⚠️ **不做"看起来像个表"的假合计以外的东西**：本表**只有 1 个合计列**（付款金额）
⇒ ⭐ **合计行有意义**（与 `jc_export` 同类）⇒ 写它，但**只合付款金额**：
  · 「审批金额」是**同一张通知书在每笔上重复出现的对照数** ⇒ 纵向加起来是**假数**
    （1000 审批 ＋ 两笔 300/200 ⇒ 合计 500，⛔ 不是 2000）；
  · 材料名 / 备注那些**不合计**（对文本求和没有意义，硬凑只会让人以为那是业务指标）。

⚠️ ⛔ **不导「撤销原因」为单独一列**：页面把它**并进「状态」那格**（`已撤销 ＋ 原因`）
⇒ 导出也**并进去**（列数与页面一致）。⭐ 想让人一眼看出"为什么撤的"，
就写在同一个格里 —— 另开一列会让表与屏幕**对不上号**。
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

#: 导出的列（**顺序 = 页面表头 `FL_THEAD` 顺序**去掉「操作」）⇒ 14 列，导出的表与屏幕**并排看能对上**。
COLUMNS: tuple[tuple[str, str], ...] = (
    ("流水号", "flow_no"),
    ("单据编码", "doc_no"),
    ("通知书日期", "doc_date"),
    ("通知书名称", "bill_name"),
    ("付款项目", "project_display"),
    ("收款单位", "payee"),
    ("分类", "category_label"),
    ("审批金额", "amount_approved"),
    ("付款日期", "pay_date"),
    ("付款金额", "amount"),
    ("实际付款方式", "pay_method"),
    ("备注", "remark"),
    ("操作人", "created_by"),
    ("状态", "status_text"),
)

#: **写数字**的列（金额一律写 `float`，这样用户在 Excel 里能直接求和/排序）。
#: ⚠️ 它与下面的 `TOTAL_KEYS` **不是一回事**（`TAIL-62` 起就是三个独立参数，⛔ 别并成一个）：
#:    「写数字」= 这一列长什么样；「要合计」= 哪几列加总；两者混用会同时把审批与撤销合计做错。
MONEY_KEYS: frozenset[str] = frozenset({"amount", "amount_approved"})

#: **参与求和**的列 —— ⭐ 只有**付款金额**（审批金额是"每笔重复的对照数"，见模块头）。
TOTAL_KEYS: frozenset[str] = frozenset({"amount"})

SHEET_NAME = "付款流水"


def _money(v) -> float | None:
    """金额 ⇒ `float`（⛔ 空的**留空**，不写 0 —— "没这个数"与"是 0"是两件事）。"""
    if v in (None, ""):
        return None
    try:
        return float(Decimal(str(v)))
    except Exception:                       # noqa: BLE001 —— 认不出就当空（⛔ 不抛，别为一行毁整表）
        return None


def build_xlsx(rows: list[dict], total_rows: list[dict] | None = None,
               total_always: bool = False) -> bytes:
    """行字典列表 ⇒ 一本 xlsx 的**字节**（不落盘：调用方决定给谁）。

    ⭐ `TAIL-62`（2026-09-21）：**实现已下沉到 `naive_export`**（本件是它的前身之一）⇒
      这里只留一层**薄委托**。⛔ 列定义 / 金额键**仍在本件**（那是**付款流水页的口径**），
      下沉的只有"怎么写成 xlsx"这一件事 ⇒ 现在**只有一个主人**。

    ⭐ `TAIL-283`：新增 `total_rows`（**哪些行参与合计**）—— 口径 = **生效**流水；
      ⛔ 别把 `rows`（屏幕上选中的，可能含已撤销）直接当求和基数：那会把撤掉的也加进去。
      `None` = 与 `rows` 同（老行为，只给"自己就是全量生效行"的调用方用）。
    ⭐ `total_always`：**基数一个都没有也写合计行** —— 选中行全已撤销时，屏幕上写的就是
      「合计（生效 0 条）¥0.00」⇒ 导出必须有那一行（见 `naive_export` 模块头）。⚠️ 透传参数，
      它**不能**让"一个 id 都没挑到"也写合计行（那层由内核的 `rows` 判定守）。

    ⚠️ 表头**加粗**＋**冻结首行**：几十行的表滚起来没有冻结行，人对不上哪列是哪列。
    ⚠️ 金额列写**数字**（⛔ 不写字符串）：这样用户在 Excel 里能直接求和/排序。
    """
    from app.report_export import naive_export as N
    return N.build_xlsx(rows, columns=COLUMNS, sheet_name=SHEET_NAME,
                        money_keys=MONEY_KEYS, total_keys=TOTAL_KEYS, total_rows=total_rows,
                        total_always=total_always)


__all__ = ["COLUMNS", "MONEY_KEYS", "TOTAL_KEYS", "SHEET_NAME", "build_xlsx"]
