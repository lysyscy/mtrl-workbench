"""`MOD-03` **批量付款 / 撤销付款 / 查看关联**路由。

拆出来的理由同 `notice_actions_router`（单文件硬上限）。三件都属"付款动作"，放一处。

依据：《说明书》§4.4.4（批量付款）· §4.4.5（撤销：按流水号 ＋ **必填原因**）·
      §4.2.7（撤单行不进付款链）· 交互规则 `R18`（操作列的就近入口 · 查看关联**纯只读**）。
"""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.core.money import to_money
from app.mod03_notice import repository as repo
from app.mod03_notice.domain import PayDraft, PayRow, confirm_batch
from app.mod03_notice.list_view import build_rows
from app.mod03_notice.notice_http import (
    DBSession,
    LIST_URL,
    PAY_URL,
    QueryState,
    State,
    back_pay,
    parse_amount,
    plan_methods_for_pay,
)
from app.mod03_notice.notice_page import render_trace_page
from app.mod03_notice.notice_pay import build_pay_window, default_pay_method, render_pay_page
from app.mod05_flow import repository as flow_repo

pay_router = APIRouter(tags=["mod03-pay"])


# --------------------------------------------------------------- 能力 7 / 8 · 批量付款（§4.4.4）


@pay_router.get(PAY_URL, response_class=HTMLResponse)
def page_pay(
    request: Request,
    ids: list[int] = Query(default=[]),
    msg: str = Query(""),
    msgkind: str = Query("ok"),
    session: Session = DBSession,
) -> HTMLResponse:
    """**批量付款窗口**（§4.4.4）—— 勾选若干条 → 一次动作。

    ⚠️ `m_<id>` / `a_<id>` 这类 query 参数 = **移出某行后被带回来的已填值**（R14③ 调整不丢已填内容）。
    """
    overrides = {
        k: v for k, v in request.query_params.multi_items() if k.startswith(("m_", "a_"))
    }
    data = build_pay_window(session, ids, overrides=overrides)
    return HTMLResponse(render_pay_page(data, message=msg, message_kind=msgkind))


@pay_router.post(PAY_URL)
async def act_pay(request: Request, session: Session = DBSession) -> RedirectResponse:
    """提交批量付款（§4.4.4）—— **整批重算**，任一不过 ⇒ **整批不产生任何流水**（不落半批）。"""
    form = await request.form()
    ids = [int(v) for v in form.getlist("ids") if str(v).strip().isdigit()]

    if form.get("cancel"):
        return RedirectResponse(LIST_URL, status_code=303)

    # ① 「移出本次付款」⇒ 回窗口，并把**其它行已填的付款方式 / 金额一并带回**（R14③）
    move = str(form.get("move") or "").strip()
    if move.isdigit():
        q: dict = {"ids": [i for i in ids if i != int(move)]}
        for key, value in form.multi_items():
            if key.startswith(("m_", "a_")) and not key.endswith(f"_{move}"):
                q[key] = value
        return RedirectResponse(f"{PAY_URL}?{urlencode(q, doseq=True)}", status_code=303)

    if not form.get("confirm"):
        return back_pay(ids, "没有点「确认付款」—— 什么都没做", kind="wn")

    try:
        rows = build_rows(session)
        by_id = {r.notice_id: r for r in rows}

        # ⚠️ 兜底：以**库里的最新状态**重算（防"勾上之后才被改成不可付"）；撤单 / 剔除行一律排除
        targets = [
            by_id[i]
            for i in ids
            if i in by_id and not by_id[i].i8_revoked and not by_id[i].excluded
        ]
        if not targets:
            raise MustReportError("没有可付款的行（勾选的单据可能已撤单 / 已被剔除）")

        pay_rows = [
            PayRow(notice_id=r.notice_id, approve_status=r.approve_status, payable=r.pay_amount)
            for r in targets
        ]
        plan_methods = plan_methods_for_pay(session)
        drafts = {
            r.notice_id: PayDraft(
                # ⚠️ 表单没给 ⇒ 用**与窗口渲染同一个出口**的默认值（§4.4.2）
                pay_method=str(
                    form.get(f"m_{r.notice_id}") or default_pay_method(r.bill_no, plan_methods)
                ),
                amount=parse_amount(form.get(f"a_{r.notice_id}")),
            )
            for r in targets
        }
        result = confirm_batch(
            pay_rows, drafts,
            pay_date=str(form.get("pay_date") or ""),
            remark=str(form.get("remark") or ""),
        )
        if result.errors:
            # **整批不产生任何流水**（不落半批）
            return back_pay(ids, "整批未产生任何流水 —— " + "；".join(result.errors[:6]), kind="err")

        rid = str(form.get("request_id") or "").strip()
        if flow_repo.has_request_id(session, rid):
            raise MustReportError(f"该提交（request_id={rid}）已经登记过流水 —— 已拒绝重复提交（§4.4.4）")

        total = Decimal("0")
        for item in result.flows:
            row = by_id[int(item["notice_id"])]
            flow_repo.create_flow(
                session,
                notice_id=row.notice_id,
                project_id=row.ownership_id,
                amount=item["amount"],
                pay_date=item["pay_date"],
                pay_method=item["pay_method"],
                request_id=rid,
            )
            total += to_money(item["amount"])
        return back_pay(
            [],
            f"已登记 {len(result.flows)} 条付款流水，合计 {total:.2f} 元"
            "（一次付款一条独立流水）；相关通知书的已付金额与付款状态已随之更新",
        )
    except MustReportError as exc:
        return back_pay(ids, exc.message, kind="err")


# --------------------------------------------------------------- 能力 9 · 撤销付款（就近入口）


@pay_router.post("/m03/notices/revoke-flow")
def act_revoke_flow(
    flow_id: int = Form(...),
    reason: str = Form(""),
    st: QueryState = State,
    session: Session = DBSession,
) -> RedirectResponse:
    """就近撤销**一条**流水（§4.4.5：**按流水号** · **原因必填**）—— 只回退流水汇总，不动源数据。"""
    try:
        flow = flow_repo.get_flow(session, int(flow_id))
        if flow is None:
            raise MustReportError(f"流水 {flow_id} 不存在")
        no = flow.flow_no
        flow_repo.revoke(session, flow, reason=reason, changed_by=current_operator())
        return back_pay(
            [],
            f"已撤销流水 {no}（原因：{reason.strip()}）；该通知书已付金额已回退、付款状态按 §4.4.2 重新判定",
            kind="wn",
        )
    except MustReportError as exc:
        return back_pay([], exc.message, kind="err")


# --------------------------------------------------------------- 能力 9 · 查看关联（纯只读）


@pay_router.get("/m03/notices/trace", response_class=HTMLResponse)
def page_trace(id: int = Query(...), session: Session = DBSession) -> HTMLResponse:
    """**查看关联**（`R18`）：纯只读 —— 单据 / 项目 / 供应商 / 关联 / 两金额 / 付款状态 ＋ 流水子表（含已撤销）。

    ⚠️ **零副作用**：不开任何写路径、不动勾选、不进任何留痕。
    """
    row = repo.get_notice(session, int(id))
    if row is None:
        raise MustReportError(f"通知书 {id} 不存在")
    flows = [
        {
            "flow_no": f.flow_no, "amount": f"{to_money(f.amount):.2f}", "pay_date": f.pay_date,
            "pay_method": f.pay_method, "status": f.status,
            "status_label": "生效" if f.status == "effective" else "已撤销",
            "revoke_reason": f.revoke_reason,
            "revoked_at": f.revoked_at.strftime("%Y-%m-%d %H:%M") if f.revoked_at else "",
        }
        for f in flow_repo.list_flows_of_notice(session, int(id))
    ]
    data = {
        "id": row.id,
        "bill_no": row.bill_no or f"#{row.id}",
        "ph_id": row.ph_id,
        "doc_date": row.doc_date,
        "bill_name": (row.fields or {}).get("BillName") or "",
        "project_name": row.project_name,
        "category": row.category,
        "approve_status": row.approve_status,
        "approve_amount": f"{to_money(row.amount_approved):.2f}",
        "stat_settle": f"{to_money(row.stat_settle):.2f}",
        "stat_paid": f"{to_money(row.stat_paid):.2f}",
        "is_manual": bool(row.is_manual),
        "i8_revoked": bool(row.i8_revoked),
        "flows": flows,
    }
    return HTMLResponse(render_trace_page(data))


__all__ = ["pay_router"]
