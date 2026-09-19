"""`MOD-03` **JSON 动作 API** —— 供前端壳（`app/web/`）用 `fetch` 调用。

⚠️ 与 `notice_actions_router`（表单向 · PRG 303 回跳）**共用同一批纯函数出口**
   （`notice_actions.change_category` / `manual_exclude` / `restore_excluded`，
   落库走同一个 `repository`）—— 本文件只做「取数 → 判定 → 落库 → 回 JSON」，
   ⛔ **不重复、不另写任何判定**（一份内容只许一个主人）。

⚠️ 回执形状：HTTP **恒 200**，用 `ok` 标志区分成败 —— 前端壳是"就地改、即时反馈"，
   靠 HTTP 状态码分流会逼它写第二套错误分支（与本项目「内部工具、简单优先」不符）。
   失败时 `message` 一定是**可直接给人看**的一句中文（判定函数已经这么产出了）。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.mod03_notice import repository as repo
from app.mod03_notice.models import EXCLUDE_BY_MANUAL, EXCLUDE_NONE
from app.mod03_notice.notice_actions import (
    change_category,
    manual_exclude,
    restore_excluded,
)
from app.mod03_notice.notice_http import DBSession

api_router = APIRouter(tags=["mod03-json"])


class IdsIn(BaseModel):
    """勾选行 = 一组 `notice.id`；**单行动作也走这里**（只传一个）。"""

    ids: list[int] = Field(default_factory=list)


class CategoryIn(IdsIn):
    category: str = ""


@api_router.post("/api/m03/actions/category")
def api_category(req: CategoryIn, session: Session = DBSession) -> dict:
    """**批量改分类**（§4.2.4）—— 单行「就地改分类」= 只传一个 id，走同一条路。"""
    try:
        rows = repo.notices_as_dicts(session, ids=req.ids)
        change = change_category(rows, req.ids, req.category)
        repo.apply_category(session, change.changed, change.category)
        return {
            "ok": True,
            "changed": list(change.changed),
            "category": change.category,
            "message": change.message,
        }
    except MustReportError as exc:
        return {"ok": False, "changed": [], "message": exc.message}


@api_router.post("/api/m03/actions/exclude")
def api_exclude(req: IdsIn, session: Session = DBSession) -> dict:
    """**人工批量剔除**（§4.2.2）—— 标记来源 = `manual`（只有这一类能被「恢复剔除」放开）。"""
    try:
        report = manual_exclude(repo.notices_as_dicts(session, ids=req.ids), req.ids)
        repo.set_excluded(session, report.marked, excluded=True, source=EXCLUDE_BY_MANUAL)
        return {"ok": True, "marked": list(report.marked), "message": report.message}
    except MustReportError as exc:
        return {"ok": False, "marked": [], "message": exc.message}


@api_router.post("/api/m03/actions/restore")
def api_restore(req: IdsIn, session: Session = DBSession) -> dict:
    """**恢复剔除**（§4.2.2）—— 必须先勾选；**只恢复人工剔除的行**，规则命中的一律不恢复。"""
    try:
        report = restore_excluded(repo.notices_as_dicts(session, ids=req.ids), req.ids)
        repo.set_excluded(session, report.restored, excluded=False, source=EXCLUDE_NONE)
        return {"ok": True, "restored": list(report.restored), "message": report.message}
    except MustReportError as exc:
        return {"ok": False, "restored": [], "message": exc.message}


class StatIn(BaseModel):
    """**统计金额手改**的入参（§4.5.3）。

    ⚠️ 字段名用**后端的旁路字段名**（`stat_settle` / `stat_paid`），不用壳里的短名（`ss` / `sp`）
       —— 名字映射由壳的适配层做（照既有的 `CAT_API` 做法），⛔ 后端不为某个前端改名。
    """

    notice_id: int
    field: str
    value: str


@api_router.post("/api/m03/actions/stat")
def api_stat(req: StatIn, session: Session = DBSession) -> dict:
    """**统计金额手改**（§4.5.3）—— 上限 = 审批金额；超额**拦截并保留原值**；**留痕**；欠款**实时重算**。

    ⚠️ 与 PRG `POST /m03/notices/stat` **共用** `notice_actions.apply_stat_change` ——
       本文件只做「取数 → 判定 → 落库 → 回 JSON」，⛔ **不重复、不另写任何判定或文案**。
    ⚠️ 值没变时 `ok=True, changed=False`（**什么都没做**，§4.2.7）—— 前端也照常提示那句中文。
    """
    from app.core.identity import current_operator
    from app.mod03_notice.notice_actions import apply_stat_change

    try:
        trace, message = apply_stat_change(
            session, req.notice_id, field=req.field, value=req.value,
            changed_by=current_operator(),
        )
    except MustReportError as exc:
        return {"ok": False, "changed": False, "message": exc.message}

    if trace is None:
        return {"ok": True, "changed": False, "message": message}

    return {
        "ok": True,
        "changed": True,
        "notice_id": req.notice_id,
        "field": req.field,
        "before": str(trace.before),
        "after": str(trace.after),
        "label": trace.label,
        "message": message,
    }


class ManualSaveIn(BaseModel):
    """**手动行新增 / 编辑**的入参（§4.2.6）—— 字段名与表单向**同一套**（⛔ 不为前端改名）。

    `row_id` 空 = **新增**；有值 = **编辑该手动行**（「新增与编辑共用同一套」）。
    ⚠️ 金额都是**字符串**（原样交给 `manual_row_payload` 校验 —— 判定只许有一处）。
    """

    row_id: str = ""
    doc_date: str = ""
    bill_no: str = ""
    bill_name: str = ""
    biz_type: str = ""
    payee: str = ""
    category: str = ""
    amount_approved: str = ""
    stat_paid: str = ""
    ownership_id: str = ""


@api_router.post("/api/m03/actions/manual-save")
def api_manual_save(req: ManualSaveIn, session: Session = DBSession) -> dict:
    """**新增 / 编辑手动付款通知书**（§4.2.6）—— 校验不通过 ⇒ `ok=False`（**不落库**），
    外壳据此**保留草稿行**让用户改（不清空已填内容，R14③）。

    ⚠️ 与 PRG `POST /m03/notices/save` **共用** `notice_actions.apply_manual_save` ——
       本文件只做「取数 → 判定 → 落库 → 回 JSON」，⛔ 不重复、不另写任何判定或文案。
    """
    from app.core.identity import current_operator
    from app.mod03_notice.notice_actions import apply_manual_save

    data = req.model_dump()
    row_id = data.pop("row_id", "")
    try:
        row, message = apply_manual_save(
            session, row_id=row_id, entered_by=current_operator(), fields=data
        )
    except MustReportError as exc:
        return {"ok": False, "row_id": row_id, "message": exc.message}

    return {
        "ok": True,
        "row_id": str(row.id),
        "ph_id": row.ph_id,
        "is_new": not str(row_id or "").strip().isdigit(),
        "row": {
            "bill_no": row.bill_no or "",
            "doc_date": row.doc_date or "",
            "category": row.category or "",
            "amount_approved": str(row.amount_approved),
            "stat_settle": str(row.stat_settle),
            "stat_paid": str(row.stat_paid),
            "ownership_id": row.ownership_id,
        },
        "message": message,
    }


class NoticeIdIn(BaseModel):
    notice_id: int


@api_router.post("/api/m03/actions/manual-delete-impact")
def api_manual_delete_impact(req: NoticeIdIn, session: Session = DBSession) -> dict:
    """**删除前的影响范围**（§7.2 / §9.4 —— 硬要求）—— 壳弹确认框时**先取这一段**，⛔ 不自己拼。

    ⚠️ 与删除本身**共用** `notice_actions.manual_delete_impact` / `assert_manual_editable`：
       **i8 抓取行连"影响范围"都不给看**（§4.2.7：不提供删除入口）。
    """
    from app.mod03_notice.notice_actions import manual_delete_impact

    try:
        return {"ok": True, **manual_delete_impact(session, req.notice_id)}
    except MustReportError as exc:
        return {"ok": False, "message": exc.message}


@api_router.post("/api/m03/actions/manual-delete")
def api_manual_delete(req: NoticeIdIn, session: Session = DBSession) -> dict:
    """**删除一条手动行**（§4.2.6）—— 只对手动行开放；i8 抓取行永不可删（§4.2.7）。

    ⚠️ 与 PRG `POST /m03/notices/delete` **共用** `notice_actions.apply_manual_delete` ——
       本文件只做「取数 → 判定 → 落库 → 回 JSON」，⛔ 不重复、不另写任何判定或文案。
    """
    from app.mod03_notice.notice_actions import apply_manual_delete

    try:
        row, message = apply_manual_delete(session, req.notice_id)
    except MustReportError as exc:
        return {"ok": False, "notice_id": req.notice_id, "message": exc.message}
    return {"ok": True, "notice_id": int(row.id), "message": message}


class BatchPayIn(BaseModel):
    """**批量付款**的入参（§4.4.4）。

    `drafts` = `{notice_id: {"pay_method": str, "amount": str}}`（表单/输入框的原值，金额由**后端**解析）；
    `request_id` = **幂等号**（前端每次提交生成一个 ⇒ 服务端据它拒重复提交，§4.4.4）。
    """

    ids: list[int] = Field(default_factory=list)
    drafts: dict[str, dict] = Field(default_factory=dict)
    pay_date: str = ""
    remark: str = ""
    request_id: str = ""


@api_router.post("/api/m03/actions/batch-pay")
def api_batch_pay(req: BatchPayIn, session: Session = DBSession) -> dict:
    """**批量付款**（§4.4.4）—— 整批重算，任一不过 ⇒ **整批不产生任何流水**（不落半批）；
    `request_id` 重复 ⇒ **拒绝重复提交**。

    ⚠️ 与 PRG `POST /m03/pay` **共用** `notice_actions.apply_batch_pay` ——
       本文件只做「取数 → 判定 → 落库 → 回 JSON」，⛔ 不重复、不另写任何判定或文案。
    ⚠️ `parse_amount` / `plan_methods_for_pay` 与 PRG **同一份**（都住**存活件** `notice_actions` ✓，
       `§19` 批 4 · S4② 搬过来的）。
    """
    from app.mod03_notice.notice_actions import (
        apply_batch_pay,
        parse_amount,
        plan_methods_for_pay,
    )

    drafts = {
        int(k): {"pay_method": str((v or {}).get("pay_method") or ""),
                 "amount": parse_amount((v or {}).get("amount"))}
        for k, v in (req.drafts or {}).items()
    }
    try:
        created, message = apply_batch_pay(
            session, ids=list(req.ids), drafts=drafts,
            pay_date=req.pay_date, remark=req.remark, request_id=req.request_id,
            plan_methods=plan_methods_for_pay(session),
        )
    except MustReportError as exc:
        return {"ok": False, "created": [], "message": exc.message}

    return {"ok": True, "created": created, "count": len(created), "message": message}


__all__ = ["api_router"]
