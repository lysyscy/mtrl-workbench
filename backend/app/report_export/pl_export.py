"""`MOD-04` 付款计划审查结果的 **Excel 导出**（`TAIL-04` · `REQ-R1` · §7.1）。

⭐ `TAIL-04` 的**倒数第 2 张页**（本件之后只剩 `MOD-03` 付款通知书台账）。
   共用件 = `report_export/naive_export.py`（**朴素导出**那一档，口径见它的模块头）。

**口径（§7.1）**：

- **行** = **页面上当前看到的那些**（调用方传 id 列表，**按传入顺序**出）⇒
  前端筛选（单据年月 / 多选项目 / 审查结果两档）与后端 **100% 一致**。
- **列** = **页面表头 `PL_THEAD` 去掉「勾选 / 操作」两列** ⇒ 13 列。
- **取值** = **页面显示的那个值**：下面逐列说明，凡有"页面把两样东西并进一格"的，导出**并进去**
  （⛔ 另开一列会让表与屏幕**对不上号** —— 同 `fl_export` 的「状态 ＋ 撤销原因」）。

## 逐列的口径（⚠️ 每一列都对着 `index.html` 的 `V.m04` 行渲染逐条核过）

| 列 | 页面那格显示 | 导出取什么 |
|---|---|---|
| `#` | `${p.id}`（＋「手动」徽标） | `id`（手动标记**并进同一格**：`12（手动）`） |
| 年月 | `${p.ym}` | `year_month` |
| 项目（填报…） | `plProjCell`：**唯一命中 ⇒ 展示名**；0 命中 ⇒ 填报原值 ＋「未匹配」；多命中 ⇒ 填报原值 ＋「重名 N 条」 | 同左（判定用后端的 `match_status`，⛔ 不在导出层重算匹配） |
| 单据号 | 未匹配行是**输入框**、已匹配行是文本；空 ⇒ 「未填」小标 | `doc_no`（**空就空着** —— 「未填」是屏幕上的小标，不是值） |
| i8 流程金额 / 本月预付款金额 | `M(...)` | **数字**（要合计，见下） |
| 已付款金额 / 剩余付款金额 | `hit ? M(...) : —` | **数字**；**未命中就空着**（⛔ 不写 0） |
| 付款时间 / 付款方式 / 备注 | 行内可改控件，值是数据 | 原值 |
| 审查结果 | `tag(rv)`（＋「已强制通过」徽标） | `audit_result`（强制标记**并进同一格**） |
| 处理 | 完全匹配 ⇒ 「无需处理」；已强制 ⇒ **强制备注**；否则 ⇒ **一个按钮** | 见下「处理那一列」 |

⚠️ **「处理」那一列是有意改写的**：它在页面上**是个按钮**（`强制通过`）—— 按「控件不导出」本应留空，
   但**整列留空会让人以为漏了数据**，而"这行处理了没有"正是**这张表最要紧的一件事**
   （§4.3.4 的审查结果就是要人来处置的）。
   ⇒ 导**状态词**：完全匹配 ⇒ `无需处理`（页面原话）；已强制 ⇒ 强制备注（页面原话）；
   否则 ⇒ **`未处理`** —— ⚠️ 这个词**不是新造的**：页面自己的口径说明第 3 条与
   「取消强制通过」按钮的提示语都写「回到「**未处理**」态」（§4.3.4）。⛔ 不导按钮。

⚠️ **合计行**：页面 `sumRowOf(PL_THEAD, list, {5:…, 8:…})` —— **只合「i8 流程金额」与「本月预付款金额」两列**。
   ⇒ 本件 `TOTAL_KEYS` 就是这两列；⚠️「已付款 / 剩余付款」是金额但**不合计**（页面不合计它们，
   硬加两格合计就是**凭空多出来的数** —— `naive_export` 把「写数字」与「要合计」拆成两个集合正是为此）。
"""

from __future__ import annotations

from app.report_export import naive_export as N

#: 导出的列（**顺序 = 页面表头 `PL_THEAD` 顺序**去掉「勾选 / 操作」）⇒ 导出的表与屏幕**并排看能对上**。
#: 第二项 = 行字典里的键（由 `mod04_plan.router.export_plans` 按口径解析好）。
COLUMNS: tuple[tuple[str, str], ...] = (
    ("#", "id_text"),
    ("年月", "year_month"),
    ("项目（填报：展示名 / 仓库名）", "project_text"),
    ("单据号（计划填报）", "doc_no"),
    ("i8 流程金额", "flow_amount"),
    ("已付款金额", "paid_amount"),
    ("剩余付款金额", "unpaid_amount"),
    ("本月预付款金额", "planned_amount"),
    ("付款时间", "pay_date"),
    ("付款方式", "pay_method"),
    ("备注", "remark"),
    ("审查结果", "audit_text"),
    ("处理", "handle_text"),
)

#: **写数字**的列（Excel 里能直接求和/排序）—— ⛔ 见模块头「金额例外」。
MONEY_KEYS: frozenset[str] = frozenset({
    "flow_amount", "paid_amount", "unpaid_amount", "planned_amount",
})

#: **要合计**的列（⚠️ 与 `MONEY_KEYS` **故意不同**：页面只合这两列 —— 见模块头「合计行」）。
TOTAL_KEYS: frozenset[str] = frozenset({"flow_amount", "planned_amount"})

SHEET_NAME = "付款计划审查结果"


def build_xlsx(rows: list[dict]) -> bytes:
    """行字典列表 ⇒ 一本 xlsx 的**字节**（不落盘：调用方决定给谁）。"""
    return N.build_xlsx(
        rows,
        columns=COLUMNS,
        sheet_name=SHEET_NAME,
        money_keys=MONEY_KEYS,
        total_keys=TOTAL_KEYS,
    )


__all__ = ["COLUMNS", "MONEY_KEYS", "SHEET_NAME", "TOTAL_KEYS", "build_xlsx"]
