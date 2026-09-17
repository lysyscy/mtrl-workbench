"""MOD-03 路由 —— **批量打印 / 仅导出 PDF / 打印机设置 / 抓取**（API）。

⚠️ 薄层：真实依赖（i8 / Playwright / 打印机 / DB）在此组装；
   编排逻辑全在 `service.run_batch`（纯函数，可离线单测）。
⚠️ 依赖一律经 `Depends` 暴露 —— 测试用 `app.dependency_overrides` 注入桩，
   使「系统内勾选 → 单选/多选端到端」（001-09）可在不连库、不启浏览器下断言。

⚠️ **页面与行级动作已拆到 `notice_router.py`**（`/m03/notices` 列表页 · 批量动作 · 草稿行 · 撤销 · 查看关联）——
   本文件只服务「勾选 → 输出」这条链路与设置入口，**别把页面再写回来**（一文件一职责，行数也守得住）。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.logging import get_logger
from app.mod02_i8.client import I8Client
from app.mod02_i8.notice_source import NoticeDetailFetcher, NoticeFetcher  # 取数归 MOD-02（2026-09-15 归位）
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.classify import decide_placement
from app.mod03_notice.merge import apply_placement_to_new, plan_merge
from app.mod03_notice.repository import (
    create_run_record,
    finish_run_record,
    get_notice_by_ph_id,
    get_notices_by_ids,
    list_notices,
    list_stat_traces,
    notice_as_dict,
    upsert_notice,
)
from app.mod03_notice.schemas import (
    BatchRequest,
    BatchResponse,
    FetchRequest,
    FetchResponse,
    ItemOutcomeOut,
    PrinterSettingRequest,
    PrinterSettingResponse,
)
from app.mod03_notice.service import MODE_PRINT, BatchResult, run_batch
from app.mod03_notice.print.design import DesignFetcher
from app.mod03_notice.print.ipp import send_pdf
from app.mod03_notice.print.render import PdfRenderer
from app.mod03_notice.print.signatures import SignatureStore
from app.mod03_notice.settings_store import apply_printer_setting

logger = get_logger()

router = APIRouter(prefix="/api/m03", tags=["mod03"])


# --------------------------------------------------------------- 依赖（可注入）


def get_batch_executor() -> Callable[[list[int], str], BatchResult]:
    """批量执行器：真实实现（连库 + i8 + 浏览器 + 打印机）。测试可覆盖。"""

    def _exec(ids: list[int], mode: str) -> BatchResult:
        with session_scope() as session:
            notices = list(get_notices_by_ids(session, ids))
        target = ",".join((n.bill_no or str(n.id)) for n in notices)[:512]
        run_type = "print" if mode == MODE_PRINT else "export_pdf"

        client = I8Client(allow_kick=False)
        renderer = PdfRenderer()
        try:
            result = run_batch(
                notices,
                mode=mode,
                design_fetcher=DesignFetcher(client),
                # 单张详情的三个来源（主表 / 明细 / 流程=签名）—— 渲染必需，漏传会印出空白件
                detail_fetcher=NoticeDetailFetcher(client),
                # 签名图缓存落 `artifacts/.sigcache`（与 `tools/render_preview.py` 同一处）
                signature_store=SignatureStore(
                    client, cache_dir=get_settings().artifacts_path / ".sigcache"
                ),
                render_pdf=renderer.render_html_to_pdf,
                dispatch_pdf=(send_pdf if mode == MODE_PRINT else None),
            )
        finally:
            renderer.close()
            client.close()

        _persist_run(run_type=run_type, target=target, result=result)
        return result

    return _exec


def apply_fetched_row(session, row: dict) -> tuple[bool, bool]:
    """把一条抓取记录落库 —— 返回 `(是否新行, 是否有改动)`。

    - **新行**：跑剔除判定（§4.2.2）与分类（§4.2.3）后落库；
    - **已有行**：按**再次导入合并**（§4.2.7）—— 源字段跟随 i8、统计两金额按留痕、
      **分类 / 剔除 / 撤单 / 归属一律不被覆盖**（见 `merge.PROTECTED`）。
    """
    existing = get_notice_by_ph_id(session, row["ph_id"])
    if existing is None:
        placement = decide_placement(row)
        upsert_notice(session, **apply_placement_to_new(placement, row))
        return True, True

    plan = plan_merge(
        notice_as_dict(existing), row, list_stat_traces(session, existing.id), notice_id=existing.id
    )
    for key, value in plan.values.items():
        setattr(existing, key, value)
    existing.fetched_at = datetime.now()
    session.flush()
    if plan.alerts:
        logger.warning(
            "再次导入提醒（单 {}）：{}", existing.bill_no or existing.ph_id, "；".join(plan.alerts)
        )
    return False, plan.changed


def get_fetch_executor() -> Callable[[str, bool], tuple[int, int]]:
    """抓取执行器（D4 最小取数）。测试可覆盖。"""

    def _exec(year_month: str, allow_kick: bool) -> tuple[int, int]:
        client = I8Client(allow_kick=allow_kick)
        try:
            rows = NoticeFetcher(client).fetch_month(year_month)
        except Exception as exc:  # noqa: BLE001
            with session_scope() as session:
                rec = create_run_record(session, run_type="fetch", target=year_month, total=0)
                finish_run_record(
                    session, rec, status="failed", success=0, fail=0, detail={}, error_message=str(exc)
                )
            raise
        finally:
            client.close()

        with session_scope() as session:
            rec = create_run_record(session, run_type="fetch", target=year_month, total=len(rows))
            created = updated = 0
            for row in rows:
                is_new, changed = apply_fetched_row(session, row)
                if is_new:
                    created += 1
                elif changed:
                    updated += 1
            upserted = created + updated
            finish_run_record(
                session, rec, status="success", success=upserted, fail=0,
                detail={"created": created, "updated": updated, "total": len(rows)},
            )
        return len(rows), upserted

    return _exec


def get_notice_lister() -> Callable[..., list[PaymentNotice]]:
    def _list(bill_type: str | None = None, limit: int = 200) -> list[PaymentNotice]:
        with session_scope() as session:
            return list(list_notices(session, bill_type=bill_type, limit=limit))

    return _list


# --------------------------------------------------------------- 路由


@router.get("/notices")
def get_notices(
    bill_type: str | None = Query(None, description="按单据类型过滤：mechanical / material"),
    limit: int = Query(200, ge=1, le=1000),
    lister: Callable[..., list[PaymentNotice]] = Depends(get_notice_lister),
) -> list[dict]:
    """m03 页表格数据源（勾选打印的对象）。"""
    return [_row(n) for n in lister(bill_type=bill_type, limit=limit)]


@router.post("/notices/fetch", response_model=FetchResponse)
def fetch_notices(
    req: FetchRequest,
    executor: Callable[[str, bool], tuple[int, int]] = Depends(get_fetch_executor),
) -> FetchResponse:
    """按核算年月抓取（D4 最小取数）。

    ⚠️ 登录含强踢（KillOnlineUser）：`allow_kick=False` 时若检测到在线冲突 ⇒ 直接失败、不踢人。
    ⚠️ 抓取失败**不自动重试登录**（D9）。
    """
    fetched, upserted = executor(req.year_month, req.allow_kick)
    return FetchResponse(year_month=req.year_month, fetched=fetched, upserted=upserted)


@router.post("/batch", response_model=BatchResponse)
def batch(
    req: BatchRequest,
    executor: Callable[[list[int], str], BatchResult] = Depends(get_batch_executor),
) -> BatchResponse:
    """批量打印 / 仅导出 PDF（共用同一次勾选，由 `mode` 分流）。"""
    result = executor(req.ids, req.mode)
    batch_name = Path(result.batch_dir).name if result.batch_dir else ""
    items = [
        ItemOutcomeOut(
            notice_id=o.notice_id,
            bill_no=o.bill_no,
            ok=o.ok,
            reason=o.reason,
            pdf_path=o.pdf_path,
            download_url=(
                f"/api/m03/pdf/{batch_name}/{Path(o.pdf_path).name}" if o.pdf_path and batch_name else ""
            ),
        )
        for o in result.outcomes
    ]
    resp = BatchResponse(
        mode=result.mode,
        total=result.total,
        success=len(result.success),
        failed=len(result.failed),
        unprinted_bill_nos=result.unprinted_bill_nos,
        batch_dir=result.batch_dir,
        items=items,
    )
    # 001-08 / 001-03 / PDF-001-05：批内存在未产出 ⇒ 随响应显式带出（前端必须展示，不得静默）
    if resp.failed:
        logger.warning("批量{} 未产出 {} 张：{}", result.mode, resp.failed, resp.unprinted_bill_nos)
    return resp


@router.get("/pdf/{batch}/{name}")
def download_pdf(batch: str, name: str) -> FileResponse:
    """产物取用入口（PDF-001-04）—— 仅允许取 `artifacts/pdf/` 下的文件（防目录穿越）。"""
    root = get_settings().pdf_export_path.resolve()
    target = (root / batch / name).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="产物不存在")
    return FileResponse(target, media_type="application/pdf", filename=name)


@router.get("/settings/printer", response_model=PrinterSettingResponse)
def get_printer_setting() -> PrinterSettingResponse:
    """打印机地址当前值（设置弹窗回填用）。"""
    return PrinterSettingResponse(printer_ipp_url=get_settings().printer_ipp_url)


@router.put("/settings/printer", response_model=PrinterSettingResponse)
def set_printer_setting(req: PrinterSettingRequest) -> PrinterSettingResponse:
    """修改打印机地址（SETUP-001）：写 `.env` + `cache_clear()` ⇒ 即时生效、无需重启。"""
    value = apply_printer_setting(req.printer_ipp_url)
    return PrinterSettingResponse(printer_ipp_url=value)


# --------------------------------------------------------------- 内部


def _row(n: PaymentNotice) -> dict:
    return {
        "id": n.id,
        "bill_no": n.bill_no,
        "bill_type": n.bill_type,
        "project_name": n.project_name,
        "approve_status": n.approve_status,
        "amount_approved": float(n.amount_approved or 0),
        "amount_paid": float(n.amount_paid or 0),
    }


def _persist_run(*, run_type: str, target: str, result: BatchResult) -> None:
    detail = {
        "items": [
            {
                "notice_id": o.notice_id,
                "bill_no": o.bill_no,
                "ok": o.ok,
                "reason": o.reason,
                "pdf_path": o.pdf_path,
            }
            for o in result.outcomes
        ]
    }
    status = "success" if not result.failed else ("failed" if not result.success else "partial")
    error_message = "" if not result.failed else "未产出单号：" + "、".join(result.unprinted_bill_nos)
    with session_scope() as session:
        rec = create_run_record(session, run_type=run_type, target=target, total=result.total)
        finish_run_record(
            session,
            rec,
            status=status,
            success=len(result.success),
            fail=len(result.failed),
            detail=detail,
            error_message=error_message,
        )


# --------------------------------------------------------------- 页面（服务端渲染）

# ⚠️ 页面 router **不带 `/api/m03` 前缀**（与 MOD-04 一致）—— 页面路径是 `/m03/notices`。
# ⚠️ **已迁到 `notice_router.py`**（列表页 + 行级动作 + 草稿行 + 撤销 + 查看关联），
#    这里再导出一份只是为了 `__all__` 里不出现悬空名（历史调用方兼容）。
from app.mod03_notice.notice_router import page_router  # noqa: E402,F401  ← 兼容再导出

__all__ = ["router", "page_router", "apply_fetched_row"]
