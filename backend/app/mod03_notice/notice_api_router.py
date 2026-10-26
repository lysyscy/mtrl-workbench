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
from app.mod03_notice.plan_audit_api import router as plan_audit_router
from app.mod05_flow.models import PAY_METHODS

api_router = APIRouter(tags=["mod03-json"])

api_router.include_router(plan_audit_router)

# ⚠️ **只在页面上成立**的列（值是按钮 / 表单 HTML）—— API 必须剔除，否则就"吐 HTML"了
PAGE_ONLY_KEYS: tuple[str, ...] = ("actions", "_picked")


# --------------------------------------------------------------- 会话 / 筛选（可注入 ⇒ 离线自检）


def get_session() -> Iterator[Session]:
    """查询 / 动作共用的会话（**短事务**）—— 经 `Depends` 暴露 ⇒ 自检可注入假会话（不连库）。"""
    with session_scope() as session:
        yield session


# 写入提交后才发送回执，顶栏历史与返回结果使用同一个已提交事务。
DBSession = Depends(get_session, scope='function')


def notice_filters(period, project, category, approve_status, pay_status) -> NoticeFilters:
    """列表查询共用的筛选解析。

    ⚠️ 与其它页同一约定：**`period=None` ⇒ 用默认（北京时间当月）；`period=""` ⇒ 全部**。

    ⚠️⚠️ **`include_archived=True` —— 这是"取数层"，不是"页面筛选层"**（2026-09-20 修）：
       本函数只服务 `/api/m03/notice-list`，而它的调用方是**壳**（壳拿全量、自己再筛 `ntHit`）。
       ⛔ 取数层**先按页面的"默认隐藏"砍一刀** ⇒ 壳里根本没有剔除行 ⇒ 切「分类 = 剔除」**必然全空**
          （用户 2026-09-20 实测；库里 200 行 → 接口只回 129 行 = 200 − 71）。
       ⚠️ 依赖注入时给的桩若自己造 `NoticeFilters`，记得也要给这个字段（默认 `False`）。
    """
    return NoticeFilters(
        period=default_period(PERIOD_DEFAULT_KEY) if period is None else period,
        project_ids=tuple(project or ()),
        category=category or CATEGORY_ALL,
        approve_status=approve_status,
        pay_status=pay_status,
        include_archived=True,          # ⭐ 取数层给全 —— 默认隐藏是**筛选层**（壳的 `ntHit`）的事
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
    """**恢复剔除**（§4.2.2）—— 必须先勾选；**人工剔除与规则命中的都恢复**（⭐ 2026-10-08 用户裁定）。

    ⚠️ **恢复后一并回填归属**（⭐ 2026-10-08）：规则剔除的行**落库时故意不带归属**
       （`classify.rows_needing_ownership`：避免整批归属校验被误拦）⇒ 不回填的话，
       它们回到列表就是"付款项目未建档" ＋ 项目筛选一挡就再也勾不上（用户实测报障）。
    """
    from app.mod03_notice.notice_actions import refill_ownership

    try:
        report = restore_excluded(repo.notices_as_dicts(session, ids=req.ids), req.ids)
        repo.set_excluded(session, report.restored, excluded=False, source=EXCLUDE_NONE)
        refill = refill_ownership(session, report.restored)
        message = report.message + ("；" + refill.message if refill.message else "")
        return {"ok": True, "restored": list(report.restored),
                "ownership_filled": list(refill.filled), "message": message}
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
    approve_status: str = ""
    bill_no: str = ""
    bill_name: str = ""
    biz_type: str = ""
    payee: str = ""
    category: str = ""
    amount_approved: str = ""
    stat_settle: str | None = None
    stat_paid: str = ""
    ownership_id: str = ""


@api_router.post("/api/m03/actions/manual-save")
def api_manual_save(req: ManualSaveIn, session: Session = DBSession) -> dict:
    """**新增 / 编辑手动付款通知书**（§4.2.6）—— 校验不通过 ⇒ `ok=False`（**不落库**），
    外壳据此**保留草稿行**让用户改（不清空已填内容，R14③）。

    ⚠️ 出口 = `notice_manual_actions.apply_manual_save`（§4.2.6 的校验 / 落库 / 文案**只此一份**）——
       本文件只做「取数 → 判定 → 落库 → 回 JSON」，⛔ 不重复、不另写任何判定或文案。
       （⚠️ 旧页 PRG `POST /m03/notices/save` 已随 `§19` 删除 ⇒ 观测面就是本端点。）
    """
    from app.core.identity import current_operator
    from app.mod03_notice.notice_manual_actions import apply_manual_save

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

    ⚠️ 与删除本身**共用** `notice_manual_actions.manual_delete_impact` / `assert_manual_editable`：
       **i8 抓取行连"影响范围"都不给看**（§4.2.7：不提供删除入口）。
    """
    from app.mod03_notice.notice_manual_actions import manual_delete_impact

    try:
        return {"ok": True, **manual_delete_impact(session, req.notice_id)}
    except MustReportError as exc:
        return {"ok": False, "message": exc.message}


@api_router.post("/api/m03/actions/manual-delete")
def api_manual_delete(req: NoticeIdIn, session: Session = DBSession) -> dict:
    """**删除一条手动行**（§4.2.6）—— 只对手动行开放；i8 抓取行永不可删（§4.2.7）。

    ⚠️ 出口 = `notice_manual_actions.apply_manual_delete`（校验 / 落库 / 文案**只此一份**）——
       本文件只做「取数 → 判定 → 落库 → 回 JSON」，⛔ 不重复、不另写任何判定或文案。
       （⚠️ 旧页 PRG `POST /m03/notices/delete` 已随 `§19` 删除 ⇒ 观测面就是本端点。）
    """
    from app.mod03_notice.notice_manual_actions import apply_manual_delete

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


@api_router.post("/api/m03/payment-context")
def api_payment_context(req: BatchPayIn, session: Session = DBSession) -> dict:
    from app.mod03_notice.notice_pay_actions import payment_context
    try:
        return payment_context(session, ids=req.ids, pay_date=req.pay_date)
    except MustReportError as exc:
        return {"ok": False, "message": exc.message}


@api_router.post("/api/m03/actions/batch-pay")
def api_batch_pay(req: BatchPayIn, session: Session = DBSession) -> dict:
    """**批量付款**（§4.4.4）—— 整批重算，任一不过 ⇒ **整批不产生任何流水**（不落半批）；
    `request_id` 重复 ⇒ **拒绝重复提交**。

    ⚠️ 出口 = `notice_pay_actions.apply_batch_pay`（§4.4.4 的判定 / 落库 / 文案**只此一份**）——
       本文件只做「取数 → 判定 → 落库 → 回 JSON」，⛔ 不重复、不另写任何判定或文案。
       （⚠️ 旧页 PRG `POST /m03/pay` 已随 `§19` 删除 ⇒ 观测面就是本端点。）
    ⚠️ `parse_amount` / `default_pay_method` 与它**同住** `notice_pay_actions` ✓（§4.4.2 的同一份口径）。
    """
    from app.mod03_notice.notice_pay_actions import (
        apply_batch_pay,
        parse_amount,
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
        )
    except MustReportError as exc:
        return {"ok": False, "created": [], "message": exc.message}

    from app.mod05_flow import service as flow_service
    flows = [f for f in flow_service.flows_of_notices(session, created)
             if req.request_id and f.request_id == req.request_id.strip()]
    return {"ok": True, "created": created, "count": len(created), "message": message,
            "flows": [{"notice_id": f.notice_id, "flow_no": f.flow_no, "amount": str(f.amount),
                       "pay_date": f.pay_date, "pay_method": f.pay_method, "remark": f.remark}
                      for f in flows]}


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
    from app.mod01_projects import service as PS
    from app.mod03_notice.models import PaymentNotice
    from app.mod03_notice.sup_match import LVL_NAMES, match_of, pool_of, row_pool_rows

    row = session.get(PaymentNotice, int(req.notice_id))
    if row is None:
        return {"ok": False, "message": f"找不到付款通知书 {req.notice_id}"}
    key = ""
    if row.ownership_id is not None:
        key = next((str(p.warehouse_name or "") for p in PS.all_projects(session)
                    if p.id == int(row.ownership_id)), "")
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
    from app.mod03_notice.notice_actions import jc_supplier_problem

    from app.mod03_notice.service import get_notice
    from app.mod11_jc.service import links_by_notice

    row = get_notice(session, int(req.notice_id), with_for_update=True, populate_existing=True)
    # ⚠️ 判定**只有一处**（`notice_actions.jc_supplier_problem`）—— 本层只负责"取数 → 判 → 落库 → 回 JSON"
    problem = jc_supplier_problem(row)
    if problem:
        return {"ok": False, "message": problem}
    if row.excluded or row.i8_revoked:
        return {"ok": False, "message": "撤单或剔除后不能维护供应商；已有关系仍可查看、解除"}
    if links_by_notice(session, [int(row.id)]).get(int(row.id)):
        return {"ok": False, "message": "已关联时供应商由合同确定，请更换合同或先解除关联"}
    row.jc_supplier = str(req.supplier or "").strip()[:128]
    session.flush()
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
    from app.mod03_notice.domain import PayRow
    reason = ("已剔除" if row.excluded else "i8 已撤单" if row.i8_revoked else
              PayRow(row.notice_id, row.approve_status, row.pay_amount, row.category, bool(row.has_link)).label)
    out.update({
        "pay_block_reason": reason,
        "category": row.category,
        "project_name": row.project_name,
        "ownership_id": row.ownership_id,
        "is_excluded": bool(row.excluded),
        "exclude_source": row.exclude_source,
        "exclude_rule_hint": row.exclude_rule_hint,
        "is_revoked": bool(row.i8_revoked),
        "is_manual": bool(row.is_manual),
        "edited_fields": list(row.edited_fields or ()),
        "amount_approved": str(row.amount_approved),
        "amount_paid": str(row.amount_paid),
        "pay_amount": str(row.pay_amount),
        "stat_settle": str(row.stat_settle),
        "stat_paid": str(row.stat_paid),
        "has_effective_flow": bool(row.effective_flows),
        "has_any_flow": bool(row.flows),
        "has_link": bool(row.has_link),
        # ⭐ `P4` 超付（§4.4.6）：**判定在后端**（`NoticeRow.is_overpaid`），壳侧只负责把
        #    「超付」标记渲出来 —— ⛔ 壳里不许再算一遍 `amount_paid > amount_approved`。
        "is_overpaid": bool(row.is_overpaid),
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
        "payment_methods": list(PAY_METHODS),
        "items": [_api_item(rec) for rec in data["rows"]],
    }


@api_router.get("/api/m03/payment-preview")
def payment_preview(ids: list[int] = Query(default=[]), session: Session = DBSession) -> dict:
    """核对所选通知书的当前付款状态；与列表复用金额和不可付原因。"""
    data = build_page_data(session, filters=notice_filters("", [], "", "", ""), notice_ids=ids)
    return {"payment_methods": list(PAY_METHODS), "items": [_api_item(rec) for rec in data["rows"]]}


class ExportIn(BaseModel):
    """导出请求（`TAIL-04` · §7.1）。

    ⚠️ **收 id 列表，⛔ 不收"筛选条件"** —— 页面的筛选（年月 / **多选**项目 / 分类 / 审批状态 /
      付款状态）是**前端**算的 ⇒ 传条件就得在后端**再实现一遍** ⇒ **两套口径必打架**。
    ⭐ 传 id 还顺带把**顺序**带上了（导出的行序 = 屏幕上的行序）。
    """

    ids: list[int] = Field(default_factory=list)


def _export_row(rec: dict) -> dict:
    """一行 → **导出值**（键 = `nt_export.COLUMNS` 的第二项）。

    ⚠️ 本函数**只做「页面显示值」的对齐**，⛔ **不在这里判定业务**（剔除 / 撤单 / 派生的判定全在
       `list_view` / `domain` 里）—— 判定搬进导出层 = 又一份口径。
    ⚠️ 金额一律给**原始数值串**（⛔ 不用列表里的 `*_text`：那是**千分位排版**，
       Excel 里要的是数字 —— 口径见 `naive_export` 模块头「取值」）。
    """
    it = _api_item(rec)
    row = rec.get("_row")
    # 「分类」那格：页面 `ntArchTag` **先判剔除、后判撤单**，两者都不是才显示分类 ⇒ 顺序照抄
    if it.get("is_excluded"):
        category_text = "剔除"
    elif it.get("is_revoked"):
        category_text = "i8 已撤单"
    else:
        category_text = it.get("category_label") or ""
    return {
        "doc_date": it.get("doc_date") or "",
        "bill_no": it.get("bill_no") or "",
        "project_display": it.get("project_display") or "",
        "category_text": category_text,
        "bill_name": it.get("bill_name") or "",
        "biz_type": it.get("biz_type") or "",
        "payee": it.get("payee") or "",
        "jc_supplier": it.get("jc_supplier") or "",
        "input_by": it.get("input_by") or "",
        "amount_approved": str(getattr(row, "amount_approved", "") or ""),
        "pay_amount": str(getattr(row, "pay_amount", "") or ""),
        "amount_paid": str(getattr(row, "amount_paid", "") or ""),
        "stat_settle": str(getattr(row, "stat_settle", "") or ""),
        "stat_paid": str(getattr(row, "stat_paid", "") or ""),
        "approve_status": it.get("approve_status") or "",
        "pay_status": it.get("pay_status") or "",
    }


@api_router.post("/api/m03/notices/export")
def export_notices(req: ExportIn, session: Session = DBSession) -> dict:
    """导出**付款通知书台账**（`TAIL-04` · `REQ-R1` · §7.1）⇒ `{ok, filename, rows, content_b64}`。

    ⭐ **行** = 传入的那些 id（= **屏幕上看到的**，**连它的顺序一起**）；
    **列** = 页面表头 `NT_THEAD` 去掉「勾选 / 操作」⇒ 16 列；**取值** = **页面显示的那个值**
    （逐列口径见 `report_export/nt_export.py` 的模块头）。

    ⚠️ **取数是"全量捞一遍再按 id 挑"**：本端点的"筛选"**全靠传入的 id**
       ⇒ 所以这里的 `NoticeFilters` 是**全开**的（`period=""` 全部 / 无项目 / 无分类 /
       无审批状态 / 无付款状态 / `include_archived=True`），⛔ **不是**页面的默认筛选。
       若这里跟着页面默认走（默认隐藏剔除行），用户切到「分类 = 剔除」导出的就会**是空的** ——
       页面的"默认隐藏"是**筛选层**的事，不是取数层（同 `notice_filters` 那条注释的口径）。

    ⚠️ **合计行**：`live_rows` 只放**有效行**（`NoticeRow.is_live`）—— 剔除行不计入、
       ⚠️ 但「有牵涉的撤单行」**仍计入**（§4.2.7 不许静默丢账）；一行有效行都没有 ⇒ 不写合计行
       （与页面同口径，见 `nt_export` 模块头）。
    """
    import base64
    from datetime import date

    from app import export_registry as EXP
    X = EXP.get("nt")

    # ⚠️ **取数层给全量**（见 docstring）—— 每一档都显式写出来，⛔ 别用 `notice_filters()` 的默认值
    filters = NoticeFilters(
        period="", project_ids=(), category=CATEGORY_ALL,
        approve_status="", pay_status="", include_archived=True,
    )
    data = build_page_data(session, filters=filters)
    by_id = {int(rec["notice_id"]): rec for rec in (data.get("rows") or ())}
    ids = [int(i) for i in (req.ids or [])]
    # ⚠️ **按传入的 id 顺序**出行（⛔ 不是按库里的顺序）—— 那是**屏幕上的行序**
    pairs = [(_rec, _export_row(_rec)) for _rec in (by_id[i] for i in ids if i in by_id)]
    out = [r for _, r in pairs]
    live = [r for rec, r in pairs
            if rec.get("_row") is not None and bool(rec["_row"].is_live)]
    blob = X.build_xlsx(out, live_rows=live)
    name = f"付款通知书台账_{date.today().strftime('%Y%m%d')}.xlsx"
    return {"ok": True, "filename": name, "rows": len(out),
            "content_b64": base64.b64encode(blob).decode("ascii")}


__all__ = ["api_router", "get_session"]
