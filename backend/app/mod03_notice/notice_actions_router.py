"""`MOD-03` **行级动作路由**（PRG）：改分类 · 剔除 / 恢复 · 手动新增 / 编辑 / 删除 · 统计手改 · 按计划勾选。

拆出来的理由：`notice_router` 一个文件装三件事会越过「单文件硬上限 600 行」（工程纪律）。
本文件与 `notice_router`（页面 / 列表 API）、`notice_pay_router`（批量付款 / 撤销 / 查看关联）**共用** `notice_http` 的公共件。

⚠️ **判定一律调纯函数出口**（`notice_actions` / `domain`），本文件只做取数、落库与 303 回跳。
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod03_notice import repository as repo
from app.mod03_notice.models import EXCLUDE_BY_MANUAL, EXCLUDE_NONE
from app.mod03_notice.notice_actions import (
    assert_manual_editable,
    change_category,
    manual_exclude,
    manual_row_payload,
    restore_excluded,
)
from app.mod03_notice.notice_http import DBSession, QueryState, State, back

actions_router = APIRouter(tags=["mod03-actions"])


# --------------------------------------------------------------- 能力 2 / 3 · 改分类 · 剔除 / 恢复


@actions_router.post("/m03/notices/category")
def act_category(
    category: str = Form(...),
    ids: list[int] = Form(default=[]),
    st: QueryState = State,
    session: Session = DBSession,
) -> RedirectResponse:
    """**批量改分类**（§4.2.4）—— 只能改三类；**不留痕**、**重抓不覆盖**。"""
    try:
        rows = repo.notices_as_dicts(session, ids=ids)
        change = change_category(rows, ids, category)
        repo.apply_category(session, change.changed, change.category)
        return back(st, change.message)
    except MustReportError as exc:
        return back(st, exc.message, kind="err")


@actions_router.post("/m03/notices/exclude")
def act_exclude(
    ids: list[int] = Form(default=[]), st: QueryState = State, session: Session = DBSession
) -> RedirectResponse:
    """**人工批量剔除**（§4.2.2）—— 标记来源 = `manual`（只有这一类能被「恢复剔除」放开）。"""
    try:
        report = manual_exclude(repo.notices_as_dicts(session, ids=ids), ids)
        repo.set_excluded(session, report.marked, excluded=True, source=EXCLUDE_BY_MANUAL)
        return back(st, report.message, kind="wn")
    except MustReportError as exc:
        return back(st, exc.message, kind="err")


@actions_router.post("/m03/notices/restore")
def act_restore(
    ids: list[int] = Form(default=[]), st: QueryState = State, session: Session = DBSession
) -> RedirectResponse:
    """**恢复剔除**（§4.2.2）—— 必须先勾选；**只恢复人工剔除的行**，规则命中的一律不恢复。"""
    try:
        report = restore_excluded(repo.notices_as_dicts(session, ids=ids), ids)
        repo.set_excluded(session, report.restored, excluded=False, source=EXCLUDE_NONE)
        return back(st, report.message, kind="wn")
    except MustReportError as exc:
        return back(st, exc.message, kind="err")


# --------------------------------------------------------------- 能力 4 · 手动新增 / 编辑 / 删除


@actions_router.post("/m03/notices/draft")
def act_draft(
    new: str = Form(""),
    edit: str = Form(""),
    st: QueryState = State,
) -> RedirectResponse:
    """开草稿行（**增行模式**，不弹窗，§4.2.6）：`new=1` 新增 / `edit=<id>` 原地编辑。"""
    token = str(edit or "").strip() or ("new" if str(new or "").strip() else "")
    if not token:
        return back(st, "没有指定要新增还是编辑", kind="err")
    return back(st, "已就绪：填完点「保存」（手动行的统计结算金额恒为 0）", kind="wn", draft=token)


@actions_router.post("/m03/notices/draft-cancel")
def act_draft_cancel(st: QueryState = State) -> RedirectResponse:
    """取消草稿行 —— **不留任何数据**（每步可中断，§9.5）。"""
    return back(st, "已取消草稿行（未写入任何数据）", kind="wn")


@actions_router.post("/m03/notices/save")
def act_save(
    doc_date: str = Form(""),
    bill_no: str = Form(""),
    bill_name: str = Form(""),
    biz_type: str = Form(""),
    payee: str = Form(""),
    category: str = Form(""),
    amount_approved: str = Form(""),
    stat_paid: str = Form(""),
    ownership_id: str = Form(""),
    id: str = Form(""),
    st: QueryState = State,
    session: Session = DBSession,
) -> RedirectResponse:
    """保存手动行（**新增与编辑共用同一套**，§4.2.6）—— 判定走 `notice_actions.manual_row_payload`。"""
    try:
        # ⚠️ 2026-09-19（`§19` 批 4 · S2a）：校验 / 落库 / 文案一律走**唯一出口**
        #    `notice_actions.apply_manual_save`（与 JSON API `/api/m03/actions/manual-save` **共用**）
        #    —— ⛔ 别在这里重写校验或另写文案（一份内容只许一个主人）。
        from app.mod03_notice.notice_actions import apply_manual_save

        _, msg = apply_manual_save(
            session, row_id=id, entered_by=current_operator(),
            fields=dict(doc_date=doc_date, bill_no=bill_no, bill_name=bill_name,
                        biz_type=biz_type, payee=payee, category=category,
                        amount_approved=amount_approved, stat_paid=stat_paid,
                        ownership_id=ownership_id),
        )
        return back(st, msg)
    except MustReportError as exc:
        # 校验不过 ⇒ **保留草稿行**让用户改（不清空已填内容，R14③）
        keep = str(id or "").strip() or "new"
        return back(st, exc.message, kind="err", draft=keep)


@actions_router.post("/m03/notices/delete")
def act_delete(
    id: int = Form(...), st: QueryState = State, session: Session = DBSession
) -> RedirectResponse:
    """删除一条**手动行**（§4.2.6：只对手动行开放）—— i8 抓取行永不可删（§4.2.7）。"""
    try:
        row = repo.get_notice(session, int(id))
        if row is None:
            raise MustReportError(f"要删除的行 {id} 不存在")
        assert_manual_editable(row)
        label = row.bill_no or row.ph_id
        repo.delete_notice(session, row)
        return back(st, f"已删除手动行「{label}」（只删这一行；欠款随取数实时重算）", kind="wn")
    except MustReportError as exc:
        return back(st, exc.message, kind="err")


# --------------------------------------------------------------- 能力 11 · 统计金额手改（§4.5.3）


@actions_router.post("/m03/notices/stat")
async def act_stat(
    request: Request,
    st: QueryState = State,
    session: Session = DBSession,
) -> RedirectResponse:
    """**统计金额手改**（§4.5.3）—— 上限 = 审批金额；超额**拦截并保留原值**；**留痕**；**欠款实时重算**。

    ⚠️ 整页共用一个表单：`target=「行id:字段」` 指明改哪一格，值在 `v_<id>_<field>` 里（见 `notice_row.stat_cell`）。
    """
    form = await request.form()
    target = str(form.get("target") or "")
    notice_id, _, field = target.partition(":")
    if not notice_id.isdigit() or not field:
        return back(st, f"保存目标非法：{target!r}", kind="err")
    value = form.get(f"v_{notice_id}_{field}")

    try:
        # ⚠️ 2026-09-19（`§19` 批 4 · S1）：判定 / 落库 / 留痕 / 欠款重算 / 回执文案一律走**唯一出口**
        #    `notice_actions.apply_stat_change`（与 JSON API `/api/m03/actions/stat` **共用**）——
        #    ⛔ 别在这里重写判定或另写一句文案（一份内容只许一个主人）。
        from app.mod03_notice.notice_actions import apply_stat_change

        trace, message = apply_stat_change(
            session, int(notice_id), field=field, value=value, changed_by=current_operator()
        )
    except MustReportError as exc:
        return back(st, exc.message, kind="err")
    # 值没变 ⇒ 提示走 `wn`（原样照搬原来的那句「什么都没做」）；改了 ⇒ 正常回执
    return back(st, message, kind="ok" if trace is not None else "wn")


# --------------------------------------------------------------- 能力 6 · 按本月计划勾选（§4.3.5）


@actions_router.post("/m03/notices/pick-plan")
def act_pick_plan(st: QueryState = State) -> RedirectResponse:
    """**「按本月计划勾选」**（§4.3.5）—— 一键勾选「**北京时间当月**」付款计划命中的通知书。

    三条口径，一条都不能少：
    1. **月份不可自选** —— 一律按**北京时间当月**（按钮上直接带出当月）；
    2. **先把视图参数放宽到「全部月份 + 未付清」**，使命中的通知书（含**跨月单据**）全部落入当前筛选结果，
       再一次性勾选 —— 这样"只勾当前筛选结果内的行"依然成立；
    3. **「项目」筛选一律不动**（它是用户表达的业务范围）—— 被项目筛选挡掉的行跳过，并在回报里**报数**。

    ⚠️ **可点窗口 = 付款计划的生效时间**（每月 10 号 → 月底，§4.3.2）：窗口外**按钮先禁用**（R14①）。
    """
    from datetime import date
    from urllib.parse import urlencode

    from fastapi.responses import RedirectResponse as _RR

    from app.core.period import default_period as _dp
    from app.mod03_notice.notice_http import LIST_URL
    from app.mod04_plan.domain import in_effective_window, window_label

    today = date.today()
    if not in_effective_window(today.day):
        return back(
            st,
            f"「按本月计划勾选」只在付款计划的生效窗口内可点（{window_label(today.day)}）—— 本次未执行",
            kind="err",
        )

    plan_ym = _dp("plan", today)          # 月份不可自选：一律北京时间当月
    q = {
        "period": "",                     # 放宽：全部月份（跨月单据也要能勾上）
        "project": list(st.project or ()),# 项目筛选**不动**
        "category": "",                   # 放宽：全部分类
        "approve_status": "",             # 放宽：全部审批状态
        "pay_status": "unpaid",           # 放宽到「未付清」
        "sort": "", "dir": 0,
        "plan": plan_ym,
        "msg": f"已按 {plan_ym} 的付款计划勾选（视图参数已放宽到「全部月份 + 未付清」）",
        "msgkind": "wn",
    }
    return _RR(f"{LIST_URL}?{urlencode(q, doseq=True)}", status_code=303)


__all__ = ["actions_router"]
