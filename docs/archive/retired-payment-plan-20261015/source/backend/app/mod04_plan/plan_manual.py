"""付款计划的**手动行**（`MOD-04` · §4.3 ＋ 用户 2026-09-16 口述新增）。

## 为什么要有一条"手动行"

付款计划有两类来源：
| 来源 | 谁产生 | 导入时 |
|---|---|---|
| **自动行**（导入行） | Excel 导入（§4.3.3） | **清理并重写**（§9.5） |
| **手动行**（本模块） | 用户在列表里**手动补一行** | **不被触碰**（§9.5：导入只清理并重写自动行） |

## ⭐ 用户 2026-09-16 明确：**手动行一样要被审查**

审查（§4.3.4 的 6 种判定）是**按行实时派生**的（`domain.audit_rows`，不落库、不看来源）
⇒ 手动行**天然**与导入行同一条审查链路：同样参与 6 种判定、同样计入「审查结果」筛选两档、
同样计入 KPI 计数与表内合计。本模块**不做任何"跳过审查"的分支**。

## 与「付款通知书」的手动行的区别（别照抄）

| | 付款通知书（`MOD-03` §4.2.6） | 付款计划（本模块） |
|---|---|---|
| 删除 | ⛔ **不提供**（i8 行永不删；手动行可删） | ✅ **所有行都可删**（§4.3.6 逐行 + 批量） |
| 编辑 | 只对手动行 | **只对手动行**（导入行要改就重导） |
| 留痕 | 统计两金额留痕 | **不留痕**（§9.3：付款计划的改动不在留痕范围内） |

⚠️ 判定一律走纯函数；落库在 `repository`、路由在 `router`、页面在 `view` / 本模块的 `draft_row_html`。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.core.errors import MustReportError
from app.core.money import MoneyError, require_non_negative
from app.mod03_notice.page import esc
from app.mod04_plan.models import PlanRow
from app.mod05_flow.models import PAY_METHODS

_YM_RE = re.compile(r"^\d{4}-\d{2}$")

# 草稿行整页**共用一个表单**（`<form>` 不能是 `<tr>` 的子元素 ⇒ 控件用 `form` 属性关联）
DRAFT_FORM_ID = "f-row"
_FA = f' form="{DRAFT_FORM_ID}"'


def is_manual_row(row) -> bool:
    """该计划行是否**手动行**（`dict` / ORM 都可用）。"""
    if isinstance(row, dict):
        return bool(row.get("is_manual"))
    return bool(getattr(row, "is_manual", False))


def assert_manual_editable(row) -> None:
    """**编辑只对手动行开放** —— 导入行是"项目端报来的原始数据"，要改就重导（§4.3.3）。"""
    if not is_manual_row(row):
        raise MustReportError(
            "编辑只对**手动新增的计划行**开放 —— 导入回来的行属于项目端报来的原始数据（§4.3.3）；"
            "要改请**修正 Excel 后重新导入**（导入会按 §9.5 清该月自动行并重写）"
        )


@dataclass
class ManualPlanRow:
    """手动行的**校验结论 + 落库字段**。"""

    values: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def manual_row_payload(
    *,
    year_month: str = "",
    project_input: str = "",
    project_id: int | None = None,
    doc_no: str = "",
    flow_amount: object = None,
    planned_amount: object = None,
    pay_date: str = "",
    pay_method: str = "",
    remark: str = "",
) -> ManualPlanRow:
    """组装一条**手动新增付款计划行**的落库字段。

    校验（都显式报出，不静默取默认）：
    1. **年月必填**且形如 `YYYY-MM` —— 它是**归月依据**（§4.3.6 按月归档）；
    2. 两个金额 **≥ 0**（§8.4：手动新增一律 ≥ 0）；
    3. **付款方式**要么留空、要么是「现汇 / 承兑 / 供应链 / 其他」之一（§4.3.3 该列的取值）。

    ⚠️ **单据号允许为空**（§4.3.3）—— 空号会被审查判成「无单据号」，**只提示不拦截**。
    ⚠️ **项目允许为空**（与导入同款：项目列可能匹配不上）—— 留空的行在列表里标「未匹配」。
    """
    ym = str(year_month or "").strip()
    if not _YM_RE.match(ym):
        raise MustReportError(
            f"手动行的「年月」必须形如 `2026-09`（当前 {ym or '（空）'}）—— 它是**归月依据**（§4.3.6 按月归档）"
        )

    def money(value: object, label: str) -> Decimal:
        try:
            return require_non_negative(value if value not in (None, "") else 0, field=label)
        except MoneyError as exc:
            raise MustReportError(f"手动行的{label}不合法（{exc}）") from exc

    method = str(pay_method or "").strip()
    if method and method not in PAY_METHODS:
        allowed = " / ".join(PAY_METHODS)
        raise MustReportError(f"付款方式只能是「{allowed}」（或留空）—— 当前「{method}」（§4.3.3）")

    notes = ["手动行**不被导入清理**（§9.5：导入只重写自动行），且**一样参与 §4.3.4 的 6 种审查判定**"]
    if not str(doc_no or "").strip():
        notes.append("单据号为空 ⇒ 审查结果会是「无单据号」（只提示、不拦截）")

    return ManualPlanRow(
        values={
            "year_month": ym,
            "project_input": str(project_input or "").strip(),
            "project_id": int(project_id) if project_id not in (None, "") else None,
            "match_status": "matched" if project_id not in (None, "") else "unmatched",
            "match_candidates": 1 if project_id not in (None, "") else 0,
            "doc_no": str(doc_no or "").strip(),
            "flow_amount": money(flow_amount, "i8 流程金额"),
            "planned_amount": money(planned_amount, "本月预付款金额"),
            "pay_date": str(pay_date or "").strip(),
            "pay_method": method,
            "remark": str(remark or "").strip(),
            "forced_through": False,
            "forced_remark": "",
            "is_manual": True,
            "raw": {"来源": "手动新增"},
        },
        notes=notes,
    )


# ---------------------------------------------------------------- 表内草稿行


def _opt(value: str, label: str, current: str) -> str:
    sel = " selected" if str(value) == str(current) else ""
    return f'<option value="{esc(value)}"{sel}>{esc(label)}</option>'


def project_select(current: int | None, options: list[dict]) -> str:
    """项目下拉 —— 选项键 = **档案行 id**（写操作按 id 定位，§9.8 铁律 5）。

    ⚠️ 列表的「项目」筛选用的是**仓库名**归并键；这里是**落库用的 id**，两者不要混：
       筛选按仓库名、落库按 id，落库后由 `service.project_key()` 反查仓库名参与筛选。
    """
    cur = "" if current in (None, "") else str(current)
    items = [f'<option value=""{"" if cur else " selected"}>（未指定）</option>']
    for o in options or ():
        items.append(_opt(str(o.get("key")), str(o.get("label") or o.get("key")), cur))
    return f'<select name="project_id" class="cell"{_FA}>{"".join(items)}</select>'


def draft_row_html(
    *,
    plan_row: dict | None,
    project_options: list[dict],
    default_ym: str,
    error: str = "",
) -> str:
    """表内草稿行（`plan_row=None` ⇒ 新增；否则为**编辑**该手动行）—— 列序与 `view.COLUMNS` 一致。"""
    r = plan_row or {}
    is_edit = bool(r)
    hidden_id = f'<input type="hidden" name="row_id" value="{esc(r.get("id"))}"{_FA}>' if is_edit else ""

    def text(name: str, value, *, cls: str = "cell", itype: str = "text", extra: str = "") -> str:
        return f'<input type="{itype}" name="{name}" class="{cls}" value="{esc(value or "")}"{_FA}{extra}>'

    ym = r.get("year_month") or default_ym
    method_opts = "".join(_opt("", "（未填）", str(r.get("pay_method") or ""))) + "".join(
        _opt(m, m, str(r.get("pay_method") or "")) for m in PAY_METHODS
    )

    cells = [
        "＋",
        # ⚠️ 字段名用 `row_ym`（**不是** `year_month`）：同一个表单里 `hidden_filters` 已经把**筛选月**
        #    也放进了 body，两者同名时 `FormData` 只取**第一个**（= 筛选月）⇒ 用户填的「归月」会被静默忽略。
        text("row_ym", ym, extra=' placeholder="2026-09" required'),
        project_select(r.get("project_id"), project_options),
        text("doc_no", r.get("doc_no"), extra=' placeholder="可空"'),
        text("flow_amount", r.get("flow_amount") or "0.00", cls="cell num"),
        "—",                                   # 已付款金额（由命中的 i8 通知书派生）
        "—",                                   # 剩余付款金额（同上）
        text("planned_amount", r.get("planned_amount") or "0.00", cls="cell num"),
        text("pay_date", r.get("pay_date"), itype="date"),
        f'<select name="pay_method" class="cell"{_FA}>{method_opts}</select>',
        text("remark", r.get("remark")),
        '<span class="mut" title="保存后按 §4.3.4 出审查结果（手动行与导入行同一条链路）">保存后判定</span>',
        f'<button class="pri"{_FA} title="保存">保存</button> '
        f'<button{_FA} formaction="/m04/row/cancel" title="取消">取消</button>',
    ]
    row = '<tr class="draftrow" data-seg="draft">' + hidden_id + "".join(
        f"<td>{c}</td>" for c in cells
    ) + "</tr>"
    tip = f'<div class="notice err">{esc(error)}</div>' if error else ""
    return row + tip


__all__ = [
    "DRAFT_FORM_ID", "is_manual_row", "assert_manual_editable",
    "ManualPlanRow", "manual_row_payload", "project_select", "draft_row_html",
    "PlanRow",
]
