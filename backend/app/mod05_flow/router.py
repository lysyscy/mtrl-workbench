"""`MOD-05` 路由 —— **API（JSON）＋ 页面（服务端渲染 · PRG）**。

⚠️ 薄层：判定与形态全在 `domain.py`（纯函数）；组装在 `service.py`；页面在 `view.py`。
⚠️ 取数经 `Depends` 暴露 ⇒ 自检可注入桩（**不连库**），与 `MOD-02` / `MOD-04` 同款。

口径：《说明书》§4.4.2（一次付款一条流水 / 两态）· §4.4.5（撤销必填原因）· §4.5.1（欠款三类）
      · §4.5.2（期初占位行）· §4.5.4（逐月台账）· §4.5.5（付款统计）。
"""

from __future__ import annotations

from typing import Callable
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query
# ⚠️ 2026-09-21：`HTMLResponse` 已无人用（本模块的服务端渲染页全清）⇒ 从 import 里去掉。
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod05_flow import repository as repo
from app.mod05_flow import service as svc
from app.mod05_flow.domain import default_flow_period
# ⭐ 历史付款流水导入（§4.4.6）—— 独立路由件，由本文件汇总（`main.py` 不用改）。
# ⚠️ 2026-09-21（`§19` 四个暂留件收口）：`import_router.py`（三条 PRG）＋ `import_view.py`（服务端渲染页）
#    **已整体删除** —— 能力原样搬成 JSON API `import_api.py`（壳 `V.m05imp` 在用），旧页无独有能力。
from app.mod05_flow.import_api import router as import_api_router
# ⚠️ 2026-09-19（`§19` 批 3）：`app.mod05_flow.view`（四个 `render_m05*`）已随四个旧页整体删除（授权 `D18`）
#    —— ⛔ 别再加回来（共用件已搬进 `import_view.py`，而那个文件 2026-09-21 也已随导入页收口删除 ⇒
#    要加共用件请放 `mod03_notice/page.py` 或本模块的纯函数件）。

router = APIRouter(tags=["mod05"])
router.include_router(import_api_router)

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
    **列** = 页面表头 `FL_THEAD` 去掉「操作」⇒ 9 列；**取值** = **页面显示的那个值**。

    ⚠️ **本端点不用 join 通知书 / 项目** —— `/api/m05/flows` 的 `rows` 里**已经有**：
      · `doc_no`（单据编码，= 通知书的 `bill_no`）
      · `project_display`（付款项目 = **展示名**，由 `service._flow_dict` 走
        `core.projects.project_label` 算好 —— ⛔ 不是仓库名那个"键"、更不是 `project_id`）
      · `status_label`（**已给中文**「生效 / 已撤销」）
      ⇒ ⭐ **取数端本来就够**，本端点只做"按 id 挑 ＋ 换列名 ＋ 拼状态文案"。

    ⚠️ **状态那格**：页面把「撤销原因」**并进状态格里**（`已撤销 ＋ 原因`）⇒
       导出也**并进去**（保持 9 列与页面一致）；⛔ 另开一列会让表与屏幕**对不上号**。
    """
    import base64
    from datetime import date

    from app.report_export import fl_export as X

    data = load()                       # ⭐ 空参 = **全量**（本端点的"筛选"靠传入的 id）
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
        "id": r.get("id"),
        "doc_no": r.get("doc_no") or "",
        "project_display": r.get("project_display") or "",
        "pay_date": r.get("pay_date") or "",
        "amount": r.get("amount"),
        "pay_method": r.get("pay_method") or "",
        "remark": r.get("remark") or "",
        "created_by": r.get("created_by") or "",
        "status_text": _status(r),
    } for r in picked]
    blob = X.build_xlsx(out)
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


# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 3**）：本模块的**四个服务端渲染页已整体删除**（授权 `D18`）——
#    `GET /m05`（付款流水）· `GET /m05/debt`（欠款）· `GET /m05/ledger`（逐月台账）· `GET /m05/stats`
#    （付款统计）＋ PRG `POST /m05/revoke`（壳走 `POST /api/m05/flows/{id}/revoke` ✓）＋ **`view.py`（451 行）**。
#    ⇒ 这四页的读一律走 **JSON API**（`/api/m05/flows` · `/debt` · `/ledger` · `/stats`，壳在用 ✓）；
#    ⛔ 别再往本文件加页面路由（`D18` 的口径：新页面 = 新壳 + API）。
# ⚠️ **两个例外（⛔ 不许删）**：「历史付款导入」—— ⭐ **2026-09-21 已搬进新壳**（`import_api.py` ＋
#    壳 `V.m05imp`）⇒ 服务端渲染页与三条 PRG 已删 ✓；**三个 PRG**
#    （`POST /m05/opening` · `/m05/opening/delete` · `/m05/ledger/remark`）**新壳正在用**（另有真机 `_e2e_m05_wired.py`）。





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

    from app.report_export import service as EX

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
def api_export_total_debt():
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
            path, _note = svc.export_total_debt(s)
    except MustReportError as exc:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(exc)})
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
        # ⚠️ 文件名**由后端带出**（⛔ 不让壳自己拼：命名规则两处各写一份，改一处就会静默走形）
        headers={"X-Export-Filename": quote(path.name)},
    )





# --------------------------------------------------------------- 动作（303 回原查询）


@router.post("/m05/opening")
def act_opening(
    category: str = Form(...), project_id: int = Form(...), cutoff_ym: str = Form(""),
    settle_amount: str = Form(""), paid_amount: str = Form(""), remark: str = Form(""),
    end_ym: str = Form(""),
) -> RedirectResponse:
    """录入 / 覆盖**期初占位行**（同一「口径 + 项目 + 截止年月」重复录入 = 覆盖）→ 303 回**台账页**。

    ⚠️ **参数一律 `Form`**（同上：期初表单的输入全在 body）。
    """
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
    opening_id: int = Form(...), project_id: int = Form(0), end_ym: str = Form("")
) -> RedirectResponse:
    """删除期初占位行 → 303 回台账页。⚠️ **参数一律 `Form`**（同上）。"""
    q = {"project_id": project_id, "end_ym": end_ym}
    with session_scope() as s:
        n = repo.delete_opening(s, opening_id)
    return _back(q, f"已删除 {n} 条期初占位行（台账首行随之消失）", kind="wn", path="/m05/ledger")


@router.post("/m05/ledger/remark")
def act_remark(
    category: str = Form(...), project_id: int = Form(...), ym: str = Form(""),
    remark: str = Form(""), end_ym: str = Form(""),
) -> RedirectResponse:
    """写 / 清台账备注（**空串 = 清除该格**；键 = 口径 + 项目 + 月）→ 303 回**台账页**。

    ⚠️ **参数一律 `Form`**（同上）。
    """
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
