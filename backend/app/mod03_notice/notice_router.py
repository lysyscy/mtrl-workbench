"""`MOD-03` **列表页与列表 API**（服务端渲染 ＋ PRG 的"读"侧）。

与另两个 router 的分工（**同一职责一处**，也守住单文件行数上限）：

| 文件 | 管什么 |
|---|---|
| `notice_router.py`（本文件） | `/m03/notices` 页面 · `/api/m03/notice-list` 列表 API |
| `notice_actions_router.py` | 行级动作：改分类 · 剔除 / 恢复 · 手动新增 / 编辑 / 删除 · 统计手改 · 按计划勾选 |
| `notice_pay_router.py` | 批量付款窗口 · 撤销付款 · 查看关联 |
| `router.py` | 「勾选 → 输出」链路（批量打印 / 仅导出 PDF）与打印机设置 |

三个 router 共用的东西（会话 / 当前查询 / PRG 回跳 / 筛选解析）在 `notice_http.py`。

依据：《说明书》§4.2（列表与筛选）· §4.2.5（四金额与派生列）· §4.3.5（按计划勾选）·
      §9.2（付款侧默认年月 = 当月）· 设计规则 `R10①`（空态行跨列数由表头派生）。
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.mod03_notice import repository as repo
from app.mod03_notice.notice_actions import is_manual_row
from app.mod03_notice.notice_actions_router import actions_router
from app.mod03_notice.notice_http import (  # noqa: F401  ← get_session 再导出：调用方 / 自检注入用
    DBSession,
    PAGE_ONLY_KEYS,
    get_session,
    notice_filters,
)
from app.mod03_notice.notice_page import build_page_data, render_notice_page
from app.mod03_notice.notice_pay_router import pay_router
from app.mod03_notice.page import SORT_NONE

page_router = APIRouter(tags=["mod03-pages"])
page_router.include_router(actions_router)
page_router.include_router(pay_router)


# --------------------------------------------------------------- 草稿行（§4.2.6 增行模式）


def _draft_from_notice(row) -> dict:
    """编辑某手动行 ⇒ 草稿行的初值（各列显示值）。"""
    from app.core.money import to_money

    return {
        "id": row.id,
        "doc_date": str(row.doc_date or ""),
        "bill_no": str(row.bill_no or ""),
        "project_name": str(row.project_name or ""),
        "category": str(row.category or ""),
        "bill_name": str((row.fields or {}).get("BillName") or ""),
        "biz_type": str(row.biz_type or ""),
        "payee": str(row.payee or ""),
        "amount_approved_text": f"{to_money(row.amount_approved):.2f}",
        "stat_paid_text": f"{to_money(row.stat_paid):.2f}",
        "ownership_id": row.ownership_id,
        "approve_status": str(row.approve_status or ""),
    }


def _resolve_draft(token: str, session: Session) -> tuple[dict | None, str]:
    """把 `?draft=` 解析成草稿行数据（`None` = 不显示草稿行）。"""
    text = str(token or "").strip()
    if not text:
        return None, ""
    # ⚠️ 只认字面量 `new` —— **不要把 "1" 也当"新增"**：那会让"编辑第 1 行"变成"新增一行"。
    #    （增行按钮走 `new=1` → `act_draft` 已把它归一成 `new`，所以这里不需要数字别名。）
    if text == "new":
        return {}, ""
    if not text.isdigit():
        return None, f"草稿参数非法：{text}"
    row = repo.get_notice(session, int(text))
    if row is None:
        return None, f"要编辑的行 {text} 不存在"
    if not is_manual_row(row):
        return None, "编辑只对**手动新增行**开放 —— i8 抓取行是源数据（§4.2.6 / §9.3）"
    return _draft_from_notice(row), ""


def _plan_docs(session: Session, plan_ym: str) -> list[str]:
    """某月付款计划里出现过的**单据号**（§4.3.5 的勾选依据）。

    ⚠️ 单据号**允许为空**（§4.3.3）⇒ 空号不参与勾选（它认不出对应哪张通知书）。
    """
    if not str(plan_ym or "").strip():
        return []
    from app.mod04_plan.repository import list_rows

    return [
        str(r.doc_no or "").strip()
        for r in list_rows(session)
        if str(r.year_month or "") == str(plan_ym) and str(r.doc_no or "").strip()
    ]


# --------------------------------------------------------------- 页面 / 列表 API


@page_router.get("/m03/notices", response_class=HTMLResponse)
def page_notices(
    period: str | None = Query(None),
    project: list[str] = Query(default=[]),
    category: str = Query(""),
    approve_status: str = Query(""),
    pay_status: str = Query(""),
    sort: str = Query(""),
    dir: int = Query(SORT_NONE),
    draft: str = Query("", description="new = 新增草稿行；<id> = 编辑该手动行"),
    plan: str = Query("", description="非空 = 按该（当月）付款计划**预勾选**命中的行，§4.3.5"),
    msg: str = Query(""),
    msgkind: str = Query("ok"),
    session: Session = DBSession,
) -> HTMLResponse:
    """付款通知书列表页（§4.2）—— 五段骨架走 `notice_page.render_notice_page`，**本页不手写骨架**。"""
    filters = notice_filters(period, project, category, approve_status, pay_status)
    draft_data, draft_error = _resolve_draft(draft, session)
    data = build_page_data(
        session, filters=filters, sort_col=sort, sort_dir=dir,
        draft=draft_data, draft_error=draft_error,
        plan_ym=plan, plan_docs=_plan_docs(session, plan),
    )
    return HTMLResponse(render_notice_page(data, message=msg, message_kind=msgkind))


@page_router.get("/api/m03/notice-list")
def get_notice_list(
    period: str | None = Query(None),
    project: list[str] = Query(default=[]),
    category: str = Query(""),
    approve_status: str = Query(""),
    pay_status: str = Query(""),
    sort: str = Query(""),
    dir: int = Query(SORT_NONE),
    session: Session = DBSession,
) -> dict:
    """列表页的数据源（含筛选与计数）。

    ⚠️ 与 `GET /api/m03/notices` 的区别：那个是**静态页 `m03` 的「勾选打印对象」**（按 `bill_type` 过滤）；
       本端点服务的是**列表页** —— 四金额 / 分类 / 剔除 / 付款状态 / 计数都在这里。
    """
    filters = notice_filters(period, project, category, approve_status, pay_status)
    data = build_page_data(session, filters=filters, sort_col=sort, sort_dir=dir)
    c = data["counters"]
    return {
        "filters": {
            "period": filters.period,
            "project_ids": list(filters.project_ids),
            "category": filters.category,
            "approve_status": filters.approve_status,
            "pay_status": filters.pay_status,
        },
        "counters": {
            "shown": c.shown, "effective": c.effective, "excluded": c.excluded,
            "revoked": c.revoked, "excluded_by": c.excluded_by, "text": c.text(),
        },
        # ⚠️ **页面专用**的列（「操作」列是按钮 / 表单 HTML）**不进 API** —— 本端点只吐纯数据
        "items": [
            {k: v for k, v in rec.items() if k != "_row" and k not in PAGE_ONLY_KEYS}
            for rec in data["rows"]
        ],
    }


__all__ = ["page_router"]
