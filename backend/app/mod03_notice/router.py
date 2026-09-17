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
from app.core.errors import MustReportError
from app.core.logging import get_logger
from app.mod01_projects.domain import (
    OwnershipDecision,
    ensure_batch_settled,
    needs_archive,
    resolve_ownership,
)
from app.mod01_projects.repository import all_projects
from app.mod02_i8.client import I8Client
from app.mod02_i8.notice_source import NoticeDetailFetcher, NoticeFetcher  # 取数归 MOD-02（2026-09-15 归位）
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.classify import decide_placement, rows_needing_ownership
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


def apply_fetched_row(session, row: dict, *,
                      ownership_id: int | None = None) -> tuple[bool, bool]:
    """把一条抓取记录落库 —— 返回 `(是否新行, 是否有改动)`。

    - **新行**：跑剔除判定（§4.2.2）与分类（§4.2.3）后落库，**并带上归属**（§2.5.1 链路 C）；
    - **已有行**：按**再次导入合并**（§4.2.7）—— 源字段跟随 i8、统计两金额按留痕、
      **分类 / 剔除 / 撤单 / 归属一律不被覆盖**（见 `merge.PROTECTED`）。

    ⚠️ `ownership_id` **只对新行生效**（已有行的归属由人指定过，不被再次导入冲掉）；
       它由调用方在**整批校验通过后**传入 —— 见 `get_fetch_executor`。
    """
    existing = get_notice_by_ph_id(session, row["ph_id"])
    if existing is None:
        placement = decide_placement(row)
        upsert_notice(session, **apply_placement_to_new(placement, row,
                                                        ownership_id=ownership_id))
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

        # ⭐⭐ **落库前整批校验归属**（§2.7.4 · §2.5.1 链路 C · `ACC-PRJ-OWN-001`）：
        #     **归属未走完 ⇒ 整批不入库**（一行都不落），并**显式留痕 + 报出**。
        #     ⚠️ 这一步**必须在写库之前** —— 否则库里就会躺着「待指定 / 未建档」的行，
        #        那正是本条口径要杜绝的，也正是"事后还得给旧单据补归属"那套补救逻辑的根源。
        #     ⚠️ 判定输入只有两样：**项目全名**（i8 的 `PhidPc_EXName`）＋ **单据名**（`fields.BillName`）
        #        —— 全名撞上壳 ⇒ 再看单据名命中了壳下哪个小微的关键词。
        # ⭐ **（`TAIL-29`-①）先剔掉「规则剔除行」，再校验归属** ——
        #    §4.2.2「指定项目不在统计范围」的行**与本域无关、天生没有归属**；
        #    让它们参与「整批校验」会把**整批误拦**。实测：2026-09 的 61 行里，
        #    「集团公司第四分公司机关工程」×2 行就把 61 行**全拦下** ⇒ 该月一条都进不来。
        #    ⛔ **判定必须用同一份规则源**（`classify.is_excluded` → `match_exclude_rule` → `DEFAULT_RULES`）
        #       —— **不许在编排层另写一份剔除判定**（「同一件事被实现两遍」是本项目反复踩的坑）。
        #    ⇒ 剔除行**照旧落库**（落库时 `decide_placement` 会给它打 `exclude_source=rule`），
        #      只是**不参与归属校验**、`ownership_id=None`。
        need_own = rows_needing_ownership(rows)          # `[(原序号, 行)]` —— 剔除行已被排除
        n_excluded = len(rows) - len(need_own)

        def _judge() -> list[tuple[int, dict, OwnershipDecision]]:
            """对 `need_own` 跑一遍归属判定（**每次都读最新档案** —— 建档后要重判）。"""
            with session_scope() as session:
                projects = all_projects(session)
                return [
                    (
                        i,
                        row,
                        resolve_ownership(
                            name_full=str(row.get("project_name") or ""),
                            doc_name=str((row.get("fields") or {}).get("BillName") or ""),
                            projects=projects,
                        ),
                    )
                    for i, row in need_own
                ]

        judged = _judge()

        # ⭐ **（`TAIL-29`-③）付款侧「自动建档」**（§2.5.1 链路 A）—— 有 `not_archived` 就**就地建档**：
        #    用**同一个 i8 会话**取「常用项目列表（`API-06`，`phid` 权威）＋ 仓库名单（`API-05`）」，
        #    再走 `sync_and_archive`（链路 A 的完整实现：`plan_archive` 计划 → **幂等落库**）。
        #    ⇒ 建完**重新判定**一次（新档案立刻生效，免得"抓到了却建不了"）。
        #    ⚠️ 代码落点早就写好且有判据（`ACC-PRJ-SYNC-001`）—— 之前从没被这条链路调用，
        #       正是「**判据绿 ≠ 链路对**」的标本（`TAIL-29`-③）。
        #    ⚠️ **只建「能自动定的」**：普通项目带真实仓库名；**壳下的具体小微仍需关键词**
        #       ⇒ 那部分留给链路 C 弹窗（`TAIL-29`-②），本步**不猜**。
        #    ⚠️ 失败**不改本地档案**（`sync_and_archive` 内部保证：取数抛错 ⇒ `plan=None` 一行不写）。
        if needs_archive([d for _, _, d in judged]):
            from app.mod01_projects.sync_service import sync_and_archive          # noqa: PLC0415
            from app.mod02_i8.router import get_common_project_rows, get_warehouse_rows  # noqa: PLC0415

            cp_loader = get_common_project_rows()
            wh_loader = get_warehouse_rows()
            with session_scope() as session:
                archive_out = sync_and_archive(
                    session,
                    load_common=lambda: cp_loader(allow_kick, client),      # ⭐ 复用**同一个**会话
                    load_warehouses=lambda: wh_loader(allow_kick, client),
                )
            if not archive_out.get("degraded"):
                judged = _judge()

        try:
            ensure_batch_settled([d for _, _, d in judged])
        except MustReportError as exc:
            # ⚠️ 报错**必须说清是哪几行** —— 只报数量等于没报：用户正是要据此去
            #    「建档 / 补小微关键词」，不给名字他就无从下手（§2.5.1 链路 C 的出路）。
            unsettled = [(r, d) for _, r, d in judged if not d.settled]
            detail = "；".join(
                f"{r.get('project_name') or '(项目名为空)'}（{d.kind}）" for r, d in unsettled[:10]
            )
            more = f"…等共 {len(unsettled)} 行" if len(unsettled) > 10 else ""
            message = f"{exc}｜未走完的项目：{detail}{more}"
            with session_scope() as session:          # 另开一个 session 记失败（与上面抓取失败同款）
                rec = create_run_record(session, run_type="fetch", target=year_month,
                                        total=len(rows))
                finish_run_record(
                    session, rec, status="failed", success=0, fail=len(rows),
                    detail={"reason": "ownership_unsettled",
                            "unsettled": len(unsettled),
                            "excluded": n_excluded,
                            "projects": [str(r.get("project_name") or "") for r, _ in unsettled]},
                    error_message=message,
                )
            raise MustReportError(message) from exc

        # 行序号 → 归属（**剔除行恒为 None**）；按**原顺序**落库，不打乱行序语义
        ownership_of: dict[int, int | None] = {i: d.target_id for i, _, d in judged}

        with session_scope() as session:
            rec = create_run_record(session, run_type="fetch", target=year_month, total=len(rows))
            created = updated = 0
            for i, row in enumerate(rows):
                is_new, changed = apply_fetched_row(session, row,
                                                    ownership_id=ownership_of.get(i))
                if is_new:
                    created += 1
                elif changed:
                    updated += 1
            upserted = created + updated
            finish_run_record(
                session, rec, status="success", success=upserted, fail=0,
                detail={"created": created, "updated": updated, "total": len(rows),
                        "excluded": n_excluded},
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
