"""付款通知书列表的**行渲染** —— 「操作」列（`R18`）＋ 手动新增 / 编辑的**表内草稿行**（§4.2.6）。

## 「操作」列的口径（设计规则 `R18`）

只承载**"对这条记录在本系统里的处置"**，按**可用条件**出现，**不是每行堆满按钮**：

| 条件 | 出口 |
|---|---|
| **手动新增行** | 「手动」徽标 ＋ **编辑 / 删除** |
| **有生效付款流水**（`Σ payEff > 0`） | **撤销付款**（1 条就地展开 / 多条**跳 `MOD-05` 逐条撤**） |
| **有关联集采合同** | **查看关联**（纯只读） |
| 一个都不满足 | 显示「—」 |

⚠️ **i8 抓取行永不给编辑 / 删除** —— i8 是源数据，本系统只读（§9.3）；要改去 i8 改、再重新抓取。
⚠️ **不做逐行「付款」按钮**（付款一律"勾选 → 批量付款"）；**不把「不计入统计」做成行内开关**（剔除是勾选 + 批量动作）。

## 手动行的草稿行（§4.2.6）

原型是「**表内增行**」（不是弹窗）：点「＋ 手动新增通知书」⇒ 表尾出现草稿行，就地填、就地存。
本模块产出那一行的 `<tr>`；**列数与表头一致**由 `columns()` 决定（这里按同一顺序排）。
"""

from __future__ import annotations

from urllib.parse import urlencode

from app.mod03_notice.notice_actions import CATEGORY_CHOICES, category_name
from app.mod03_notice.page import esc
from app.mod05_flow.models import PAY_METHODS

# 一个条件都不满足时「操作」列的显示
ACTION_EMPTY = "—"

MANUAL_TAG = '<span class="tag wn" title="手动新增行（没有 i8 单据）">手动</span>'


def _form(action: str, fields: dict, label: str, *, cls: str = "", title: str = "") -> str:
    """一个**小表单按钮**（服务端渲染下的行内动作；PRG 回原查询）。"""
    hidden = "".join(
        f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in (fields or {}).items()
    )
    klass = f' class="{cls}"' if cls else ""
    tip = f' title="{esc(title)}"' if title else ""
    return f'<form class="inline" method="post" action="{esc(action)}">{hidden}<button{klass}{tip}>{esc(label)}</button></form>'


def _revoke_form(row) -> str:
    """就近撤销：**该行只有 1 条生效流水** ⇒ 就地展开撤销窗（原因**必填**，§4.4.5）。"""
    flow = row.effective_flows[0]
    return (
        '<details class="pop"><summary class="lnk">撤销付款</summary>'
        '<div class="popbody">'
        f'<div class="mut sm">流水 {esc(flow.get("flow_no"))} · '
        f'{esc(flow.get("amount"))} 元 · {esc(flow.get("pay_date"))}</div>'
        f'<form method="post" action="/m03/notices/revoke-flow">'
        f'<input type="hidden" name="flow_id" value="{esc(flow.get("id"))}">'
        '<input name="reason" placeholder="撤销原因（必填）" required>'
        '<button class="dg" type="submit">确认撤销</button>'
        "</form></div></details>"
    )


def action_cell(row) -> str:
    """「操作」列的单元格 HTML（`R18` 的唯一出口）。"""
    parts: list[str] = []

    if getattr(row, "is_manual", False):
        parts.append(MANUAL_TAG)
        parts.append(
            _form("/m03/notices/draft", {"edit": row.notice_id}, "编辑", title="原地变成草稿行（不新增行）")
        )
        parts.append(_form("/m03/notices/delete", {"id": row.notice_id}, "删除", cls="dg", title="只删这一行手动数据"))

    if getattr(row, "has_effective_flow", False):
        flows = row.effective_flows
        if len(flows) == 1:
            parts.append(_revoke_form(row))
        else:
            # 多条 ⇒ **不在这里挑**：跳到付款流水页并筛到这一张单，由用户逐条撤（R18）
            href = "/m05?" + urlencode({"notice_id": row.notice_id, "year_month": ""})
            parts.append(
                f'<a class="lnk" href="{esc(href)}" '
                f'title="该行有 {len(flows)} 条生效流水 —— 到「付款流水」页逐条撤销（不提供一键撤全部）">'
                f"撤销付款 →</a>"
            )

    if getattr(row, "has_link", False):
        parts.append(
            f'<a class="lnk" href="{esc("/m03/notices/trace?" + urlencode({"id": row.notice_id}))}" '
            'title="只读：单据 / 项目 / 供应商 / 关联 / 两金额 / 付款状态 + 该行流水子表（含已撤销）">查看关联</a>'
        )

    return " ".join(parts) if parts else ACTION_EMPTY


# ---------------------------------------------------------------- 表内草稿行（手动新增 / 编辑）


def _opt(value: str, label: str, current: str) -> str:
    sel = " selected" if str(value) == str(current) else ""
    return f'<option value="{esc(value)}"{sel}>{esc(label)}</option>'


# 草稿行的表单 id —— ⚠️ `<form>` 不能是 `<tr>` 的子元素（HTML 解析器会把它提出表格），
# 故草稿行的每个控件都用 `form="f-draft"` **属性关联**（form 元素本身由页面渲染在数据区之外）。
DRAFT_FORM_ID = "f-draft"
_FA = f' form="{DRAFT_FORM_ID}"'


def _project_select(current: int | None, options: list[dict]) -> str:
    """归属项目下拉（§4.2.6：全部已建档项目，**含归档、不含壳**）。"""
    cur = "" if current in (None, "") else str(current)
    items = [f'<option value=""{"" if cur else " selected"}>（未指定）</option>']
    for o in options or ():
        label = str(o.get("label") or o.get("key") or "")
        if o.get("archived"):
            label = f"{label}（已归档）"
        items.append(_opt(str(o.get("key")), label, cur))
    return f'<select name="ownership_id" class="cell"{_FA}>{"".join(items)}</select>'


def draft_row_html(
    *,
    columns: list[dict],
    notice: dict | None,
    project_options: list[dict],
    operator: str,
    error: str = "",
) -> str:
    """渲染**表内草稿行**（`notice=None` ⇒ 新增；否则为**编辑**该手动行）。

    ⚠️ 「统计结算金额」对手动行**恒 0 且不可改**（§4.2.6）⇒ 该格是**只读文本**，不是输入框。
    ⚠️ 「录入人 = 当前登录用户」⇒ 只读展示，**不由手填**。
    """
    n = notice or {}
    is_edit = bool(n)
    hidden_id = f'<input type="hidden" name="id" value="{esc(n.get("id"))}"{_FA}>' if is_edit else ""
    err = f'<div class="mut sm" style="color:var(--dg-d)">{esc(error)}</div>' if error else ""

    def text(name: str, value, *, cls: str = "cell", itype: str = "text", extra: str = "") -> str:
        return (
            f'<input type="{itype}" name="{name}" class="{cls}" value="{esc(value or "")}"{_FA}{extra}>'
        )

    cells: dict[str, str] = {
        "pick": "＋",
        "doc_date": text("doc_date", n.get("doc_date"), itype="date", extra=" required"),
        "bill_no": text("bill_no", n.get("bill_no"), extra=' placeholder="可空"'),
        "project_display": _project_select(n.get("ownership_id"), project_options),
        "category_label": (
            f'<select name="category" class="cell"{_FA}>'
            + "".join(_opt(c, category_name(c), str(n.get("category") or "")) for c in CATEGORY_CHOICES)
            + "</select>"
        ),
        "bill_name": text("bill_name", n.get("bill_name")),
        "biz_type": text("biz_type", n.get("biz_type")),
        "payee": text("payee", n.get("payee")),
        "jc_supplier": "—",
        "input_by": f'<span class="mut" title="录入人 = 当前登录用户（§4.2.6），不由手填">{esc(operator)}</span>',
        "amount_approved_text": text(
            "amount_approved", n.get("amount_approved_text") or "0.00", cls="cell num", extra=" required"
        ),
        "pay_amount_text": "—",
        "amount_paid_text": "0.00",
        "stat_settle_text": (
            '<span class="mut" title="手动行的统计结算金额恒为 0 且不可修改（§4.2.6）">0.00 恒为 0</span>'
        ),
        "stat_paid_text": text(
            "stat_paid", n.get("stat_paid_text") or "0.00", cls="cell num",
            extra=' title="要入账就填这里（它进逐月欠款台账当月的「付款」列）"',
        ),
        "approve_status": f'<span class="mut">{esc(n.get("approve_status") or "手工录入")}</span>',
        "pay_status": "未付清",
        "actions": (
            f'<button class="pri"{_FA} title="保存">保存</button> '
            f'<button{_FA} formaction="/m03/notices/draft-cancel" title="取消">取消</button>'
        ),
    }

    tds = []
    for col in columns:
        klass = ' class="%s"' % col["cls"] if col.get("cls") else ""
        tds.append(f"<td{klass}>{cells.get(col.get('key'), '')}</td>")
    return f'<tr class="draftrow" data-seg="draft">{hidden_id}{"".join(tds)}</tr>{err}'


# ---------------------------------------------------------------- 统计两金额的行内手改（§4.5.3）

STAT_FORM_ID = "f-stat"

# 两个旁路字段 → 它们在列表里的显示值键
STAT_CELL_KEYS: dict[str, str] = {
    "stat_settle": "stat_settle_text",
    "stat_paid": "stat_paid_text",
}


def stat_cell(row, field: str, text: str) -> str:
    """统计金额（旁路字段）的**行内手改格**（§4.5.3）—— R8 的三态在这里落地：

    - **可改** = `.cell` 输入框；
    - **已手改** = 再加 `.ed` 黄底（判据 = **留痕**，不是另开的开关，§4.2.7）；
    - **只读** = 不可改的字段（本函数只用于两个旁路字段）。

    ⚠️ **上限 = 审批金额**：超额由 `domain.adjust_stat` **拦截并保留原值**（这里只把上限写进 `title` 提示）。
    ⚠️ 整页共用一个表单 `f-stat`，靠 `target=「行id:字段」` 指定**改的是哪一格** —— 避免每行造一个表单。
    """
    edited = field in (getattr(row, "edited_fields", ()) or ())
    cls = "cell num ed" if edited else "cell num"
    tip = f"上限 = 审批金额 {row.amount_approved}（按发票走，只能少付、不能多付）—— 超额会拦截并保留原值"
    return (
        f'<input name="v_{row.notice_id}_{field}" value="{esc(text)}" class="{cls}" '
        f'form="{STAT_FORM_ID}" title="{esc(tip)}">'
        f'<button form="{STAT_FORM_ID}" name="target" value="{row.notice_id}:{field}" '
        f'title="保存这一格（写留痕 + 欠款实时重算）">存</button>'
    )


__all__ = [
    "ACTION_EMPTY", "MANUAL_TAG", "DRAFT_FORM_ID", "STAT_FORM_ID", "STAT_CELL_KEYS",
    "action_cell", "draft_row_html", "stat_cell", "PAY_METHODS",
]
