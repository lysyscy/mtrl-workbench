"""`MOD-04` 路由 —— **只服务 JSON API**（旧页面/PRG 半边已于 2026-09-18 随 `§19` 批 2 删除）。

⚠️ 薄层：判定与形态全在 `domain.py` / `plan_ui.py`；组装在 `service.py`。
⚠️ 取数经 `Depends` 暴露 ⇒ 自检可注入桩（**不连库**），与 `MOD-02` 同款。

口径：《说明书》§4.3.3（可手改列 / 单据号仅未匹配行）· §4.3.4（审查与两档归并）· §4.3.6（列表内删除）
      · §4.3.7（生效窗口）。**新壳与 API 走同一份组装出口**（`service.build_page_data`）。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Callable

from fastapi import APIRouter, Depends, Query
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
    audit_rows,
    cancel_force,
    force_through,
)
from app.mod04_plan.plan_api_router import router as plan_api_router
from app.mod04_plan.plan_ui import (
    delete_impact,
    delete_rows,
    inline_edit,
    inline_editable_columns,
    re_match,
)
# ⚠️ 2026-09-18（`§19` 批 2）：页面/PRG 半边删除后**清掉**的 import（⛔ 别再加回来）——
#    `File`/`Form`/`UploadFile`（表单）· `HTMLResponse`/`RedirectResponse`（页面与 PRG）·
#    `urlencode`（PRG 回跳）· `select`（唯一用处是页面取数）· `date`（页面日期控件）·
#    `importer`（`parse_workbook`/`attach_projects` 只剩页面在调）· `plan_manual`（手动行的页面表单）·
#    `project_views`（页面展示件）· `view`（渲染件整体已删）· `ProjectBrief`（只页面用）。
#    ⚠️ **必须留着**（⛔ 别当页面件删）：`Callable`（`PageData = Callable[..., dict]`，**API 依赖的类型别名** ——
#    我第一版按"只给页面用"删了它，结果整套测试 collection error）· `get_db`（`tests/test_plan_import.py`·
#    `test_plan_manual.py` 覆盖的依赖）· `session_scope`（JSON API 的会话口，`test_api_m04_force.py` 也 patch 它）·
#    `SORT_NONE`（`api_list` 的 `dir` 默认值）· `Session`/`Iterator`（`get_db` 签名）。

router = APIRouter(tags=["mod04"])
# ⭐ 前端壳的 **JSON API**（`TAIL-35`：手动行 ＋ 导入）—— 独立路由件，由本文件汇总
router.include_router(plan_api_router)


def get_db() -> Iterator[Session]:
    """写动作的会话（经 `Depends` 暴露 ⇒ 自检可注入假会话）。

    ⚠️ 2026-09-18（`§19` 批 2）：原先另有 `DBSession = Depends(get_db)` 这个别名，只给**页面**用
       ⇒ 已随页面删除；`get_db` 本身**留着**（`tests/test_plan_import.py`·`test_plan_manual.py` 在覆盖它）。
    """
    with session_scope() as session:
        yield session




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


# ⚠️ 2026-09-18（`TAIL-27` · `§19` **批 2**）：**本模块的页面/PRG 半边已整体删除**（授权 `D18`）——
#    `page_m04` / `act_row_*` / `page_delete_confirm` / `act_cell` / `act_delete` / `act_re_match` /
#    `act_force` / `act_force_cancel` / `page_import` / `act_import` ＋ `get_row_loader` ＋ `_back`。
#    ⇒ 本文件此后**只服务 JSON API**（新壳 `m04` 在用）。
# ⚠️ 留存的内部件（⛔ 别当页面件顺手删）：`get_page_data`（**7 个 API 路由的依赖**）、`_parse_ids`、
#    `_row_dict`、`_audit_one`（API 复用）；`plan_ui`/`plan_manual`/`project_views` 是**业务纯函数**；
#    `importer.parse_workbook`/`attach_projects` 是**业务**（`render_import_page` 已随页删）。
# ⚠️ 判据点**没跟着删** —— 按 `§19` 铁律搬了断言：
#    `ACC-PLAN-AUDIT-001/001-09` → `tests/test_api_m04_force.py`（先搬、后删，2026-09-18）；
#    `ACC-PLAN-MANUAL-001/001-05`·`001-07` → `tests/test_api_m04_manual.py`；
#    `001-06`（手动行徽标）与「失败保留已填内容」→ `tests/test_wired_m04.py`（壳侧）。






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


__all__ = ["router"]
