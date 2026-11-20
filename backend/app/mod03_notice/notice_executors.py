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
from datetime import datetime
from typing import Callable

from app.core.config import PROJECT_ROOT, get_settings
from app.core.db import session_scope
from app.core.errors import MustReportError
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
from app.mod02_i8.notice_source import NoticeDetailFetcher, NoticeFetcher  # 取数归 MOD-02
from app.mod03_notice.classify import DEFAULT_RULES, decide_placement, rows_needing_ownership
from app.mod03_notice.merge import apply_placement_to_new, plan_merge
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.repository import (
    create_run_record,
    fetch_detail,
    finish_run_record,
    get_notice_by_ph_id,
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
from app.mod03_notice.schemas import FetchResponse
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
    return [found.get(notice_id) or PaymentNotice(id=notice_id, bill_no=str(notice_id)) for notice_id in ids]


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


def apply_fetched_row(session, row: dict, *,
                      ownership_id: int | None = None,
                      rules=None) -> tuple[bool, bool]:
    """把一条抓取记录落库 —— 返回 `(是否新行, 是否有改动)`。

    - **新行**：跑剔除判定（§4.2.2）与分类（§4.2.3）后落库，**并带上归属**（§2.5.1 链路 C）；
    - **已有行**：按**再次导入合并**（§4.2.7）—— 源字段跟随 i8、统计两金额按留痕、
      **分类 / 剔除 / 撤单 / 归属一律不被覆盖**（见 `merge.PROTECTED`）。

    ⚠️ `ownership_id` **只对新行生效**（已有行的归属由人指定过，不被再次导入冲掉）；
       它由调用方在该行归属校验通过后传入 —— 见 `get_fetch_executor`。
    ⚠️ `rules` = 本次抓取用的**生效规则集**（`rules_repository.effective_rules` 的唯一出口）；
       由调用方**读一次传进来**（⛔ 不在这里每次现读 —— 同一批要保证判据一致）。
    """
    existing = get_notice_by_ph_id(session, row["ph_id"])
    if existing is None:
        placement = decide_placement(row, rules=rules if rules is not None else DEFAULT_RULES)
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


def get_fetch_executor() -> Callable[[str, bool], FetchResponse]:
    """抓取执行器（D4 最小取数）。测试可覆盖。"""

    def _exec(year_month: str, allow_kick: bool) -> FetchResponse:
        t0 = datetime.now()
        # 路由绑定会话策略。主取数与补建档的两个读取共用同一客户端。
        with closing(open_i8_client(allow_kick=allow_kick, owner=current_name())) as client:
            return _fetch(year_month, allow_kick, client, t0)

    def _fetch(year_month: str, allow_kick: bool, client: I8Client, t0: datetime) -> FetchResponse:
        try:
            rows = NoticeFetcher(client).fetch_month(year_month)
        except I8OnlineConflictError:
            raise
        except Exception as exc:  # noqa: BLE001
            with session_scope() as session:
                rec = create_run_record(session, run_type="fetch", target=year_month, total=0,
                                        started_at=t0)
                # ⚠️ **取数失败也要写标记**（`TAIL-41`）：漏了这条，"最近一次付款通知书抓取"就指不住，
                #    读侧会掉回更早的记录 ⇒ 又变成"抓取之后仍摆着旧清单"。
                finish_run_record(
                    session, rec, status="failed", success=0, fail=0,
                    detail=fetch_detail(), error_message=str(exc),
                )
            raise

        # ACC-PRJ-OWN-001：归属未确定的行本次不写，下次抓取重新判断。
        # 规则剔除行照常保留，不要求归属确定；两处判定使用同一份规则。
        # ⭐ **（`TAIL-40`）规则来源改为「库 → 出厂默认」**：本批**读一次**生效规则集，随后
        #    **同时**喂给「挑需校验的行」与「落库时的剔除判定」—— 一处读取、两处同一份
        #    （⛔ 不许在编排层另写一份剔除判定，也不许两处各读一次）。
        with session_scope() as session:
            rules = effective_rules(session)
        need_own = rows_needing_ownership(rows, rules)   # `[(原序号, 行)]` —— 剔除行已被排除
        n_excluded = len(rows) - len(need_own)

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
            online_conflict = None

            def load_for_archive(loader):
                nonlocal online_conflict
                try:
                    return loader(allow_kick, client)
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
            rec = create_run_record(session, run_type="fetch", target=year_month, total=len(rows),
                                    started_at=t0)
            created = updated = 0
            for i, row in accepted:
                is_new, changed = apply_fetched_row(session, row,
                                                    ownership_id=ownership_of.get(i),
                                                    rules=rules)
                if is_new:
                    created += 1
                elif changed:
                    updated += 1
            upserted = created + updated
            # 剔除不要求归属确定，但能唯一匹配现有档案的也应支持项目筛选。
            # 已有归属保留；缺档案/小微待定留空，不触发建档或阻断导入。
            from sqlalchemy import select
            from app.mod03_notice.notice_actions import refill_ownership
            excluded_ids = list(session.scalars(select(PaymentNotice.id).where(
                PaymentNotice.ph_id.in_([row["ph_id"] for _, row in accepted]),
                PaymentNotice.excluded.is_(True), PaymentNotice.ownership_id.is_(None),
            )))
            refill = refill_ownership(session, excluded_ids)
            finish_run_record(
                session, rec, status="partial" if ignored else "success",
                success=len(accepted), fail=len(ignored),
                detail=fetch_detail(created=created, updated=updated, total=len(rows),
                                    excluded=n_excluded, ownership_filled=len(refill.filled),
                                    reason="ownership_unsettled" if ignored else "",
                                    unresolved=ignored),
                error_message=f"已忽略 {len(ignored)} 条归属未确定的单据，本月数据尚未导齐" if ignored else "",
            )
            return FetchResponse(
                year_month=year_month, fetched=len(rows), upserted=upserted, ignored=ignored,
                receipt=fetch_receipt(rec),
            )

    return _exec


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
