"""`MOD-05` 路由 —— **API（JSON）＋ 页面（服务端渲染 · PRG）**。

⚠️ 薄层：判定与形态全在 `domain.py`（纯函数）；组装在 `service.py`；页面在 `view.py`。
⚠️ 取数经 `Depends` 暴露 ⇒ 自检可注入桩（**不连库**），与 `MOD-02` / `MOD-04` 同款。

口径：《说明书》§4.4.2（一次付款一条流水 / 两态）· §4.4.5（撤销必填原因）· §4.5.1（欠款三类）
      · §4.5.2（期初占位行）· §4.5.4（逐月台账）· §4.5.5（付款统计）。
"""

from __future__ import annotations

from typing import Callable
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod05_flow import repository as repo
from app.mod05_flow import service as svc
from app.mod05_flow.domain import default_flow_period
# ⭐ 历史付款流水导入（§4.4.6）—— 独立路由件，由本文件汇总（`main.py` 不用改）
from app.mod05_flow.import_router import router as import_router
from app.mod05_flow.view import (
    render_m05,
    render_m05_debt,
    render_m05_ledger,
    render_m05_stats,
)

router = APIRouter(tags=["mod05"])
router.include_router(import_router)

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
            return svc.build_debt(s, **kw)

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
    year: int = Query(0), quarter: int = Query(0),
    load: PageData = Depends(get_stats_data),
) -> dict:
    """付款统计（左按项目 · 右时间轴；**换粒度不换口径**）。"""
    return load(granularity=granularity, year=year or None, quarter=quarter or None)


@router.post("/api/m05/flows/{flow_id}/revoke")
def api_revoke(
    flow_id: int,
    reason: str = Query(..., description="**必填**（空 ⇒ 语义错误）"),
    changed_by: str = Query(""),
) -> dict:
    """撤销一条流水（§4.4.5）—— 原因交给 `domain.revoke_flow` 把关（**空原因被拒**）。"""
    with session_scope() as s:
        flow = repo.get_flow(s, flow_id)
        if flow is None:
            raise MustReportError(f"流水 {flow_id} 不存在")
        return repo.revoke(s, flow, reason=reason, changed_by=changed_by)


# --------------------------------------------------------------- 页面（PRG）


@router.get("/m05", response_class=HTMLResponse)
def page_flows(
    year_month: str | None = Query(None, description=YM_DOC),
    status: str = Query(""), pay_method: str = Query(""), project_id: str = Query(""),
    keyword: str = Query(""), msg: str = Query(""), msgkind: str = Query("ok"),
    load: PageData = Depends(get_flows_data),
) -> HTMLResponse:
    """付款流水页（**未传年份 = 当月；显式传空 = 全部月份**）。"""
    data = load(
        year_month=_resolve_ym(year_month), status=status or None,
        pay_method=pay_method or None,
        project_id=int(project_id) if str(project_id).strip() else None, keyword=keyword,
    )
    return HTMLResponse(render_m05(data, message=msg, message_kind=msgkind))


@router.get("/m05/debt", response_class=HTMLResponse)
def page_debt(
    msg: str = Query(""), msgkind: str = Query("ok"), load: PageData = Depends(get_debt_data)
) -> HTMLResponse:
    return HTMLResponse(render_m05_debt(load(), message=msg, message_kind=msgkind))


@router.get("/m05/ledger", response_class=HTMLResponse)
def page_ledger(
    project_id: int = Query(0), end_ym: str = Query(""),
    msg: str = Query(""), msgkind: str = Query("ok"),
    load: PageData = Depends(get_ledger_data),
) -> HTMLResponse:
    """台账页：`project_id` 缺省时取**第一个项目**（项目选择器本身在筛选栏）。"""
    if not project_id:
        project_id = _first_project_id() or 0
    if not project_id:
        # 一个项目都没有 ⇒ 骨架照出，只是数据区为空（**不假装有数据**）
        data = {
            "project_id": 0, "project_options": [], "sides": [],
            "shared_project_selector": True, "has_switch_caliber_button": False,
        }
        return HTMLResponse(render_m05_ledger(data, message=msg, message_kind=msgkind))
    return HTMLResponse(
        render_m05_ledger(load(project_id=int(project_id), end_ym=end_ym),
                          message=msg, message_kind=msgkind)
    )


@router.get("/m05/stats", response_class=HTMLResponse)
def page_stats(
    granularity: str = Query(""), year: int = Query(0), quarter: int = Query(0),
    msg: str = Query(""), msgkind: str = Query("ok"),
    load: PageData = Depends(get_stats_data),
) -> HTMLResponse:
    data = load(granularity=granularity, year=year or None, quarter=quarter or None)
    return HTMLResponse(render_m05_stats(data, message=msg, message_kind=msgkind))


# --------------------------------------------------------------- 动作（303 回原查询）


@router.post("/m05/revoke")
def act_revoke(
    flow_id: int = Query(...), reason: str = Query(""),
    year_month: str = Query(""), status: str = Query(""), pay_method: str = Query(""),
    project_id: str = Query(""), keyword: str = Query(""),
) -> RedirectResponse:
    """撤销 → 303 回**流水页**原查询（**空原因被拒绝**，原因原样回报）。"""
    q = {"year_month": year_month, "status": status, "pay_method": pay_method,
         "project_id": project_id, "keyword": keyword}
    try:
        with session_scope() as s:
            flow = repo.get_flow(s, flow_id)
            if flow is None:
                raise MustReportError(f"流水 {flow_id} 不存在")
            out = repo.revoke(s, flow, reason=reason)
        return _back(q, f"流水 {out['flow_id']} 已撤销（原因：{out['reason']}）—— 该笔退出统计", kind="wn")
    except MustReportError as exc:
        return _back(q, exc.message, kind="err")


@router.post("/m05/opening")
def act_opening(
    category: str = Query(...), project_id: int = Query(...), cutoff_ym: str = Query(""),
    settle_amount: str = Query(""), paid_amount: str = Query(""), remark: str = Query(""),
    end_ym: str = Query(""),
) -> RedirectResponse:
    """录入 / 覆盖**期初占位行**（同一「口径 + 项目 + 截止年月」重复录入 = 覆盖）→ 303 回**台账页**。"""
    q = {"project_id": project_id, "end_ym": end_ym}
    try:
        if not str(cutoff_ym).strip():
            raise MustReportError("期初占位行必须填「截止年月」")
        with session_scope() as s:
            repo.upsert_opening(
                s, category=category, project_id=int(project_id), cutoff_ym=str(cutoff_ym).strip(),
                settle_amount=settle_amount or 0, paid_amount=paid_amount or 0, remark=remark,
            )
        return _back(q, f"已录入期初占位行（{category} · 截止 {cutoff_ym}）", path="/m05/ledger")
    except MustReportError as exc:
        return _back(q, exc.message, kind="err", path="/m05/ledger")


@router.post("/m05/opening/delete")
def act_opening_delete(
    opening_id: int = Query(...), project_id: int = Query(0), end_ym: str = Query("")
) -> RedirectResponse:
    q = {"project_id": project_id, "end_ym": end_ym}
    with session_scope() as s:
        n = repo.delete_opening(s, opening_id)
    return _back(q, f"已删除 {n} 条期初占位行（台账首行随之消失）", kind="wn", path="/m05/ledger")


@router.post("/m05/ledger/remark")
def act_remark(
    category: str = Query(...), project_id: int = Query(...), ym: str = Query(""),
    remark: str = Query(""), end_ym: str = Query(""),
) -> RedirectResponse:
    """写 / 清台账备注（**空串 = 清除该格**；键 = 口径 + 项目 + 月）→ 303 回**台账页**。"""
    with session_scope() as s:
        text = repo.set_remark(s, category=category, project_id=int(project_id), ym=ym, remark=remark)
    tip = "已清除该格备注" if not text else f"备注已存：{text}"
    return _back({"project_id": project_id, "end_ym": end_ym}, tip, path="/m05/ledger")


# --------------------------------------------------------------- 内部


def _back(query: dict, msg: str, *, kind: str = "ok", path: str = "/m05") -> RedirectResponse:
    """303 回原查询（PRG）—— 防止刷新重放提交。"""
    data = {k: v for k, v in query.items() if v not in (None, "")}
    data.update({"msg": msg, "msgkind": kind})
    return RedirectResponse(f"{path}?{urlencode(data)}", status_code=303)


def _first_project_id() -> int | None:
    with session_scope() as s:
        opts = svc.project_options(s)
    return int(opts[0]["id"]) if opts else None


__all__ = ["router"]
