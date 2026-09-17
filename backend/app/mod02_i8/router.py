"""`MOD-02` 路由（抓取任务页：入参换算 / 命中回显 / 手动触发 / 同步 / 执行记录）。

⚠️ 薄层：判定与形态全在 `fetch_task.py`（纯函数），HTTP 与落库在此组装。
⚠️ 依赖经 `Depends` 暴露 ⇒ 测试可注入桩（不连 i8、不连库）。
"""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.db import session_scope
from app.mod02_i8.client import I8Client
from app.mod02_i8.fetch_task import (
    CONFIRM_CLOSES_DIALOG,
    MANUAL_ONLY,
    build_dialog,
    build_fetch_params,
    degrade_to_excel,
    echo_params,
    fetch_record_payload,
)
from app.mod02_i8.models import RunRecord
from app.mod02_i8.notice_source import NoticeFetcher
from app.mod02_i8.repository import create_run_record, finish_run_record
from app.mod02_i8.schemas import (
    FetchPlanOut,
    FetchPreviewOut,
    FetchPreviewRequest,
    FetchRunOut,
    FetchRunRequest,
    RunRecordOut,
    SyncOut,
)
from app.mod02_i8.sources import CommonProjectSource, WarehouseSource

router = APIRouter(prefix="/api/m02", tags=["mod02"])


# --------------------------------------------------------------- 依赖（可注入）


def get_notice_rows() -> Callable[[str, bool], list[dict]]:
    """付款通知书取数（`API-01`）。测试可覆盖。"""

    def _fetch(year_month: str, allow_kick: bool) -> list[dict]:
        client = I8Client(allow_kick=allow_kick)
        try:
            return NoticeFetcher(client).fetch_month(year_month)
        finally:
            client.close()

    return _fetch


def get_warehouse_rows() -> Callable[..., list[dict]]:
    """仓库名单取数（`API-05`）。`allow_kick` 默认 `False`（**D9：强踢必须显式授权**）。

    ⭐ 传入 `client` ⇒ **复用该会话**（不新建、不关闭）：让「抓一次」只登录一次
       （抓取链路要顺带取名单来建档，见 `TAIL-29`-③；⛔ 否则一次抓取会登录 3 次 = 顶号 3 次）。
    """

    def _fetch(allow_kick: bool = False, client: I8Client | None = None) -> list[dict]:
        own = client is None
        c = client if client is not None else I8Client(allow_kick=allow_kick)
        try:
            return WarehouseSource(c).fetch()
        finally:
            if own:
                c.close()

    return _fetch


def get_common_project_rows() -> Callable[..., list[dict]]:
    """常用项目列表取数（`API-06`）。`allow_kick` 默认 `False`（**D9**）。

    ⭐ 同 `get_warehouse_rows`：可传 `client` **复用会话**。
    """

    def _fetch(allow_kick: bool = False, client: I8Client | None = None) -> list[dict]:
        own = client is None
        c = client if client is not None else I8Client(allow_kick=allow_kick)
        try:
            return CommonProjectSource(c).fetch()
        finally:
            if own:
                c.close()

    return _fetch


# --------------------------------------------------------------- 路由


@router.get("/fetch/plan", response_model=FetchPlanOut)
def fetch_plan(year_month: str = Query(..., description="核算年月，形如 2026-08")) -> FetchPlanOut:
    """核算年月 → 单据日期起止（闭区间）＋ 回显；**只允许「月」**（001-01 / 001-02）。"""
    from app.core.period import period_capabilities

    params = build_fetch_params(year_month)
    return FetchPlanOut(
        year_month=params["year_month"],
        start_date=params["start_date"],
        end_date=params["end_date"],
        echo=echo_params(params),
        capabilities=list(period_capabilities("fetch")),
        manual_only=MANUAL_ONLY,
        confirm_closes_dialog=CONFIRM_CLOSES_DIALOG,
    )


@router.post("/fetch/preview", response_model=FetchPreviewOut)
def fetch_preview(
    req: FetchPreviewRequest,
    rows_loader: Callable[[str, bool], list[dict]] = Depends(get_notice_rows),
) -> FetchPreviewOut:
    """抓取前核对：该月**命中条数**（有效 / 剔除分列）+ 换算回显（001-03 / 001-04）。

    ⚠️ 接口不可用 ⇒ **降级**并显式说明（001-06），不得静默。
    """
    params = build_fetch_params(req.year_month)
    echo = echo_params(params)
    try:
        rows = rows_loader(req.year_month, req.allow_kick)
    except Exception as exc:  # noqa: BLE001
        info = degrade_to_excel(exc)
        return FetchPreviewOut(
            year_month=req.year_month, echo=echo, degraded=True, message=info["message"]
        )
    dialog = build_dialog(req.year_month, rows)
    return FetchPreviewOut(
        year_month=req.year_month,
        echo=echo,
        total=dialog.preview.total,
        valid=dialog.preview.valid,
        excluded=dialog.preview.excluded,
    )


@router.post("/fetch/run", response_model=FetchRunOut)
def fetch_run(
    req: FetchRunRequest,
    rows_loader: Callable[[str, bool], list[dict]] = Depends(get_notice_rows),
) -> FetchRunOut:
    """**手动触发**抓取（001-05）；每次抓取**留一条执行记录**（001-07）。

    ⚠️ `allow_kick=True` 会强制踢掉该账号其他在线会话 —— 须用户在界面显式确认。
    ⚠️ 失败**不自动重试登录**（D9）；接口不可用 ⇒ **降级为手动 Excel 导入并显式说明**（001-06）。
    """
    target = f"付款通知书 {req.year_month}"
    try:
        rows = rows_loader(req.year_month, req.allow_kick)
    except Exception as exc:  # noqa: BLE001
        info = degrade_to_excel(exc)
        _persist_fetch(
            payload=fetch_record_payload(object_desc=target, success=0, fail=0, error_message=str(exc))
        )
        return FetchRunOut(
            year_month=req.year_month, fetched=0, status="failed", degraded=True, message=info["message"]
        )
    _persist_fetch(payload=fetch_record_payload(object_desc=target, success=len(rows), fail=0))
    return FetchRunOut(year_month=req.year_month, fetched=len(rows), status="success")


@router.post("/sync/warehouses", response_model=SyncOut)
def sync_warehouses(
    allow_kick: bool = Query(False, description="⭐ 须用户在界面二次确认后才为 true（D9：强踢）"),
    rows_loader: Callable[..., list[dict]] = Depends(get_warehouse_rows),
) -> SyncOut:
    """**同步仓库名单**（`API-05`，手动点击）—— 建档推导判据 / 占位行扶正的数据源。

    ⚠️ 仓库名单**本身不落库**（它是「仓库名 ↔ 所属项目全名」的**映射**、不是档案行）——
       它是**建档的输入**；要建档请点「**同步常用项目列表**」（`ACC-PRJ-SYNC-001`）。
    """
    try:
        rows = rows_loader(allow_kick)
    except Exception as exc:  # noqa: BLE001
        _persist_fetch(run_type="sync", payload=fetch_record_payload(
            object_desc="仓库列表", success=0, fail=0, error_message=str(exc)
        ))
        return SyncOut(table="warehouse_list", degraded=True, message=str(exc))
    _persist_fetch(run_type="sync", payload=fetch_record_payload(object_desc="仓库列表", success=len(rows), fail=0))
    return SyncOut(table="warehouse_list", count=len(rows), sample=rows[:5])


@router.post("/sync/common-projects", response_model=SyncOut)
def sync_common_projects(
    allow_kick: bool = Query(False, description="⭐ 须用户在界面二次确认后才为 true（D9：强踢）"),
    rows_loader: Callable[..., list[dict]] = Depends(get_common_project_rows),
    wh_loader: Callable[..., list[dict]] = Depends(get_warehouse_rows),
) -> SyncOut:
    """**同步常用项目列表**（`API-06`，手动点击）—— **`phid` 权威来源**；抓完**按 `phid` 幂等建档**。

    ⭐ 建档规则主人 =《全自动建档-实施计划》**§三 链路 A**（判据 `ACC-PRJ-SYNC-001`）：
    能自动定的自动建（普通项目带真实仓库名 · 小微壳只建壳 · 无仓库落占位行），
    需要人定的**显式列出、不自动建**（多仓库 / 壳下具体小微 / 缺 phid）—— **禁静默**。

    ⚠️ 仓库名单（`API-05`）**与本次同步一起取**（它是"仓库名 ↔ 所属项目全名"的映射，建档要用）。
    ⚠️ `allow_kick=True` 会**踢掉该账号其他在线会话**（D9）⇒ 只能由界面二次确认后传。
    """
    from app.mod01_projects.sync_service import sync_and_archive      # noqa: PLC0415

    with session_scope() as s:
        out = sync_and_archive(
            s,
            load_common=lambda: rows_loader(allow_kick),
            load_warehouses=lambda: wh_loader(allow_kick),
        )
    if out["degraded"]:
        _persist_fetch(run_type="sync", payload=fetch_record_payload(
            object_desc="常用项目列表", success=0, fail=0, error_message=out["message"]
        ))
        return SyncOut(table="common_project", degraded=True, message=out["message"])
    counts = out["counts"]
    _persist_fetch(run_type="sync", payload=fetch_record_payload(
        object_desc="常用项目列表", success=counts["create"], fail=0))
    return SyncOut(
        table="common_project",
        count=counts["create"],
        counts=counts,
        # `sample` 放**待人工 / 缺 phid**（比放新建的行更有用：那是"还要人去做什么"）
        # ⚠️ **不截断** —— 截断会把排在第 2 条以后的待办**静默吞掉**（本轮实测踩到）：
        #    这两类列表本身很小（受项目数上界），全给；口径 = 「显式列出、禁静默」。
        sample=(out["plan"]["manual"] + out["plan"]["no_phid"]),
        message=(f"建档 {counts['create']} 条 · 已在档案 {counts['exists']} 条 · "
                 f"待人工 {counts['manual']} 条 · 缺 phid {counts['no_phid']} 条"),
    )


@router.get("/fetch/records", response_model=list[RunRecordOut])
def fetch_records(limit: int = Query(20, ge=1, le=200)) -> list[RunRecordOut]:
    """最近执行记录（供看板「本月尚未抓取 / 最近一次抓取失败」）。"""
    with session_scope() as s:
        rows = list(
            s.execute(select(RunRecord).order_by(RunRecord.id.desc()).limit(limit)).scalars().all()
        )
        return [
            RunRecordOut(
                id=r.id,
                run_type=r.run_type,
                target=r.target,
                status=r.status,
                success_count=r.success_count,
                fail_count=r.fail_count,
                error_message=r.error_message,
                started_at=r.started_at.isoformat(timespec="seconds"),
                finished_at=r.finished_at.isoformat(timespec="seconds") if r.finished_at else None,
            )
            for r in rows
        ]


# --------------------------------------------------------------- 内部


def _persist_fetch(*, payload: dict, run_type: str | None = None) -> None:
    """写一条执行记录（只写台账，**不参与业务统计**）。"""
    if run_type:
        payload = {**payload, "run_type": run_type}
    with session_scope() as s:
        rec = create_run_record(
            s, run_type=payload["run_type"], target=payload["target"], total=payload["total_count"]
        )
        finish_run_record(
            s,
            rec,
            status=payload["status"],
            success=payload["success_count"],
            fail=payload["fail_count"],
            detail={},
            error_message=payload["error_message"],
        )


__all__ = ["router"]
