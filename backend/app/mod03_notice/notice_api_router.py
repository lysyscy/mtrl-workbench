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


__all__ = ["api_router"]
