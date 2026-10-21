"""MOD-05 路由：JSON API 与壳调用的表单写入回执。

⚠️ 薄层：判定与形态全在 `domain.py`（纯函数）；组装在 `service.py`；页面在 `view.py`。
⚠️ 取数经 `Depends` 暴露 ⇒ 自检可注入桩（**不连库**），与 `MOD-02` / `MOD-04` 同款。

口径：《说明书》§4.4.2（一次付款一条流水 / 两态）· §4.4.5（撤销必填原因）· §4.5.1（欠款三类）
      · §4.5.2（期初占位行）· §4.5.4（逐月台账）· §4.5.5（付款统计）。
"""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, Form, Query
# ⚠️ 2026-09-21：`HTMLResponse` 已无人用（本模块的服务端渲染页全清）⇒ 从 import 里去掉。
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod05_flow import repository as repo
from app.mod05_flow import service as svc
from app.mod05_flow import history
from app.mod05_flow.domain import default_flow_period
# ⭐ `TAIL-283`：导出合计的基数判「生效 / 已撤销」用**域里的常量**（⛔ 别在本文件写 'effective' 字面）
from app.mod05_flow.models import FLOW_EFFECTIVE
router = APIRouter(tags=["mod05"])
# 历史付款导入已归档：docs/archive/retired-imports-20261015/README.md。

PageData = Callable[..., dict]

# ⚠️ `year_month` 统一语义（页面与 API 一致）：
#    **不传（None）= 用默认（北京时间当月）**；**显式传空（''）= 全部月份**。
YM_DOC = "YYYY-MM；**空=全部**；不传=当月"


# --------------------------------------------------------------- 依赖（可注入）


def get_flows_data() -> PageData:
    def _load(**kw) -> dict:
        with session_scope() as s:
            return svc.build_flows(s, **kw)

    return _load


def get_debt_data() -> PageData:
    def _load(**kw) -> dict:
        with session_scope() as s:
            # ⭐ `TAIL-100`：走 `build_debt_live`（＝ `build_debt` ＋ **注入集采欠款**）——
            #   原先这里直接 `build_debt(s)` ⇒ `jc_debt` 恒 `None` ⇒ 「集采欠款」恒 ¥0.00。
            return svc.build_debt_live(s, **kw)

    return _load


def get_ledger_data() -> PageData:
    def _load(**kw) -> dict:
        with session_scope() as s:
            return svc.build_ledger(s, **kw)

    return _load


def get_stats_data() -> PageData:
    def _load(**kw) -> dict:
        with session_scope() as s:
            return svc.build_stats(s, **kw)

    return _load


def _resolve_ym(value: str | None) -> str:
    return default_flow_period() if value is None else value


# --------------------------------------------------------------- API（JSON）


class FlowExportIn(BaseModel):
    """导出请求（`TAIL-04` · §7.1）。

    ⚠️ **收 id 列表，⛔ 不收"筛选条件"** —— 页面的筛选（年月 / **多选**项目 / 付款方式 /
      状态 / 关键词）是**前端**算的 ⇒ 传条件就得在后端**再实现一遍** ⇒ **两套口径必打架**。
    ⭐ 传 id 还顺带把**顺序**带上了（导出的行序 = 屏幕上的行序）。
    """

    ids: list[int] = Field(default_factory=list)


@router.post("/api/m05/flows/export")
def export_flows(payload: FlowExportIn, load: PageData = Depends(get_flows_data)) -> dict:
    """导出**付款流水**（`TAIL-04` · `REQ-R1` · §7.1）⇒ `{ok, filename, rows, content_b64}`。

    ⭐ **行** = 传入的那些 id（= **屏幕上看到的**，**连它的顺序一起**）；
    **列** = 页面表头 `FL_THEAD` 去掉「操作」⇒ **14 列**（`TAIL-283` 起）；**取值** = **页面显示的那个值**。

    ⚠️ **本端点不用 join 通知书 / 项目** —— `/api/m05/flows` 的 `rows` 里**已经有**：
      · `doc_no`（单据编码，= 通知书的 `bill_no`）· `flow_no`（**真业务流水号**）
      · 通知书五项（`doc_date` / `bill_name` / `payee` / `amount_approved` / `category_label`，
        由 `service._flow_dict` 用**一次预读**的通知书字典装配；失联行五项为空 ⇒ 流水照出）
      · `project_display`（付款项目 = **展示名**，由 `service._flow_dict` 走
        `core.projects.project_label` 算好 —— ⛔ 不是仓库名那个"键"、更不是 `project_id`）
      · `status_label`（**已给中文**「生效 / 已撤销」）
      ⇒ ⭐ **取数端本来就够**，本端点只做"按 id 挑 ＋ 换列名 ＋ 拼状态文案"。

    ⚠️ **状态那格**：页面把「撤销原因」**并进状态格里**（`已撤销 ＋ 原因`）⇒
       导出也**并进去**（与页面一致）；⛔ 另开一列会让表与屏幕**对不上号**。
    """
    import base64
    from datetime import date

    from app import export_registry as EXP
    X = EXP.get("fl")

    # ⭐⭐ `TAIL-283`：这里**必须显式传空** ⇒ **全量**。`load()` 不传 = 后端默认**当月** ——
    #    而页面上翻到历史月份、或把「付款年月」摆到「年 / 全部」看到的那些行，
    #    id 传进来了却**挑不到行** ⇒ 屏幕上看得见、导出来是空的（原注释写"空参=全量"，
    #    与运行代码**正相反**，本次连同注释一起改对）。
    data = load(year_month="")
    all_rows = data.get("rows") or []
    by_id = {int(r["id"]): r for r in all_rows if r.get("id") is not None}
    ids = [int(i) for i in (payload.ids or [])]
    # ⚠️ **按传入的 id 顺序**出行（⛔ 不是按库里的顺序）—— 那是**屏幕上的行序**
    picked = [by_id[i] for i in ids if i in by_id]

    def _status(r: dict) -> str:
        txt = str(r.get("status_label") or "")
        reason = str(r.get("revoke_reason") or "").strip()
        return f"{txt}（{reason}）" if reason else txt

    out = [{
        "flow_no": r.get("flow_no") or "",
        "doc_no": r.get("doc_no") or "",
        "doc_date": r.get("doc_date") or "",
        "bill_name": r.get("bill_name") or "",
        "project_display": r.get("project_display") or "",
        "payee": r.get("payee") or "",
        "category_label": r.get("category_label") or "",
        # ⚠️ `None`（通知书失联）= 留空；`"0.00"` = 审批额**真的**是 0 ⇒ 两种不许混。
        "amount_approved": r.get("amount_approved"),
        "pay_date": r.get("pay_date") or "",
        "amount": r.get("amount"),
        "pay_method": r.get("pay_method") or "",
        "remark": r.get("remark") or "",
        "created_by": r.get("created_by") or "",
        "status_text": _status(r),
    } for r in picked]
    # ⭐ 合计基数 = 已选行里**生效**的那些（与屏幕同口径：**已撤销不进合计**）。
    # ⚠️ 边界：选中行**全是已撤销**时屏幕仍画「合计（生效 0 条）¥0.00」⇒ 导出也要有那一行；
    #    共用内核在 `total_rows=[]` 时**不写**合计行 ⇒ 用它的显式参数 `total_always=True`
    #    （⛔ 原先在这里塞一条合成行 `{"amount":"0.00"}` 逼内核写 —— 语义只活在本端点、
    #     内核看不见，且将来 `TOTAL_KEYS` 加列会静默补 0；2026-10-11 双轴 review 改掉）。
    #    `rows` 为空（一个 id 都没挑到）时内核仍不写合计行 ⇒ 不会凭空补一排 0。
    blob = X.build_xlsx(out, total_rows=[r for r in picked if r.get("status") == FLOW_EFFECTIVE],
                        total_always=True)
    name = f"付款流水_{date.today().strftime('%Y%m%d')}.xlsx"
    return {"ok": True, "filename": name, "rows": len(out),
            "content_b64": base64.b64encode(blob).decode("ascii")}


@router.get("/api/m05/flows")
def api_flows(
    year_month: str | None = Query(None, description=YM_DOC),
    status: str = Query("", description="effective / revoked / 空=全部"),
    pay_method: str = Query(""),
    project_id: str = Query(""),
    keyword: str = Query(""),
    load: PageData = Depends(get_flows_data),
) -> dict:
    """付款流水列表（筛选即时生效；**不分页**）。"""
    return load(
        year_month=_resolve_ym(year_month), status=status or None,
        pay_method=pay_method or None,
        project_id=int(project_id) if str(project_id).strip() else None, keyword=keyword,
    )


@router.get("/api/m05/debt")
def api_debt(load: PageData = Depends(get_debt_data)) -> dict:
    """欠款：三类合计 ＋ 按项目归集（集采只展示、**不在本域计算**）。"""
    return load()


@router.get("/api/m05/ledger")
def api_ledger(
    project_id: int = Query(..., description="台账两侧**共用**的项目"),
    end_ym: str = Query("", description="止月 YYYY-MM（空=按数据自动取到末月）"),
    load: PageData = Depends(get_ledger_data),
) -> dict:
    """逐月台账（两侧：辅材 / 机械）。"""
    return load(project_id=int(project_id), end_ym=end_ym)


@router.get("/api/m05/stats")
def api_stats(
    granularity: str = Query("", description="week（默认）/ month"),
    year: int = Query(0), quarter: int = Query(0), bucket: str = Query(""),
    load: PageData = Depends(get_stats_data),
) -> dict:
    """付款统计（左按项目 · 右时间轴；**换粒度不换口径**）。"""
    return load(granularity=granularity, year=year or None, quarter=quarter or None, bucket=bucket)


class OpeningPaymentIn(BaseModel):
    project_id: int
    category: str
    payment: str


class HistorySaveIn(BaseModel):
    id: int | None = Field(None, gt=0)
    project_id: int = Field(gt=0)
    category: str
    entry_kind: str = "manual"
    cutoff_ym: str
    settle_amount: str
    paid_amount: str
    remark: str = Field("", max_length=512)
    token: str = ""


class HistoryDeleteIn(BaseModel):
    id: int = Field(gt=0)
    token: str


@router.post("/api/m05/history/save")
def api_history_save(body: HistorySaveIn) -> dict:
    with session_scope() as s:
        return history.save(s, body.model_dump(exclude={"token"}), body.token)


@router.post("/api/m05/history/delete")
def api_history_delete(body: HistoryDeleteIn) -> dict:
    with session_scope() as s:
        return history.delete(s, body.id, body.token)


@router.post("/api/m05/ledger/opening-payment")
def api_opening_payment(body: OpeningPaymentIn) -> dict:
    return JSONResponse(status_code=410, content={"ok": False, "message": "页面已更新，请刷新后在台账中直接修改付款"})


@router.get("/api/m05/flows/{flow_id}/revoke-info")
def api_revoke_info(flow_id: int) -> dict:
    with session_scope() as s:
        flow = repo.get_flow(s, flow_id)
        if flow is None or flow.status != FLOW_EFFECTIVE:
            raise MustReportError("该流水不存在或已撤销，请刷新页面")
        return {"ok": True, **repo.revoke_info(s, flow)}


@router.post("/api/m05/flows/{flow_id}/revoke")
def api_revoke(
    flow_id: int,
    reason: str = Query(..., description="**必填**（空 ⇒ 语义错误）"),
    changed_by: str = "",
    stat_choice: str = "",
    expected: str = "",
) -> dict:
    """撤销一条流水（§4.4.5）—— 原因交给 `domain.revoke_flow` 把关（**空原因被拒**）。"""
    with session_scope() as s:
        flow = repo.get_flow(s, flow_id, for_update=True)
        if flow is None:
            raise MustReportError(f"流水 {flow_id} 不存在")
        from app.mod11_jc import service as jc
        from app.mod03_notice import service as notices

        nid = int(flow.notice_id or 0)
        # 付款侧须在当前事务内锁通知书，覆盖事实确认、撤销流水与统计重算。
        if nid:
            from app.mod03_notice.models import PaymentNotice
            s.get(PaymentNotice, nid, with_for_update={"key_share": True}, populate_existing=True)
        info = repo.revoke_info(s, flow)
        if expected and expected != info["expected"]:
            raise MustReportError("流水或统计付款金额已变化，请重新打开撤销窗口")
        before = jc.notice_payment_effect(s, nid) if nid else None
        protected = bool(before and notices.stat_paid_is_protected(s, nid))
        result = repo.revoke(s, flow, reason=reason, changed_by=changed_by, stat_choice=stat_choice)
        result["notice_id"] = flow.notice_id
        if before:
            after = jc.notice_payment_effect(s, nid)
            result["jc_effect"] = {"contract_id": before["contract_id"],
                                   "before": str(before["pay_sum"]), "after": str(after["pay_sum"]),
                                   "protected": protected and stat_choice != "auto"}
        else:
            result["jc_effect"] = None
        return result


# --------------------------------------------------------------- 页面（PRG）


# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 3**）：本模块的**四个服务端渲染页已整体删除**（授权 `D18`）——
#    `GET /m05`（付款流水）· `GET /m05/debt`（欠款）· `GET /m05/ledger`（逐月台账）· `GET /m05/stats`
#    （付款统计）＋ PRG `POST /m05/revoke`（壳走 `POST /api/m05/flows/{id}/revoke` ✓）＋ **`view.py`（451 行）**。
#    ⇒ 这四页的读一律走 **JSON API**（`/api/m05/flows` · `/debt` · `/ledger` · `/stats`，壳在用 ✓）；
#    ⛔ 别再往本文件加页面路由（`D18` 的口径：新页面 = 新壳 + API）。
# ⚠️ 保留三个壳正在调用的表单写入口；回 JSON 回执，不再跳转旧页面。
#    （`POST /m05/opening` · `/m05/opening/delete` · `/m05/ledger/remark`）**新壳正在用**（另有真机 `_e2e_m05_wired.py`）。
# 历史付款导入已退出系统，源码与说明在docs/archive/retired-imports-20261015。





@router.get("/api/m05/ledger/export")
def api_ledger_export(
    projects: str = Query("", description="项目（**仓库名** = 候选键，逗号分隔；≥2 个 ⇒ 打一个 zip）"),
    ym: str = Query("", description="报告月 `YYYY-MM`（空 = 材料报表类默认 = 上月，§9.2）"),
):
    """导出**逐月欠款台账成品**（`TAIL-04` 路径①）—— **每个项目一本工作簿 / 三个 sheet**
    （`辅材` / `机械` / `特殊费用月报表`）；选 ≥2 个项目 ⇒ 打成一个 zip。

    ⚠️ 失败（**一个项目都没选** · 项目**不在档案里** · 模板缺失/损坏 · **显示区对账不过**）⇒
       **JSON 200 ＋ `ok:false` ＋ 中文原因**，壳侧据 `content-type` 分流（同另三条导出）。
       ⛔ 不回 4xx：那样用户只看到一句 `HTTP 400`，而"没选项目""该项目没建档"这类话必须给人看。
    """
    from urllib.parse import quote

    from fastapi.responses import FileResponse, JSONResponse

    from app import export_registry as EXP
    EX = EXP.get("service")

    keys = [k.strip() for k in str(projects or "").split(",") if k.strip()]
    try:
        with session_scope() as s:
            path = EX.export_ledger(s, keys, ym)
    except MustReportError as exc:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(exc)})
    media = ("application/zip" if path.suffix == ".zip"
             else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return FileResponse(path, media_type=media, filename=path.name,
                        headers={"X-Export-Filename": quote(path.name)})


@router.get("/api/m05/debt/export")
def api_export_total_debt(
    projects: str = Query("", description="要导出的项目（**仓库名**，逗号分隔；**顺序即导出行序**；空 = 全部项目）"),
):
    """导出**总欠款表**（用户 2026-09-20 定）—— 每个项目一行：`集采 / 辅材 / 机械`。

    - ⭐ 列序**由用户指定**：**A 序号 · B 项目展示名 · C 集采 · D 辅材 · E 机械**
      （⛔ 别"顺手优化"成别的顺序）。
    - ⚠️ 口径**全部复用现场那两个函数**（辅材/机械 = `debt_by_category`；集采 = `build_list`）
      ⇒ 这张表与页面上看到的欠款**必然是同一个数**（⛔ 不另写一套算钱的 —— 那迟早走形）。
    - ⚠️ **机械欠款不含机械费结算**（来源在 `MOD-06`、未接通）⇒ **表尾写了同一句说明**：
      文件一旦离开页面，读到的人还得知道这件事（否则就是"看着正常的错数"）。
    - ⚠️ 失败（一条都算不出来）⇒ **JSON 200 ＋ `ok:false` ＋ 中文**，
      壳侧据 `content-type` 分流（同另四条导出）—— ⛔ 不回 4xx。
    """
    from urllib.parse import quote

    from fastapi.responses import FileResponse, JSONResponse

    from app.mod05_flow import service as svc

    try:
        with session_scope() as s:
            path, _note = svc.export_total_debt(s, projects)
    except MustReportError as exc:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(exc)})
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
        # ⚠️ 文件名**由后端带出**（⛔ 不让壳自己拼：命名规则两处各写一份，改一处就会静默走形）
        headers={"X-Export-Filename": quote(path.name)},
    )





# --------------------------------------------------------------- 表单写动作（JSON 回执）


@router.post("/m05/opening")
def act_opening(
    category: str = Form(...), project_id: int = Form(...), cutoff_ym: str = Form(""),
    settle_amount: str = Form(""), paid_amount: str = Form(""), remark: str = Form(""),
    end_ym: str = Form(""),
) -> dict:
    """录入 / 覆盖期初占位行；直接回执给壳，避免写入后跳转已退役页面。

    ⚠️ **参数一律 `Form`**（同上：期初表单的输入全在 body）。
    """
    return JSONResponse(status_code=410, content={"ok": False, "message": "页面已更新，请刷新后在辅材台账中新增历史行"})


@router.post("/m05/opening/delete")
def act_opening_delete(
    opening_id: int = Form(...), project_id: int = Form(0), end_ym: str = Form("")
) -> dict:
    """删除期初占位行并回执；参数仍用 Form。"""
    return JSONResponse(status_code=410, content={"ok": False, "message": "页面已更新，请刷新后删除对应历史行"})


@router.post("/m05/ledger/remark")
def act_remark(
    category: str = Form(...), project_id: int = Form(...), ym: str = Form(""),
    remark: str = Form(""), end_ym: str = Form(""),
) -> dict:
    """写 / 清台账备注（空串 = 清除该格；键 = 口径 + 项目 + 月）并回执。

    ⚠️ **参数一律 `Form`**（同上）。
    """
    with session_scope() as s:
        text = repo.set_remark(s, category=category, project_id=int(project_id), ym=ym, remark=remark)
    tip = "已清除该格备注" if not text else f"备注已存：{text}"
    return {"ok": True, "message": tip}


# --------------------------------------------------------------- 内部


def _first_project_id() -> int | None:
    with session_scope() as s:
        opts = svc.project_options(s)
    return int(opts[0]["id"]) if opts else None


__all__ = ["router"]
