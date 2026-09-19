"""`MOD-03` **批量付款窗口**（能力 7 / 8 · §4.4.1 / §4.4.4）—— 组装 ＋ 页面。

口径（《说明书》）：
- **§4.4.1 唯一自动核验项 = 审批状态「已批」**（发票核验 / 集采先付款特例**都不做**）。
- **§4.4.4**：**勾选若干条 → 一次动作**（**不做逐行付款按钮**）· 窗口内**每行可"移出本次付款"**·
  存在不可付行 ⇒ **「确认付款」直接禁用**（不是点了才拦）＋ 说明原因与解决路径 ·
  提交时**整批重算**，任一不过 ⇒ **整批不产生任何流水**（不落半批）·
  **实际付款方式默认取付款计划的值，取不到兜底「现汇」**· 提交按钮按下即锁定（`request_id`，防连点）。
- **§4.4.2**：**一次付款一条独立流水**；付款状态只有两态、判定基准 = 审批金额。
- **§4.2.7**：**凡"勾选 → 付款"链上的准入判据一律排除撤单行**（它的单据在 i8 侧已被删除）。

⚠️ 判定一律调 `domain.check_batch` / `confirm_batch` / `remove_from_batch`（**本文件不重写判定**）。
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.mod03_notice.domain import (
    APPROVE_STATUS_DONE,
    BatchCheck,
    PayDraft,
    PayRow,
    check_batch,
    confirm_batch,
)
from app.mod03_notice.list_view import build_rows
from app.mod03_notice.notice_page_http import PAY_URL
from app.mod03_notice.page import (
    BASE_CSS,
    DEFAULT_EMPTY_TEXT,
    esc,
    render_list_page,
)
from app.mod05_flow.models import PAY_METHODS

PAGE_ID = "m03-pay"
PAY_FORM_ID = "f-pay"
_FA = f' form="{PAY_FORM_ID}"'

TIPS = (
    "**批量付款**：勾选若干条 → 一次动作；**不做逐行付款按钮**（§4.4.4）。",
    "**唯一核验项 = 审批状态「已批」**（发票核验、集采「先付款特例」**都不做**，§4.4.1）。",
    "「本次应付」= 列表上的**付款金额**（审批金额 − 已付金额），可在本窗口逐行改小；"
    "**超过本次应付会被拦下**（不能多付）。",
    "**实际付款方式**默认取付款计划的值，取不到兜底「现汇」；可在本窗口逐行改（§4.4.2）。",
    "**存在不可付行 ⇒ 「确认付款」直接禁用**并说明原因与解决路径；提交时**整批重算**，"
    "任一不过 ⇒ **整批不产生任何流水**（不落半批）。",
    "**每行可「移出本次付款」**（同时取消该行勾选），调整时**其它行已填的付款方式 / 金额不会丢**。",
    "**撤单行与已剔除的行都不参与付款** —— 它们会被自动排除并在页面上**列出原因**（撤单 = §4.2.7；剔除 = 用户 2026-09-16 裁定）。",
)

# 付款窗口里**不予纳入**的行（并说明原因，绝不静默丢弃）
SKIP_REVOKED = "i8 已撤单行不参与付款（该单据在 i8 侧已被删除，再付款只会加深牵涉 —— §4.2.7）"
# ⚠️ **用户 2026-09-16 明确裁定「剔除行不能进付款」**（§4.2.7 只明写了撤单行，剔除行这条由用户口述定案）
SKIP_EXCLUDED = "已剔除的行**不参与付款**（它与本域无关、不进统计；用户 2026-09-16 裁定 —— §4.2.2）"


# ⚠️ 2026-09-19（`§19` 批 4 · **S3a / S4②**）：`default_pay_method` 与 `plan_methods_for_pay` 已
#    **搬进存活件** `notice_actions.py`（本件是**会被删**的页面件 ✗）—— 这里**反向 import** 它们，
#    保持本模块的对外行为一字不变 ✓。⛔ 别再在本文件里重写一份（两份实现是本仓的老毛病）。
from app.mod03_notice.notice_actions import (  # noqa: E402,F401
    default_pay_method,
    plan_methods_for_pay,
)


def build_pay_window(
    session, ids, *, flows_of=None, plan_methods: dict | None = None, overrides: dict | None = None
) -> dict:
    """批量付款窗口的数据（§4.4.4）—— 组装 + 跑**前置状态**判定（不做任何写入）。

    `plan_methods` —— `单据号 -> 付款计划的付款方式`（§4.4.2 的默认值来源）；不传则查 `plan_row`。
    `overrides` —— `{"m_<id>": 付款方式, "a_<id>": 金额}`：**移出某行时把其它行已填值带回**
    （R14③：调整不得丢失已填内容）。
    """
    ov = overrides or {}
    wanted = [int(i) for i in ids or []]
    rows = build_rows(session, flows_of=flows_of)
    by_id = {r.notice_id: r for r in rows}

    if plan_methods is None:
        plan_methods = plan_methods_for_pay(session)

    selected: list = []
    skipped: list[tuple[int, str]] = []
    for nid in wanted:
        row = by_id.get(nid)
        if row is None:
            skipped.append((nid, "该行不存在（可能已被删除）"))
        elif row.i8_revoked:
            skipped.append((nid, SKIP_REVOKED))
        elif row.excluded:
            skipped.append((nid, SKIP_EXCLUDED))
        else:
            selected.append(row)

    pay_rows = [
        PayRow(notice_id=r.notice_id, approve_status=r.approve_status, payable=r.pay_amount)
        for r in selected
    ]
    check: BatchCheck = check_batch(pay_rows)

    items = []
    for row, pr in zip(selected, pay_rows):
        items.append(
            {
                "notice_id": row.notice_id,
                "bill_no": row.bill_no,
                "doc_date": row.doc_date,
                "project_display": row.project_display or row.project_name,
                "category": row.category,
                "approve_status": row.approve_status,
                "amount_approved": f"{row.amount_approved:,.2f}",
                "amount_paid": f"{row.amount_paid:,.2f}",
                "payable": f"{row.pay_amount:,.2f}",
                "payable_raw": str(ov.get(f"a_{row.notice_id}") or f"{row.pay_amount:.2f}"),
                # §4.4.2：默认取**付款计划**的付款方式；取不到兜底「现汇」
                "pay_method": str(
                    ov.get(f"m_{row.notice_id}") or default_pay_method(row.bill_no, plan_methods)
                ),
                "blocked": pr.block() is not None,
                "block_reason": pr.label,
            }
        )

    return {
        "request_id": uuid4().hex,          # 防重复提交（§4.4.4：提交按钮按下即锁定）
        "items": items,
        "skipped": skipped,
        "check": check,
        "total_payable": f"{sum((r.pay_amount for r in selected), start=Decimal('0')):,.2f}",
        "pay_methods": list(PAY_METHODS),
        "tips": list(TIPS),
        "approve_done": APPROVE_STATUS_DONE,
    }


# ---------------------------------------------------------------- 渲染


def _row_html(item: dict, methods: list[str]) -> str:
    """一行：付款方式 ＋ 本次付款金额 ＋ 移出按钮（不可付行 → **就地禁用**并给原因，R14①）。"""
    nid = item["notice_id"]
    method_opts = "".join(
        f'<option value="{esc(m)}"{" selected" if m == item["pay_method"] else ""}>{esc(m)}</option>'
        for m in methods
    )
    if item["blocked"]:
        return (
            f'<tr class="blocked"><td>{esc(item["bill_no"])}</td><td>{esc(item["doc_date"])}</td>'
            f'<td>{esc(item["project_display"])}</td><td>{esc(item["approve_status"])}</td>'
            f'<td class="num">{esc(item["amount_approved"])}</td>'
            f'<td class="num">{esc(item["amount_paid"])}</td>'
            f'<td class="num">{esc(item["payable"])}</td>'
            f'<td colspan="3"><span class="tag dg">不可付</span> {esc(item["block_reason"])}'
            f'　<button{_FA} name="move" value="{nid}" title="把它移出本次付款（同时取消该行勾选）">移出本次付款</button>'
            "</td></tr>"
        )
    return (
        f'<tr><td>{esc(item["bill_no"])}</td><td>{esc(item["doc_date"])}</td>'
        f'<td>{esc(item["project_display"])}</td><td>{esc(item["approve_status"])}</td>'
        f'<td class="num">{esc(item["amount_approved"])}</td>'
        f'<td class="num">{esc(item["amount_paid"])}</td>'
        f'<td class="num">{esc(item["payable"])}</td>'
        f'<td><select name="m_{nid}"{_FA}>{method_opts}</select></td>'
        f'<td class="num"><input name="a_{nid}" value="{esc(item["payable_raw"])}" class="cell num"{_FA} '
        f'title="不得超过本次应付 {esc(item["payable"])}"></td>'
        f'<td><button{_FA} name="move" value="{nid}" title="把它移出本次付款（同时取消该行勾选）">移出本次付款</button></td>'
        "</tr>"
    )


def render_pay_page(data: dict, *, message: str = "", message_kind: str = "ok") -> str:
    """渲染批量付款窗口（独立页 `/m03/pay`；**共用同一次勾选**的结果）。"""
    check: BatchCheck = data["check"]
    items = data["items"]

    columns = [
        {"key": "bill_no", "label": "单据编码", "sortable": False, "cls": "", "vsep": False, "width": "126px"},
        {"key": "doc_date", "label": "单据日期", "sortable": False, "cls": "", "vsep": False, "width": "96px"},
        {"key": "project_display", "label": "付款项目", "sortable": False, "cls": "", "vsep": False, "width": ""},
        {"key": "approve_status", "label": "审批状态", "sortable": False, "cls": "", "vsep": False, "width": "74px"},
        {"key": "amount_approved", "label": "审批金额", "sortable": False, "cls": "num", "vsep": False, "width": "112px"},
        {"key": "amount_paid", "label": "已付金额", "sortable": False, "cls": "num", "vsep": False, "width": "106px"},
        {"key": "payable", "label": "本次应付", "sortable": False, "cls": "num", "vsep": False, "width": "112px"},
        {"key": "pay_method", "label": "实际付款方式", "sortable": False, "cls": "", "vsep": False, "width": "130px"},
        {"key": "amount", "label": "本次付款金额", "sortable": False, "cls": "num", "vsep": False, "width": "130px"},
        {"key": "op", "label": "操作", "sortable": False, "cls": "", "vsep": False, "width": "120px"},
    ]

    rows_html = "".join(_row_html(it, data["pay_methods"]) for it in items)

    confirm = (
        f'<button class="pri" name="confirm" value="1">确认付款（{len(items)} 条 · 合计 {esc(data["total_payable"])} 元）</button>'
        if check.enabled
        else f'<button class="pri" disabled title="{esc(check.reason)}">确认付款（禁用）</button>'
    )
    blocker = ""
    if not check.enabled:
        blocker = (
            f'<div class="notice err"><b>{esc(check.reason)}</b><br>{esc(check.how_to_fix)}</div>'
        )
    skipped = ""
    if data["skipped"]:
        lines = "".join(f"<li>{esc(nid)}：{esc(reason)}</li>" for nid, reason in data["skipped"])
        skipped = f'<details class="tip"><summary>已从本次付款中排除 {len(data["skipped"])} 条</summary><ul>{lines}</ul></details>'
    notice = f'<div class="notice {esc(message_kind)}">{esc(message)}</div>' if message else ""

    body = render_list_page(
        page_id=PAGE_ID,
        title="批量付款",
        tips=data["tips"],
        kpis=[],
        filters=[],
        columns=columns,
        rows_html=rows_html,
        empty_text="没有可付款的行（勾选的通知书可能已撤单 / 已被剔除）",
        sort_key=None,
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>批量付款 · 材料报表自动化工作台</title>
<style>{BASE_CSS}
.dt tr.blocked>td{{background:var(--dg-l)}}
.dt input.cell{{width:110px}}
form#{PAY_FORM_ID}{{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;margin:10px 0}}
form#f-pay label{{font-size:12px;color:var(--mut);display:flex;flex-direction:column;gap:3px}}
</style></head><body>
<div class="wrap">
<nav class="nav"><a href="/m03/notices">← 返回付款通知书</a> <a href="/m05">付款流水与欠款</a></nav>
{notice}{blocker}{skipped}
<form id="{PAY_FORM_ID}" method="post" action="{PAY_URL}">
<input type="hidden" name="request_id" value="{esc(data["request_id"])}">
{''.join(f'<input type="hidden" name="ids" value="{it["notice_id"]}">' for it in items)}
<label>付款日期<input type="date" name="pay_date"></label>
<label>备注（付款方式选「其他」时必填）<input name="remark"></label>
{confirm}
<button name="cancel" value="1">取消</button>
</form>
{body}
<p class="mut" style="font-size:12px">⚠️ 提交时**整批重算**：只要有一条不过，**整批不产生任何流水**（不落半批，§4.4.4）。</p>
</div>
</body></html>"""


__all__ = ["PAGE_ID", "PAY_URL", "TIPS", "SKIP_REVOKED", "SKIP_EXCLUDED", "default_pay_method", "build_pay_window", "render_pay_page"]
