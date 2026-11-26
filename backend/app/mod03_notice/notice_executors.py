"""MOD-03 的**可注入执行器 ＋ 单行落库**（自 `router.py` 拆出 · 2026-09-19）。

**为什么拆**：`router.py` 涨到 **647 行 > 600** —— `tools/doc_audit.py` 的 `T5` 写着「**禁合入**」。
病根 = **两件事挤在一个文件里**：①「勾选 → 输出」这条链路的三件**可注入依赖**
（抓取执行器 / 批量执行器 / 勾选取数器）＋ 单行落库 `apply_fetched_row`；② 10 条路由本体。
⇒ **本件 = 第①类**（重活），`router.py` 只留**路由与薄组装**。
⚠️ **路由不搬** —— `tools/chain_expected.txt` 的落点钉的就是 `router.py::名字`；搬路由会连带改落点表、
   退化解。

⚠️ 依赖一律经 `Depends` 暴露 —— 测试用 `app.dependency_overrides` 注入桩，
   使「系统内勾选 → 单选/多选端到端」（001-09）可在**不连库、不启浏览器**下断言。
⚠️ `router.py` **再导出**本件四个名字（`apply_fetched_row` / `get_batch_executor` /
   `get_fetch_executor` / `get_notice_lister`）—— 落点表与测试都从那里取
   （⚠️ `inspect.getsource()` 取的是**函数自己的源文件** ⇒ 再导出不影响那条断言），⛔ 别把它们从 `router.py` 删掉。
"""

from __future__ import annotations

from contextlib import ExitStack, closing, contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT, get_settings
from app.core.db import session_scope
from app.core.errors import AppError, MustReportError, human_reason
from app.core.logging import get_logger
from app.core.session import current_name
from app.mod01_projects.domain import (
    OwnershipDecision,
    needs_archive,
    resolve_ownership,
)
from app.mod01_projects import service as P1S
from app.mod02_i8.browser_relay import open_i8_client
from app.mod02_i8.client import I8Client, I8OnlineConflictError
from app.mod02_i8.fetch_receipt import fetch_receipt
from app.mod02_i8.notice_source import NoticeDetailFetcher, NoticeFetcher
from app.mod02_i8.payable_source import fetch_payables
from app.mod03_notice.domain import APPROVE_STATUS_DONE
from app.mod03_notice.classify import DEFAULT_RULES, decide_placement, rows_needing_ownership
from app.mod03_notice.merge import apply_placement_to_new, plan_merge
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.repository import (
    create_run_record,
    fetch_detail,
    finish_run_record,
    lock_fetched_notices,
    # ⚠️⚠️ 2026-09-20 补：`_exec` 里用了它，但**拆件时漏了 import** ⇒
    #    `NameError: name 'get_notices_by_ids' is not defined` ⇒ 每次点「批量打印 / 只导出 PDF」
    #    都炸（表现为 HTTP 500；加兜底后才在界面上看到真因）。**这条链路从 09-19 拆件起就是坏的。**
    #    ⚠️ 测试抓不到它：测试全用 `dependency_overrides` 注入**假执行器** ⇒ 真实现**从不被调用**
    #    ⇒ 已补一条「拆件漏 import」守卫（`tests/test_wiring_guards.py::test_模块里没有未定义的名字`）。
    get_notices_by_ids,
    list_notices,
    list_stat_traces,
    notice_as_dict,
    upsert_notice,
)
from app.mod03_notice.rules_repository import effective_rules
from app.mod03_notice.schemas import FetchJobStage, FetchResponse
from app.mod03_notice.service import MODE_PRINT, BatchResult, run_batch
from app.mod03_notice.print.design import DesignFetcher
from app.mod03_notice.print.dispatch import lock_a4_channel
from app.mod03_notice.print.render import PdfRenderer
from app.mod03_notice.print.signatures import SignatureStore

logger = get_logger()


class _PrintDetails(NoticeDetailFetcher):
    def fetch_info(self, ph_id: str) -> dict:
        info = super().fetch_info(ph_id)
        if not info:
            raise MustReportError("i8 未返回通知书单头。")
        return info


def load_batch_notices(ids: tuple[int, ...]) -> list[PaymentNotice]:
    with session_scope() as session:
        found = {notice.id: notice for notice in get_notices_by_ids(session, list(ids))}
    return [found.get(notice_id) or PaymentNotice(id=notice_id, bill_no="单据不存在") for notice_id in ids]


@contextmanager
def batch_resources(owner: str):
    """Keep the client, reads and Playwright renderer in the caller's thread and i8 scope."""
    with ExitStack() as stack:
        client = stack.enter_context(closing(open_i8_client(owner=owner)))
        renderer = None

        def render(html: str) -> bytes:
            nonlocal renderer
            if renderer is None:
                renderer = stack.enter_context(closing(PdfRenderer()))
            return renderer.render_html_to_pdf(html)

        yield {
            "design_fetcher": DesignFetcher(client),
            "detail_fetcher": _PrintDetails(client),
            "signature_store": SignatureStore(client),
            "render_pdf": render,
        }


def get_batch_executor() -> Callable[[list[int], str], BatchResult]:
    """Synchronous compatibility entry point. The route owns the unified session."""
    def execute(ids: list[int], mode: str) -> BatchResult:
        started = datetime.now()
        notices = load_batch_notices(tuple(ids))
        with batch_resources(current_name()) as resources:
            result = run_batch(
                notices, mode=mode, **resources,
                lock_channel=lock_a4_channel if mode == MODE_PRINT else None,
            )
        persist_batch_run(result, started)
        return result

    return execute


def persist_batch_run(result: BatchResult, started: datetime) -> None:
    _persist_run(
        run_type="print" if result.mode == MODE_PRINT else "export_pdf",
        target=",".join(item.bill_no for item in result.outcomes)[:512],
        result=result, started=started,
    )


@dataclass(frozen=True)
class FetchedNoticeWrite:
    notice: PaymentNotice
    created: bool
    changed: bool
    newly_approved: bool = False


@dataclass(frozen=True)
class SavedNoticeBatch:
    result: FetchResponse
    match_ids: list[int]


FetchProgress = Callable[[Session, FetchJobStage, FetchResponse], None]


def apply_fetched_row(session, row: dict, *, existing: PaymentNotice | None,
                      ownership_id: int | None, rules) -> FetchedNoticeWrite:
    """落一条通知书，保留原归属和人工字段，记录审批状态是否转为已批。"""
    if existing is None:
        placement = decide_placement(row, rules=rules if rules is not None else DEFAULT_RULES)
        notice = upsert_notice(session, **apply_placement_to_new(placement, row, ownership_id=ownership_id))
        return FetchedNoticeWrite(notice, created=True, changed=True)

    was_approved = existing.approve_status == APPROVE_STATUS_DONE
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
    return FetchedNoticeWrite(
        existing, created=False, changed=plan.changed,
        newly_approved=not was_approved and existing.approve_status == APPROVE_STATUS_DONE,
    )


def get_fetch_executor() -> Callable[[str, bool], FetchResponse]:
    """Synchronous compatibility entry point. The route owns the unified session."""
    def execute(year_month: str, _legacy_allow_kick: bool) -> FetchResponse:
        with closing(open_i8_client(owner=current_name())) as client:
            return run_notice_fetch(year_month, client)

    return execute


def _fetch_and_save(year_month: str, client: I8Client, progress: FetchProgress | None) -> SavedNoticeBatch:
    t0 = datetime.now()
    try:
        rows = NoticeFetcher(client).fetch_month(year_month)
    except I8OnlineConflictError:
        raise
    except Exception as exc:
        with session_scope() as session:
            rec = create_run_record(session, run_type="fetch", target=year_month, total=0, started_at=t0)
            finish_run_record(
                session, rec, status="failed", success=0, fail=0, detail=fetch_detail(),
                error_message=exc.message if isinstance(exc, AppError) else human_reason("付款通知书抓取失败", exc),
            )
        raise

    if progress is not None:
        with session_scope() as session:
            progress(session, "saving_notices", FetchResponse(year_month=year_month, fetched=len(rows), upserted=0))

    # 同一份规则用于归属筛选和写入。规则剔除行无需先确定归属。
    with session_scope() as session:
        rules = effective_rules(session)
    need_own = rows_needing_ownership(rows, rules)   # `[(原序号, 行)]` —— 剔除行已被排除

    def _judge() -> list[tuple[int, dict, OwnershipDecision]]:
        """对 `need_own` 跑一遍归属判定（**每次都读最新档案** —— 建档后要重判）。"""
        with session_scope() as session:
            projects = P1S.all_projects(session)
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

    # 补建档沿用本次会话，建档成功后再按最新档案判断归属。
    if needs_archive([d for _, _, d in judged]):
        from app.mod01_projects.sync_service import sync_and_archive          # noqa: PLC0415
        from app.mod02_i8.router import get_common_project_rows, get_warehouse_rows  # noqa: PLC0415

        cp_loader = get_common_project_rows()
        wh_loader = get_warehouse_rows()
        online_conflict = None

        def load_for_archive(loader):
            nonlocal online_conflict
            try:
                return loader(False, client)
            except I8OnlineConflictError as exc:
                online_conflict = exc
                raise

        with session_scope() as session:
            archive_out = sync_and_archive(
                session,
                load_common=lambda: load_for_archive(cp_loader),
                load_warehouses=lambda: load_for_archive(wh_loader),
            )
            if online_conflict is not None:
                raise online_conflict
        if not archive_out.get("degraded"):
            judged = _judge()

    ignored_indices = {i for i, _, d in judged if not d.settled}
    ignored = [
        {
            "project_name": str(r.get("project_name") or ""),
            "doc_name": str((r.get("fields") or {}).get("BillName") or ""),
            "bill_no": str(r.get("bill_no") or ""),
            "kind": d.kind,
            "shell_id": d.shell_id,
            "reason": d.reason,
        }
        for _, r, d in judged if not d.settled
    ]
    accepted = [(i, row) for i, row in enumerate(rows) if i not in ignored_indices]

    # 行序号 → 有效行归属；剔除行写入后尝试非阻断回填，不参与整批校验。
    ownership_of: dict[int, int | None] = {i: d.target_id for i, _, d in judged}

    with session_scope() as session:
        saved_rows = _save_fetched_rows(session, accepted, ownership_of, rules)
        rec = create_run_record(session, run_type="fetch", target=year_month, total=len(rows), started_at=t0)
        finish_run_record(
            session, rec, status="partial" if ignored else "success",
            success=saved_rows.saved, fail=len(ignored),
            detail=fetch_detail(created=saved_rows.created, updated=saved_rows.updated, total=len(rows),
                                excluded=saved_rows.excluded, ownership_filled=saved_rows.ownership_filled,
                                reason="ownership_unsettled" if ignored else "", unresolved=ignored),
            error_message=f"已忽略 {len(ignored)} 条归属未确定的单据，本月数据尚未导齐" if ignored else "",
        )
        result = FetchResponse(
            year_month=year_month, fetched=len(rows), upserted=saved_rows.created + saved_rows.updated,
            notices_saved=True, saved=saved_rows.saved, created=saved_rows.created, updated=saved_rows.updated,
            ignored=ignored, ignored_count=len(ignored), unresolved=len(ignored), excluded=saved_rows.excluded,
            receipt=fetch_receipt(rec),
        )
        if progress is not None:
            progress(session, "matching_jc", result)
    return SavedNoticeBatch(result, saved_rows.match_ids)


@dataclass(frozen=True)
class NoticesWritten:
    saved: int
    created: int
    updated: int
    excluded: int
    ownership_filled: int
    match_ids: list[int]


def _save_fetched_rows(session: Session, rows: list[tuple[int, dict]], ownership_of: dict[int, int | None],
                       rules) -> NoticesWritten:
    from app.mod03_notice.notice_actions import refill_ownership

    existing = lock_fetched_notices(session, list({row["ph_id"] for _, row in rows}))
    created_ids, updated_ids, newly_approved_ids = set(), set(), set()
    touched = {}
    for index, row in rows:
        ph_id = row["ph_id"]
        write = apply_fetched_row(
            session, row, existing=existing.get(ph_id), ownership_id=ownership_of.get(index), rules=rules,
        )
        nid = write.notice.id
        existing[ph_id] = touched[nid] = write.notice
        if write.created:
            created_ids.add(nid)
        elif write.changed:
            updated_ids.add(nid)
        if write.newly_approved:
            newly_approved_ids.add(nid)

    excluded = [n for n in touched.values() if n.excluded]
    refill = refill_ownership(session, [n.id for n in excluded if n.ownership_id is None])
    match_ids = sorted(nid for nid in created_ids | newly_approved_ids if touched[nid].category == "jc")
    return NoticesWritten(len(touched), len(created_ids), len(updated_ids - created_ids),
                          len(excluded), len(refill.filled), match_ids)


def run_notice_fetch(year_month: str, client: I8Client, *, progress: FetchProgress | None = None) -> FetchResponse:
    from app.mod11_jc import service as jc

    saved = _fetch_and_save(year_month, client, progress)
    result = saved.result
    payables = None
    try:
        if saved.match_ids:
            with session_scope() as session:
                initial = jc.auto_link_plan(session, saved.match_ids)
            if any(row.outcome.rule_code == "payable_required" for row in initial):
                try:
                    payables = fetch_payables(client)
                except Exception as exc:
                    message = exc.message if isinstance(exc, AppError) else human_reason("读取采购应付失败", exc)
                    result = result.model_copy(update={"payable_source_failed": True, "payable_source_error": message})
        return _match_saved_notices(saved.match_ids, result, payables, progress)
    except Exception as exc:
        message = exc.message if isinstance(exc, AppError) else human_reason("自动关联集采合同失败", exc)
        result = result.model_copy(update={"matching_error": message})
        if progress is not None:
            with session_scope() as session:
                progress(session, "failed", result)
        return result


def _match_saved_notices(
    ids: list[int], result: FetchResponse, payables: list[dict] | None, progress: FetchProgress | None,
) -> FetchResponse:
    from app.mod11_jc import service as jc

    with session_scope() as session:
        matches = jc.auto_link_plan(session, ids, payables,
                                    payable_source_failed=result.payable_source_failed, for_update=True)
        review = [row.as_row() for row in matches if row.outcome.bucket == "needs_review"]
        ready = [row for row in matches if row.outcome.target is not None]
        selections = [
            jc.LinkSelection(row.notice_id, row.outcome.target.contract_id, row.expected_amount,
                             row.expected_jc_supplier, row.expected_warehouse_key, row.outcome.target.supplier_name)
            for row in ready
        ]
        linked = []
        applied = jc.act_auto_link(session, selections)
        for row, write in zip(ready, applied["rows"], strict=True):
            detail = row.as_row()
            if write["contract_id"] is not None:
                linked.append(detail)
            else:
                review.append(detail | {
                    "bucket": "needs_review", "rule_code": "local_facts_changed", "reason": write["reason"],
                    "candidates": [detail["target"] | {"selectable": False}], "target": None,
                })
        completed = result.model_copy(update={
            "auto_linked_items": linked, "auto_linked": len(linked),
            "manual_review_items": review, "manual_review": len(review),
        })
        if progress is not None:
            progress(session, "completed", completed)
    return completed


def get_notice_lister() -> Callable[..., list[PaymentNotice]]:
    """⚠️ 仍在用（`tests/test_acc_pay_print.py` 直接拿它做"系统内勾选"端到端）⇒ **别随路由一起删** ✓。

    2026-09-19 实测教训：删路由时我按 **URL 文本**搜了一遍"没人引用"就动手 ✗，漏了**按符号**被 import 的这条
    ⇒ 被 `test_acc_pay_print.py` 当场抓住。⇒ **删任何公开符号前，两种搜法都要用：URL/字符串 ＋ 符号名。（本仓的
    `grep` 只覆盖文本 ⇒ 符号引用得另搜一次。）**
    """

    def _list(bill_type: str | None = None, limit: int = 200) -> list[PaymentNotice]:
        with session_scope() as session:
            return list(list_notices(session, bill_type=bill_type, limit=limit))

    return _list


def _persist_run(*, run_type: str, target: str, result: BatchResult,
                 started: datetime | None = None) -> None:
    """落一条执行记录。

    ⚠️⚠️ `started` = 本次动作**开始前**的时刻（调用方取）——
       本函数是**做完才被调**的 ⇒ 不传 ⇒ `started_at` 与 `finished_at` 同刻、**耗时恒 0**
       （用户 2026-09-20 实测「耗时一直是 0 秒」的根因，详见 `mod02_i8.repository.create_run_record`）。
    """
    detail = {
        "items": [
            {
                "notice_id": o.notice_id,
                "bill_no": o.bill_no,
                "ok": o.ok,
                "unverified": o.unverified,
                "reason": o.reason,
                "pdf_path": o.pdf_path,
                **o.receipt_fields(),
            }
            for o in result.outcomes
        ]
    }
    status = "partial" if result.unknown else (
        "success" if not result.failed else ("partial" if result.success else "failed")
    )
    messages = []
    if result.failed:
        messages.append("未产出单号：" + "、".join(result.unprinted_bill_nos))
    if result.unknown:
        messages.append("结果待核实：" + "、".join(item.bill_no for item in result.unknown))
    error_message = "；".join(messages)
    with session_scope() as session:
        rec = create_run_record(session, run_type=run_type, target=target, total=result.total,
                                started_at=started)
        finish_run_record(
            session,
            rec,
            status=status,
            success=len(result.success),
            fail=len(result.failed),
            detail=detail,
            error_message=error_message,
        )
