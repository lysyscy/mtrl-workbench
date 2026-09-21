"""`MOD-03` 付款通知书台账的 **Excel 导出**（`TAIL-04` · `REQ-R1` · §7.1）。

⭐ `TAIL-04` 的**最后一张页**（本件之前是 `MOD-04` 的 `pl_export.py`）。
   共用件 = `report_export/naive_export.py`（**朴素导出**那一档，口径见它的模块头）。

**口径（§7.1）**：

- **行** = **页面上当前看到的那些**（调用方传 id 列表，**按传入顺序**出）⇒
  前端筛选（年月 / 多选项目 / 分类 / 审批状态 / 付款状态）与后端 **100% 一致**。
- **列** = **页面表头 `NT_THEAD` 去掉「勾选 / 操作」两列** ⇒ **16 列**。
  ⚠️ 三个金额列的**表头带 `✎`**（`付款金额 ✎` / `统计结算金额 ✎` / `统计付款金额 ✎`）——
     那是**页面表头原文**（✎ = "这格在页面上可改"），照抄 ⇒ 导出的表与屏幕**并排看能对上**。
     ⛔ 别"顺手"把 ✎ 洗掉：洗净了表头就对不上屏幕，而这条正是本节的口径。
- **取值** = **页面显示的那个值**（逐列口径见下）。

## 逐列的口径（⚠️ 每一列都对着 `index.html` 的 `V.m03` 行渲染逐条核过）

| 列 | 页面那格显示 | 导出取什么 |
|---|---|---|
| 单据日期 / 单据编码 / 单据名称 / 业务类型 / 收款单位 / 录入人 | 纯文本 | 原值 |
| 付款项目 | `dispCell(n.proj,n)` ⇒ **展示名** | 后端的 `project_display`（= 展示名） |
| 分类 | 剔除行 ⇒ 「剔除」；i8 撤单行 ⇒ 「i8 已撤单」；否则 ⇒ 中文分类下拉 | 同左（**判定顺序也照抄**：先剔除、后撤单） |
| 集采实际供应商 | 值 ／ 非集采行 ⇒ 「—」 | 原值（⛔ 不替非集采行写 "—"：那是屏幕上的占位符，导出**留空**） |
| 审批金额 / 统计结算金额 / 统计付款金额 | 纯文本（含千分位） | **数字**（要合计 —— 见下） |
| 付款金额 ✎ | 输入框，值 = **本次应付** `payEff` | ⭐ 见下「付款金额那一列」 |
| 已付金额 | `paidOf`（0 显示为 `0.00`） | **数字** |
| 审批状态 / 付款状态 | 中文标签（已批/未批 · 已付清/未付清） | 后端的**中文原文**（⛔ 不导 `approve_status` 的英文或空） |

⚠️ **「付款金额」那一列**：页面上 = `payEff(n)`，**默认 = 审批金额 − 已付金额**
   （后端 `NoticeRow.pay_amount` 这条派生属性**就是同一个式子**，§4.2.5）⇒ 取后端那个值即可。
   ⚠️ **页面上"仅本次会话"的手改**（壳的 `payOv`：不落库、刷新即失效、也**不算进欠款口径**）
      **不进导出** —— 它不是数据，后端也无从得知。⇒ 导出的永远是**派生默认值**。

⚠️ **合计行**：页面 `sumRowOf(NT_THEAD, sumRows, {10…14})`，且
   **`sumRows = list.filter(ntLive)`** —— 即「**剔除行不计入**」；切到「分类 = 剔除」时
   该视图全是剔除行 ⇒ **页面没有合计行**（不给一排 0，免得看着像坏了）。
   ⇒ 本件照抄：`TOTAL_KEYS` = 那 5 个金额列，`total_rows` = **传入行里的「有效行」**
   （判据 = 后端的 `NoticeRow.is_live`，⛔ 不在导出层另写一份口径）；**一行有效行都没有 ⇒ 不写合计行**。
   ⚠️ 「有牵涉的撤单行**仍算有效**」这条（§4.2.7：不许静默丢账）**也在 `is_live` 里** —— 见它的 docstring。
"""

from __future__ import annotations

from app.report_export import naive_export as N

#: 导出的列（**顺序 = 页面表头 `NT_THEAD` 顺序**去掉「勾选 / 操作」）⇒ 导出的表与屏幕**并排看能对上**。
#: 第二项 = 行字典里的键（由 `mod03_notice.notice_api_router.export_notices` 按口径解析好）。
COLUMNS: tuple[tuple[str, str], ...] = (
    ("单据日期", "doc_date"),
    ("单据编码", "bill_no"),
    ("付款项目", "project_display"),
    ("分类", "category_text"),
    ("单据名称", "bill_name"),
    ("业务类型", "biz_type"),
    ("收款单位", "payee"),
    ("集采实际供应商", "jc_supplier"),
    ("录入人", "input_by"),
    ("审批金额", "amount_approved"),
    ("付款金额 ✎", "pay_amount"),
    ("已付金额", "amount_paid"),
    ("统计结算金额 ✎", "stat_settle"),
    ("统计付款金额 ✎", "stat_paid"),
    ("审批状态", "approve_status"),
    ("付款状态", "pay_status"),
)

#: **写数字**的列（Excel 里能直接求和/排序）—— ⛔ 见模块头「金额例外」。
MONEY_KEYS: frozenset[str] = frozenset({
    "amount_approved", "pay_amount", "amount_paid", "stat_settle", "stat_paid",
})

#: **要合计**的列 —— 与 `MONEY_KEYS` 相同（这 5 列页面都合计）；⚠️ 但**行**还要过 `is_live`（见模块头）。
TOTAL_KEYS: frozenset[str] = MONEY_KEYS

SHEET_NAME = "付款通知书台账"


def build_xlsx(rows: list[dict], *, live_rows: list[dict]) -> bytes:
    """行字典列表 ⇒ 一本 xlsx 的**字节**（不落盘：调用方决定给谁）。

    `live_rows` = **参与合计的「有效行」**（= `rows` 里 `NoticeRow.is_live` 为真的那些）。
    ⚠️ **必传、不给默认值** —— 有默认值就有人会省略它，而省略 = **合计把剔除行也算进去**
       （§4.2.7 的"不许静默丢账"反过来读：也不许把**已剔除**的账算回来）。
    ⚠️ **给空序列 ⇒ 不写合计行**（页面同口径：切到「分类 = 剔除」时页面就没有合计行）。
    """
    return N.build_xlsx(
        rows,
        columns=COLUMNS,
        sheet_name=SHEET_NAME,
        money_keys=MONEY_KEYS,
        total_keys=TOTAL_KEYS,
        total_rows=list(live_rows),
    )


__all__ = ["COLUMNS", "MONEY_KEYS", "SHEET_NAME", "TOTAL_KEYS", "build_xlsx"]
