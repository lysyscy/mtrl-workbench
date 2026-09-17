"""`MOD-04` 路由 —— **API（JSON）＋ 页面（服务端渲染 · PRG）**。

⚠️ 薄层：判定与形态全在 `domain.py` / `plan_ui.py`；组装在 `service.py`；页面在 `view.py`。
⚠️ 取数经 `Depends` 暴露 ⇒ 自检可注入桩（**不连库**），与 `MOD-02` 同款。

口径：《说明书》§4.3.3（可手改列 / 单据号仅未匹配行）· §4.3.4（审查与两档归并）· §4.3.6（列表内删除）
      · §4.3.7（生效窗口）。**页面交互与 API 走同一份组装出口**（`service.build_page_data`）。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Callable
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod01_projects.models import Project
from app.mod03_notice.page import SORT_NONE
from app.mod04_plan import repository as repo
from app.mod04_plan import service as svc
from app.mod04_plan.domain import (
    BUCKET_ALL,
    R_MATCHED,
    NoticeAmounts,
    ProjectBrief,
    audit_rows,
    cancel_force,
    force_through,
)
from app.mod04_plan.importer import attach_projects, parse_workbook, render_import_page
from app.mod04_plan.plan_manual import (
    assert_manual_editable,
    is_manual_row,
    manual_row_payload,
)
from app.mod04_plan.plan_ui import (
    delete_impact,
    delete_rows,
    inline_edit,
    inline_editable_columns,
    re_match,
)
from app.mod04_plan.view import render_delete_confirm, render_m04

router = APIRouter(tags=["mod04"])


def get_db() -> Iterator[Session]:
    """导入动作的会话（经 `Depends` 暴露 ⇒ 自检可注入假会话）。"""
    with session_scope() as session:
        yield session


DBSession = Depends(get_db)


# --------------------------------------------------------------- 依赖（可注入）

PageData = Callable[..., dict]


def get_page_data() -> PageData:
    """默认实现 = 连库组装；自检覆盖此依赖即可**不连库**。"""

    def _load(**kw) -> dict:
        with session_scope() as s:
            return svc.build_page_data(s, **kw)

    return _load


def _filters(year_month: str, project: list[str], review: str) -> dict:
    return {
        "year_month": year_month,
        "project_ids": tuple(project or ()),
        "audit_bucket": review or BUCKET_ALL,
    }


# --------------------------------------------------------------- API（JSON）


@router.get("/api/m04/plans")
def api_list(
    year_month: str = Query("", description="YYYY-MM / YYYY-MM~YYYY-MM / YYYY / 空=全部"),
    project: list[str] = Query(default=[], description="项目归并键（仓库名），可多选"),
    review: str = Query(BUCKET_ALL, description="全部 / 完全匹配 / 未匹配（**两档归并**）"),
    sort: str = Query("", description="排序列 key"),
    dir: int = Query(SORT_NONE, description="0 原序 / 1 升 / -1 降"),
    load: PageData = Depends(get_page_data),
) -> dict:
    """付款计划列表（筛选 / 排序 / 合计 / 6 种判定计数）。"""
    return load(**_filters(year_month, project, review), sort_col=sort, sort_dir=dir)


@router.get("/api/m04/delete-impact")
def api_delete_impact(
    ids: str = Query(..., description="逗号分隔的计划行 id"),
    year_month: str = Query(""), project: list[str] = Query(default=[]), review: str = Query(BUCKET_ALL),
    load: PageData = Depends(get_page_data),
) -> dict:
    """**删除前的影响范围**（§4.3.6：行号 / 所属年月 / 审查结果）—— 确认前先看这个。"""
    data = load(**_filters(year_month, project, review))
    targets = _parse_ids(ids)
    impacts = delete_impact(data["rows"], targets, {r["id"]: r["audit_result"] for r in data["rows"]})
    return {
        "count": len(impacts),
        "affected_tables": ["plan_row"],
        "impacts": [
            {"row_id": i.row_id, "seq": i.seq, "year_month": i.year_month, "result": i.result}
            for i in impacts
        ],
    }


@router.post("/api/m04/plans/{row_id}/cell")
def api_edit_cell(
    row_id: int,
    column: str = Query(..., description="pay_date / pay_method / remark / doc_no"),
    value: str = Query(""),
    load: PageData = Depends(get_page_data),
) -> dict:
    """行内改列（§4.3.3）：**立刻落库、不被导入覆盖、不留痕**；单据号只对「未匹配」行开放。"""
    with session_scope() as s:
        row = repo.get_row(s, row_id)
        if row is None:
            raise MustReportError(f"计划行 {row_id} 不存在")
        notices = svc.notice_amounts(s)
        result = _audit_one(row, notices)
        edit = inline_edit(
            row_id=row_id, column=column, value=value, allowed=inline_editable_columns(result)
        )
        repo.set_cell(s, row, edit.column, edit.value)
    return {
        "row_id": edit.row_id, "column": edit.column, "value": edit.value,
        "persisted": edit.persisted, "trace": edit.trace,
    }


@router.post("/api/m04/plans/delete")
def api_delete(
    ids: str = Query(..., description="逗号分隔的计划行 id"),
    confirmed: bool = Query(False, description="**必须显式确认**（先看 delete-impact）"),
    load: PageData = Depends(get_page_data),
) -> dict:
    """删除（§4.3.6）：**必须先列影响范围并确认**；只删该行；**只影响付款计划表**。"""
    targets = _parse_ids(ids)
    data = load(year_month="", project_ids=(), audit_bucket=BUCKET_ALL)
    results = {r["id"]: r["audit_result"] for r in data["rows"]}
    impacts = delete_impact(data["rows"], targets, results)
    kept, picked = delete_rows(data["rows"], targets, set(targets), confirmed=confirmed)
    with session_scope() as s:
        deleted = repo.delete_by_ids(s, targets)
    return {
        "deleted": deleted,
        "impacts": [{"seq": i.seq, "year_month": i.year_month, "result": i.result} for i in impacts],
        "affected_tables": ["plan_row"],
        "remaining": len(kept),
        "picked_after": sorted(picked),
    }


@router.post("/api/m04/plans/{row_id}/re-match")
def api_re_match(
    row_id: int,
    load: PageData = Depends(get_page_data),
) -> dict:
    """「再次匹配」（§4.3.3）：按**当前单据号**重跑**同一个审查引擎**。"""
    with session_scope() as s:
        row = repo.get_row(s, row_id)
        if row is None:
            raise MustReportError(f"计划行 {row_id} 不存在")
        notices = svc.notice_amounts(s)
        r = re_match(_row_dict(row), notices)
    return {"row_id": r.notice_id, "doc_no": r.doc_no, "result": r.result, "matched": r.result == R_MATCHED}


@router.post("/api/m04/plans/{row_id}/force")
def api_force_through(
    row_id: int,
    remark: str = Query("", description="**必填** —— 说明为什么放行（§4.3.4 留痕）"),
) -> dict:
    """**强制通过**（§4.3.4 · `ACC-PLAN-AUDIT-001`-09）—— 系统**只提示、不拦截**；放行**必须写备注**。

    ⚠️ 空备注**直接拒绝**（判定走 `domain.force_through`，本层不另写一套）。
    ⚠️ 语义与原型 `PL` 页一致：放行 ⇒ 行上「已强制通过」＋ 备注；**再次导入不冲掉**（`KEEP_ON_REIMPORT`）。
    """
    payload = force_through(remark)          # 空备注 ⇒ MustReportError（§4.3.4）
    with session_scope() as s:
        row = repo.get_row(s, row_id)
        if row is None:
            raise MustReportError(f"计划行 {row_id} 不存在")
        repo.set_force(s, row, forced=True, remark=payload["forced_remark"])
    return {"row_id": row_id, **payload}


@router.post("/api/m04/plans/{row_id}/force-cancel")
def api_cancel_force(row_id: int) -> dict:
    """**取消强制通过**（§4.3.4）—— 回到原判定且备注清空；**取消不留痕**（撤回一次人工放行，不产生新事实）。"""
    payload = cancel_force()
    with session_scope() as s:
        row = repo.get_row(s, row_id)
        if row is None:
            raise MustReportError(f"计划行 {row_id} 不存在")
        repo.set_force(s, row, forced=False)
    return {"row_id": row_id, **payload}


# --------------------------------------------------------------- 页面（服务端渲染 · PRG）


def get_row_loader() -> Callable[..., object]:
    """按 id 取一条计划行（**惰性**：只有真的要开草稿时才查库）。测试可覆盖此依赖。"""

    def _get(row_id: int):
        with session_scope() as s:
            return repo.get_row(s, row_id)

    return _get


@router.get("/m04", response_class=HTMLResponse)
def page_m04(
    year_month: str | None = Query(None, description="YYYY-MM / YYYY-MM~YYYY-MM / YYYY / **空=全部**"),
    project: list[str] = Query(default=[]),
    review: str = Query(BUCKET_ALL),
    sort: str = Query(""),
    dir: int = Query(SORT_NONE),
    draft: str = Query("", description="new = 新增草稿行；<id> = 编辑该**手动**行"),
    msg: str = Query(""),
    msgkind: str = Query("ok"),
    load: PageData = Depends(get_page_data),
) -> HTMLResponse:
    """付款计划页（五段骨架由 `page.render_list_page` 统一装配，**本页不手写骨架**）。

    ⚠️ **「未传参」与「显式传空」语义不同**（否则用户没法选「全部月份」）：
       · **未传** `year_month`（首次进页）⇒ 用**默认值**（付款侧 = 当月，§9.2）；
       · **显式传空**（`?year_month=`，即清空输入框后提交）⇒ **全部月份**（与控件取值语法一致）。

    ⚠️ `draft` 是**令牌**（`new` / 行号），解析在 `service.build_page_data` 内完成 ——
       这样"离线自检注入假会话"能覆盖到草稿行这条路径（不另设一个只在真库下工作的依赖）。
    """
    if year_month is None:
        year_month = svc.default_filters()["year_month"]
    data = load(**_filters(year_month, project, review), sort_col=sort, sort_dir=dir, draft=draft)
    return HTMLResponse(render_m04(data, message=msg, message_kind=msgkind))


# --------------------------------------------------------------- 手动行（§4.3 ＋ 用户 2026-09-16）


@router.post("/m04/row/draft")
def act_row_draft(
    new: str = Form(""),
    row_id: str = Form(""),
    year_month: str = Query(""), project: list[str] = Query(default=[]),
    review: str = Query(BUCKET_ALL), sort: str = Query(""), dir: int = Query(SORT_NONE),
) -> RedirectResponse:
    """开草稿行（**表内增行**，不弹窗）：`new=1` 新增 / `row_id=<id>` 原地编辑该手动行。"""
    token = str(row_id or "").strip() or ("new" if str(new or "").strip() else "")
    if not token:
        return _back(year_month, project, review, sort, dir, "没有指定要新增还是编辑", kind="err")
    return _back(
        year_month, project, review, sort, dir,
        "已就绪：填完点「保存」（手动行不被导入清理，但一样参与 6 种审查判定）", kind="wn",
        draft=token,
    )


@router.post("/m04/row/cancel")
def act_row_cancel(
    year_month: str = Query(""), project: list[str] = Query(default=[]),
    review: str = Query(BUCKET_ALL), sort: str = Query(""), dir: int = Query(SORT_NONE),
) -> RedirectResponse:
    """取消草稿行 —— **不留任何数据**（每步可中断，§9.5）。"""
    return _back(year_month, project, review, sort, dir, "已取消草稿行（未写入任何数据）", kind="wn")


@router.post("/m04/row/save")
def act_row_save(
    row_id: str = Form(""),
    year_month: str = Form(""),
    project_id: str = Form(""),
    doc_no: str = Form(""),
    flow_amount: str = Form(""),
    planned_amount: str = Form(""),
    pay_date: str = Form(""),
    pay_method: str = Form(""),
    remark: str = Form(""),
    q_year_month: str = Query("", alias="year_month"),
    project: list[str] = Query(default=[]),
    review: str = Query(BUCKET_ALL), sort: str = Query(""), dir: int = Query(SORT_NONE),
    session: Session = DBSession,
) -> RedirectResponse:
    """保存手动计划行（**新增与编辑共用同一套**）—— 判定走 `plan_manual.manual_row_payload`。

    ⚠️ Query 里的 `year_month` 与表单里的同名：**表单的是"这一行归哪个月"，Query 的是"筛选项"**
       ⇒ 表单字段用 `year_month`、筛选回跳用别名 `q_year_month`（同名字段不许混）。
    """
    try:
        payload = manual_row_payload(
            year_month=year_month, project_id=project_id, doc_no=doc_no,
            flow_amount=flow_amount, planned_amount=planned_amount,
            pay_date=pay_date, pay_method=pay_method, remark=remark,
        )
        values = dict(payload.values)
        if values.get("project_id") is not None:
            values["project_input"] = _project_label(session, values["project_id"])

        if str(row_id or "").strip().isdigit():
            row = repo.get_row(session, int(row_id))
            if row is None:
                raise MustReportError(f"要保存的计划行 {row_id} 不存在")
            assert_manual_editable(row)
            touched = repo.update_manual_row(session, row, values)
            msg = f"已保存手动行 {row.id}（改动 {len(touched)} 个字段：{'、'.join(touched) or '无'}）"
        else:
            row = repo.create_manual_row(session, values)
            msg = f"已新增 1 行手动付款计划（行号 {row.id}）"
        msg += "；" + "；".join(payload.notes)
        return _back(q_year_month, project, review, sort, dir, msg)
    except MustReportError as exc:
        # 校验不过 ⇒ **保留草稿行**让用户改（不清空已填内容）
        keep = str(row_id or "").strip() or "new"
        return _back(q_year_month, project, review, sort, dir, exc.message, kind="err", draft=keep)


def _project_label(session: Session, project_id: int) -> str:
    """项目 id → **填报值**（记展示名；拿不到则用仓库名）—— 与导入的「项目」列同一含义。"""
    for p in session.execute(select(Project)).scalars().all():
        if p.id == int(project_id):
            return p.disp or p.warehouse_name or p.name_full or ""
    return ""


@router.get("/m04/delete", response_class=HTMLResponse)
def page_delete_confirm(
    ids: str = Query(...),
    year_month: str = Query(""), project: list[str] = Query(default=[]),
    review: str = Query(BUCKET_ALL), sort: str = Query(""), dir: int = Query(SORT_NONE),
    load: PageData = Depends(get_page_data),
) -> HTMLResponse:
    """删除确认页：**先列影响范围**（§4.3.6）。"""
    data = load(**_filters(year_month, project, review), sort_col=sort, sort_dir=dir)
    targets = _parse_ids(ids)
    impacts = delete_impact(data["rows"], targets, {r["id"]: r["audit_result"] for r in data["rows"]})
    query = urlencode(
        {"year_month": year_month, "project": list(project or ()), "review": review,
         "sort": sort, "dir": int(dir), "ids": ids},
        doseq=True,
    )
    return HTMLResponse(render_delete_confirm(data, impacts, query))


@router.post("/m04/cell")
def act_cell(
    row_id: int = Form(...), column: str = Form(...), value: str = Form(""),
    year_month: str = Form(""), project: list[str] = Form(default=[]), review: str = Form(BUCKET_ALL),
    sort: str = Form(""), dir: int = Form(SORT_NONE),
    load: PageData = Depends(get_page_data),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """提交一格（立刻落库）→ 303 回原查询（PRG）。

    ⚠️ **参数一律 `Form`**：本端点的输入来自 `<form method="post">` 的 **body**（`_cell_form` 的
       hidden inputs）。此前声明为 `Query` ⇒ 表单提交**永远 422**（真机实测：`POST /m04/cell` = 422，
       而同样形态的 `/m04/row/draft` 用 `Form` = 303 正常）。**离线断言看不见**（它直接调函数）。
    """
    try:
        row = repo.get_row(db, row_id)
        if row is None:
            raise MustReportError(f"计划行 {row_id} 不存在")
        result = _audit_one(row, svc.notice_amounts(db))
        edit = inline_edit(
            row_id=row_id, column=column, value=value, allowed=inline_editable_columns(result)
        )
        repo.set_cell(db, row, edit.column, edit.value)
        db.commit()   # ⚠️ **PRG 必须在响应之前提交**（否则回跳的 GET 可能读到旧值）
        msg = f"{row_id} 的「{edit.column}」已保存为「{edit.value or '（空）'}」（立刻落库、不留痕）"
        if edit.column == "doc_no":
            msg += " —— 点该行「再次匹配」重新比对 i8 通知书"
        return _back(year_month, project, review, sort, dir, msg)
    except MustReportError as exc:
        return _back(year_month, project, review, sort, dir, exc.message, kind="err")


@router.post("/m04/delete")
def act_delete(
    ids: str = Form(...),
    year_month: str = Form(""), project: list[str] = Form(default=[]), review: str = Form(BUCKET_ALL),
    sort: str = Form(""), dir: int = Form(SORT_NONE),
    load: PageData = Depends(get_page_data),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """确认后执行删除（**只影响付款计划表**）→ 303 回原查询。

    ⚠️ **参数一律 `Form`**（同上：确认页 `render_delete_confirm` 的 `ids` 是 hidden input）。
    """
    targets = _parse_ids(ids)
    n = repo.delete_by_ids(db, targets)
    db.commit()   # ⚠️ **PRG 必须在响应之前提交**（否则回跳的 GET 可能读到旧值）
    return _back(year_month, project, review, sort, dir, f"已删除 {n} 行付款计划（只影响付款计划表）", kind="wn")


@router.post("/m04/re-match")
def act_re_match(
    row_id: int = Form(...),
    year_month: str = Form(""), project: list[str] = Form(default=[]), review: str = Form(BUCKET_ALL),
    sort: str = Form(""), dir: int = Form(SORT_NONE),
    load: PageData = Depends(get_page_data),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """再次匹配 → 303 回原查询并回报新的审查结果。

    ⚠️ **参数一律 `Form`**（同上：`row_id` 是行内表单的 hidden input）。
    """
    row = repo.get_row(db, row_id)
    if row is None:
        return _back(year_month, project, review, sort, dir, f"计划行 {row_id} 不存在", kind="err")
    r = re_match(_row_dict(row), svc.notice_amounts(db))
    extra = "（该行转入「无需处理」）" if r.result == R_MATCHED else ""
    return _back(
        year_month, project, review, sort, dir,
        f"{row_id} 已按单据号「{r.doc_no or '（空）'}」重新比对 → 审查结果：{r.result}{extra}",
    )


# --------------------------------------------------------------- 强制通过（§4.3.4 · PRG）
#
# ⚠️ **本组是「过渡形态」**：服务端渲染层按 D18 将被原型壳替换 ⇒ 接壳时按原型 `PL` 页的
#    **弹窗**（`强制通过 · <审查结果>` ＋ 备注必填 ＋ 取消不留痕）重做，但**语义已在此固化**：
#    **只提示不拦截 · 放行必须写备注（留痕）· 取消不留痕**。


@router.post("/m04/force")
def act_force(
    row_id: int = Form(...),
    remark: str = Form(""),
    year_month: str = Form(""), project: list[str] = Form(default=[]), review: str = Form(BUCKET_ALL),
    sort: str = Form(""), dir: int = Form(SORT_NONE),
    load: PageData = Depends(get_page_data),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """**强制通过**（§4.3.4）→ 303 回原查询。**空备注 ⇒ 不落库**（显式报错回执）。

    ⚠️ 判定走 `domain.force_through`（**唯一出口**），本层只落库 ＋ 回执。
    ⚠️ 会话走 `Depends(get_db)`（不用 `session_scope()`）⇒ 离线断言可注入假会话。
    """
    try:
        payload = force_through(remark)
    except MustReportError as exc:
        return _back(year_month, project, review, sort, dir, str(exc), kind="err")
    row = repo.get_row(db, row_id)
    if row is None:
        return _back(year_month, project, review, sort, dir, f"计划行 {row_id} 不存在", kind="err")
    repo.set_force(db, row, forced=True, remark=payload["forced_remark"])
    db.commit()      # ⚠️ **PRG 必须在响应之前提交** —— 否则 303 回跳的 GET 可能读到旧值
    return _back(
        year_month, project, review, sort, dir,
        f"计划行 {row_id} 已强制通过并留痕（备注：{payload['forced_remark']}）",
    )


@router.post("/m04/force-cancel")
def act_force_cancel(
    row_id: int = Form(...),
    year_month: str = Form(""), project: list[str] = Form(default=[]), review: str = Form(BUCKET_ALL),
    sort: str = Form(""), dir: int = Form(SORT_NONE),
    load: PageData = Depends(get_page_data),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """**取消强制通过** → 303 回原查询。回到原判定且备注清空；**取消不留痕**（§4.3.4）。"""
    payload = cancel_force()
    row = repo.get_row(db, row_id)
    if row is None:
        return _back(year_month, project, review, sort, dir, f"计划行 {row_id} 不存在", kind="err")
    repo.set_force(db, row, forced=False)
    db.commit()      # ⚠️ 同上：**先提交再回跳**（本轮真机端到端实测：不提交则回跳读到旧值）
    return _back(
        year_month, project, review, sort, dir,
        f"计划行 {row_id} 已取消强制通过 —— 回到原判定、备注清空（取消不留痕）",
    )


# --------------------------------------------------------------- 导入（§4.3.3 · §9.5）


def _project_briefs(session: Session) -> list[ProjectBrief]:
    """档案行 → 匹配用视图（**只带匹配所需的三个字段**）。"""
    from sqlalchemy import select

    return [
        ProjectBrief(
            id=p.id, disp=p.disp or "", warehouse_name=p.warehouse_name, name_full=p.name_full or ""
        )
        for p in session.execute(select(Project)).scalars().all()
    ]


@router.get("/m04/import", response_class=HTMLResponse)
def page_import(msg: str = Query(""), msgkind: str = Query("ok")) -> HTMLResponse:
    """导入页（先选月份 ＋ 选文件）。"""
    return HTMLResponse(
        render_import_page(
            message=msg, message_kind=msgkind,
            default_ym=str(svc.default_filters().get("year_month") or ""),
        )
    )


@router.post("/m04/import")
async def act_import(
    year_month: str = Form(""),
    file: UploadFile = File(...),
    session: Session = DBSession,
) -> RedirectResponse:
    """**导入付款计划**（§4.3.3）：按所选月份「**清该月自动行 → 重写该批**」（§9.5 幂等）。

    ⚠️ **不做判重拦截** —— 同月同单据号两行是 §4.3.4 的「重复上报」，导入照收、审查暴露。
    """
    try:
        data = await file.read()
        parsed = parse_workbook(data)
        rows = attach_projects(parsed.rows, _project_briefs(session))
        result = repo.merge_month(session, year_month=year_month, rows=rows)
    except MustReportError as exc:
        return RedirectResponse(
            f"/m04/import?{urlencode({'msg': exc.message, 'msgkind': 'err'})}", status_code=303
        )

    msg = (
        f"已导入 {len(rows)} 行到 {year_month}：新建 {result['created']} · 复用更新 {result['updated']}"
        f" · 删除该月残影 {result['deleted']}"
        f"（可手改列一律保留；该月手动行 {result['manual_kept']} 行未被触碰）"
    )
    if parsed.alerts:
        msg += "；提示：" + "；".join(parsed.alerts[:3])
    q = urlencode({"year_month": year_month, "msg": msg, "msgkind": "wn"})
    return RedirectResponse(f"/m04?{q}", status_code=303)


# --------------------------------------------------------------- 内部


def _parse_ids(ids: str) -> list[int]:
    try:
        return [int(x) for x in str(ids or "").replace(" ", "").split(",") if x]
    except ValueError as exc:
        raise MustReportError(f"计划行 id 非法：{ids!r}") from exc


def _row_dict(row) -> dict:
    return {
        "id": row.id, "year_month": row.year_month, "doc_no": row.doc_no,
        "flow_amount": row.flow_amount, "planned_amount": row.planned_amount,
    }


def _audit_one(row, notices: dict[str, NoticeAmounts]) -> str:
    """单行判定（**复用审查引擎**，不另写）。"""
    return audit_rows([_row_dict(row)], notices)[0]


def _back(year_month, project, review, sort, dir, msg: str, *, kind: str = "ok",
          draft: str = "") -> RedirectResponse:
    """303 回原查询（PRG）—— 防止刷新重放提交。"""
    q = {
        "year_month": year_month, "project": list(project or ()), "review": review,
        "sort": sort, "dir": int(dir), "msg": msg, "msgkind": kind,
    }
    if draft:
        q["draft"] = draft
    return RedirectResponse(f"/m04?{urlencode(q, doseq=True)}", status_code=303)


__all__ = ["router"]
