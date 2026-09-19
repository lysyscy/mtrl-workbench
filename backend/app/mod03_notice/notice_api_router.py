"""`MOD-03` **JSON API 汇总** —— 供前端壳（`app/web/`）用 `fetch` 调用。

⚠️ 判定一律调**纯函数出口**（`notice_actions.*` / `domain.*`，落库走同一个 `repository`）——
   本文件只做「取数 → 判定 → 落库 → 回 JSON」，⛔ **不重复、不另写任何判定**
   （一份内容只许一个主人）。

⚠️ 回执形状：HTTP **恒 200**，用 `ok` 标志区分成败 —— 前端壳是"就地改、即时反馈"，
   靠 HTTP 状态码分流会逼它写第二套错误分支（与本项目「内部工具、简单优先」不符）。
   失败时 `message` 一定是**可直接给人看**的一句中文（判定函数已经这么产出了）。

⭐ 2026-09-19（`§19` 批 4 · **S4⑤**）：列表查询端点 `GET /api/m03/notice-list` 从
   `notice_router.py` 搬到这里（那是**页面 router**，随删页消失）；**关系件**（会话依赖 /
   筛选解析 / API 必须剔除的页面专用列）也一并归到本件 —— 旧页删净后，MOD-03 对外的
   **可调用面只剩 JSON API**，故 `notice_http.py`（会话 ＋ 筛选）也随之并入本文件。
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.period import default_period
from app.mod03_notice import repository as repo
from app.mod03_notice.list_data import PERIOD_DEFAULT_KEY, build_page_data
from app.mod03_notice.list_view import CATEGORY_ALL, NoticeFilters
from app.mod03_notice.models import EXCLUDE_BY_MANUAL, EXCLUDE_NONE
from app.mod03_notice.notice_actions import (
    change_category,
    manual_exclude,
    restore_excluded,
)
from app.mod03_notice.page import SORT_NONE

api_router = APIRouter(tags=["mod03-json"])

# ⚠️ **只在页面上成立**的列（值是按钮 / 表单 HTML）—— API 必须剔除，否则就"吐 HTML"了
PAGE_ONLY_KEYS: tuple[str, ...] = ("actions", "_picked")


# --------------------------------------------------------------- 会话 / 筛选（可注入 ⇒ 离线自检）


def get_session() -> Iterator[Session]:
    """查询 / 动作共用的会话（**短事务**）—— 经 `Depends` 暴露 ⇒ 自检可注入假会话（不连库）。"""
    with session_scope() as session:
        yield session


DBSession = Depends(get_session)


def notice_filters(period, project, category, approve_status, pay_status) -> NoticeFilters:
    """列表查询共用的筛选解析。

    ⚠️ 与其它页同一约定：**`period=None` ⇒ 用默认（北京时间当月）；`period=""` ⇒ 全部**。
    """
    return NoticeFilters(
        period=default_period(PERIOD_DEFAULT_KEY) if period is None else period,
        project_ids=tuple(project or ()),
        category=category or CATEGORY_ALL,
        approve_status=approve_status,
        pay_status=pay_status,
    )


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


# --------------------------------------------------------------- 列表查询（新壳 m03 页的数据源）


class SupMatchIn(BaseModel):
    """「集采供应商自动匹配」入参（§6.6.3 · `M5-5`）。"""

    notice_id: int


@api_router.post("/api/m03/actions/sup-match")
def api_sup_match(req: SupMatchIn, session: Session = DBSession) -> dict:
    """集采供应商**自动匹配**（§6.6.3）—— 拿**本项目候选池**去探测**本行单据名**。

    ⭐ `M5-5`：判定**从壳里搬到后端**（原先在 `index.html` 的 `supPool`/`supFrags`/`supMatch`）——
       它是业务判定（决定"预填 / 让选 / 手动"三条分叉），且含一条"写错不报错"的片段长度规则。
    ⚠️ **只算不写**（⛔ 本端点不落库）：三条分叉（1 家预填 / ≥2 家让选 / 0 家手动）与
       "预填值须经人**采用**才转正式"都由壳侧编排 ⇒ 落库一律走 `jc-supplier` 那个端点。
    ⚠️ 项目键 = 该行**归属档案行的仓库名**（§2.7.4），与集采合同的项目键**同一空间** ⇒ 直接判等。
    """
    from sqlalchemy import select

    from app.mod01_projects.models import Project
    from app.mod03_notice.models import PaymentNotice
    from app.mod03_notice.sup_match import LVL_NAMES, match_of, pool_of, row_pool_rows

    row = session.get(PaymentNotice, int(req.notice_id))
    if row is None:
        return {"ok": False, "message": f"找不到付款通知书 {req.notice_id}"}
    key = ""
    if row.ownership_id is not None:
        proj = session.execute(
            select(Project.warehouse_name).where(Project.id == int(row.ownership_id))
        ).scalar()
        key = str(proj or "")
    pool = pool_of(row_pool_rows(session), project_key=key)
    # ⚠️ **单据名称在 `fields["BillName"]` 里**（`payment_notice` 表**没有独立列** —— 同 `list_view` 的 `NoticeRow.bill_name`）。
    #    ⛔ 别写 `getattr(row, "bill_name")`：那永远取不到、会**静默变成"永不匹配"**。
    doc = str((row.fields or {}).get("BillName") or "")
    hit = match_of(doc, pool)
    return {"ok": True, "notice_id": int(row.id), "project_key": key, "pool": pool,
            "level": hit["level"], "level_name": hit["level_name"] or LVL_NAMES[0],
            "cands": hit["cands"]}


class JcSupplierIn(BaseModel):
    """「集采实际供应商」入参（§6.6.3 · `M5-5`）。"""

    notice_id: int
    supplier: str = ""


@api_router.post("/api/m03/actions/jc-supplier")
def api_jc_supplier(req: JcSupplierIn, session: Session = DBSession) -> dict:
    """设置「**集采实际供应商**」（§6.6.3 · `DEV-P-04`）—— ⭐ `M5-5`。

    ⚠️ 判定**搬到这里**（原先在壳里 `editSup` 那句话）：**只有「集采」分类的通知书**才允许填 ——
       该字段是「按供应商统计欠款」与**集采台账付款引用的候选收窄**两件事的**关联锚点**，
       别的分类填了没有意义。⛔ 前端不许再自行判定后"假装成功"。
    ⚠️ 该字段 i8 **不提供** ⇒ 只能是人工值 ⇒ **不受再次导入覆盖**（`merge.PROTECTED`）。
    """
    from app.mod03_notice.models import PaymentNotice
    from app.mod03_notice.notice_actions import jc_supplier_problem

    row = session.get(PaymentNotice, int(req.notice_id))
    # ⚠️ 判定**只有一处**（`notice_actions.jc_supplier_problem`）—— 本层只负责"取数 → 判 → 落库 → 回 JSON"
    problem = jc_supplier_problem(row)
    if problem:
        return {"ok": False, "message": problem}
    row.jc_supplier = str(req.supplier or "").strip()[:128]
    session.commit()
    return {"ok": True, "notice_id": int(row.id), "supplier": row.jc_supplier,
            "message": (f"已录入集采实际供应商：{row.jc_supplier}"
                        if row.jc_supplier else "已清空集采实际供应商")}


def _api_item(rec: dict) -> dict:
    """一行 → API 载荷 = **显示值**（`list_data._row_dict` 产的）
    ＋ **状态字段**（前端壳要靠它判"能不能勾选 / 是否剔除 / 是否手动行"）。

    ⚠️ 补的是**语义字段**（`is_excluded` / `is_manual` / …），**不是**原型字段名 ——
       字段名映射由前端适配层做（`app/web/index.html` 的 `adaptNotice`）⇒ API 不为某个前端定制。
    ⛔ 页面专用 HTML（`PAGE_ONLY_KEYS`）**仍然不进 API**。
    ⚠️ 金额一律 **str**（Decimal 直接 JSON 化会变 float ⇒ 金额精度不可控；
       前端只拿它显示与求和，**落库的值一律由后端判定**）。
    """
    row = rec.get("_row")
    out = {k: v for k, v in rec.items() if k != "_row" and k not in PAGE_ONLY_KEYS}
    if row is None:
        return out
    out.update({
        "category": row.category,
        "project_name": row.project_name,
        "ownership_id": row.ownership_id,
        "is_excluded": bool(row.excluded),
        "exclude_source": row.exclude_source,
        "is_revoked": bool(row.i8_revoked),
        "is_manual": bool(row.is_manual),
        "edited_fields": list(row.edited_fields or ()),
        "amount_approved": str(row.amount_approved),
        "amount_paid": str(row.amount_paid),
        "pay_amount": str(row.pay_amount),
        "stat_settle": str(row.stat_settle),
        "stat_paid": str(row.stat_paid),
        "has_effective_flow": bool(row.effective_flows),
        "has_link": bool(row.has_link),
    })
    return out


@api_router.get("/api/m03/notice-list")
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
    """付款通知书列表的数据源（含筛选与计数）—— 四金额 / 分类 / 剔除 / 付款状态 / 计数都在这里。

    ⚠️ 与页面件无关：数据组装在 `list_data.build_page_data`（唯一出口），本端点只做**形状转换**。
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
        "items": [_api_item(rec) for rec in data["rows"]],
    }


__all__ = ["api_router", "get_session"]
