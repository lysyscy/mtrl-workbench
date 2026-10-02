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

from datetime import datetime
from typing import Callable

from app.core.config import get_settings
from app.core.db import session_scope
# ⚠️⚠️ 2026-09-20 补：`get_fetch_executor` 里 `ensure_batch_settled(...)` 抛的就是它，
#    而拆件时**同样漏了 import** ⇒ 抓取遇到"归属未结清"时不是给中文原因、而是
#    `NameError: name 'MustReportError' is not defined`（**把一句能指路的话，换成一句废话**）。
#    ⇒ 与 `get_notices_by_ids` 是同一次拆件留下的同一种病（见 `repository` 那段 import 的注释）。
from app.core.errors import MustReportError
from app.core.logging import get_logger
from app.mod01_projects.domain import (
    OwnershipDecision,
    ensure_batch_settled,
    needs_archive,
    resolve_ownership,
)
from app.mod01_projects import service as P1S
from app.mod02_i8.client import I8Client
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
from app.mod03_notice.service import MODE_PRINT, BatchResult, run_batch
from app.mod03_notice.print.design import DesignFetcher
from app.mod03_notice.print.dispatch import dispatch_pdf as print_dispatch, list_printers
from app.mod03_notice.print.render import PdfRenderer
from app.mod03_notice.print.signatures import SignatureStore

logger = get_logger()


def get_batch_executor() -> Callable[[list[int], str], BatchResult]:
    """批量执行器：真实实现（连库 + i8 + 浏览器 + 打印机）。测试可覆盖。"""

    def _exec(ids: list[int], mode: str) -> BatchResult:
        # ⚠️ 耗时的**起点**：必须在`I8Client` / 浏览器起来**之前**（见 `create_run_record` 那段
        #    —— 记录是"做完才建"的 ⇒ 不显式给起点，耗时恒 0，用户 2026-09-20 实测报的）。
        t0 = datetime.now()
        with session_scope() as session:
            notices = list(get_notices_by_ids(session, ids))
        target = ",".join((n.bill_no or str(n.id)) for n in notices)[:512]
        run_type = "print" if mode == MODE_PRINT else "export_pdf"

        # ⭐ 2026-09-18 **用户口述授权**：「打印你设置的不能强踢？不要设置这个，**强踢就强踢**，
        #    我打印的时候会看着的，不会受损失」⇒ 打印这条链路**允许强踢**（`allow_kick=True`）。
        #    ⚠️ `D9` 的原意是"**不许悄悄踢**"（要有人在场、要显式授权）—— 打印**本来就是人工点击、
        #    人就在机器旁** ⇒ 这里就是那次显式授权；⛔ 抓取那条链路仍按各自入参（默认不踢）。
        client = I8Client(allow_kick=True)
        # ⚠️⚠️ `PdfRenderer()` **必须在 `try` 之内**（2026-09-20 修）：它要起 Playwright 浏览器，
        #    起不来时会**抛**。原先它写在 `try` **之外** ⇒ 它抛 ⇒ `finally` 里的 `client.close()`
        #    **不会执行** ⇒ **i8 会话就那样挂在那儿**（连接泄漏；且下一次还会撞同一个会话）。
        #    ⇒ 用 `renderer=None` 打底 + `finally` 里判空关闭。
        renderer = None
        try:
            renderer = PdfRenderer()
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
                # ⭐ 2026-09-18（`TAIL-46`-②）：投递走**通道分流**（`auto` = IPP → 系统驱动 → RAW 9100；
                #    设置里选的通道**当场生效** —— 分流器每次都现读设置）。⛔ 这里不再是裸 `send_pdf`。
                dispatch_pdf=(print_dispatch if mode == MODE_PRINT else None),
            )
        finally:
            # ⚠️ 判空：`PdfRenderer()` 自己抛时它还是 `None`（见上）—— ⛔ 别在这里 NPE，
            #    那会把**真因**（浏览器起不来）盖成"AttributeError: NoneType"（更难查）。
            if renderer is not None:
                renderer.close()
            client.close()

        _persist_run(run_type=run_type, target=target, result=result, started=t0)
        return result

    return _exec


def apply_fetched_row(session, row: dict, *,
                      ownership_id: int | None = None,
                      rules=None) -> tuple[bool, bool]:
    """把一条抓取记录落库 —— 返回 `(是否新行, 是否有改动)`。

    - **新行**：跑剔除判定（§4.2.2）与分类（§4.2.3）后落库，**并带上归属**（§2.5.1 链路 C）；
    - **已有行**：按**再次导入合并**（§4.2.7）—— 源字段跟随 i8、统计两金额按留痕、
      **分类 / 剔除 / 撤单 / 归属一律不被覆盖**（见 `merge.PROTECTED`）。

    ⚠️ `ownership_id` **只对新行生效**（已有行的归属由人指定过，不被再次导入冲掉）；
       它由调用方在**整批校验通过后**传入 —— 见 `get_fetch_executor`。
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


def get_fetch_executor() -> Callable[[str, bool], tuple[int, int]]:
    """抓取执行器（D4 最小取数）。测试可覆盖。"""

    def _exec(year_month: str, allow_kick: bool) -> tuple[int, int]:
        # ⚠️ 耗时的**起点**：必须在 `I8Client` 登录 i8 **之前**（见 `create_run_record` 那段）
        t0 = datetime.now()
        client = I8Client(allow_kick=allow_kick)
        try:
            rows = NoticeFetcher(client).fetch_month(year_month)
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
                                        total=len(rows), started_at=t0)
                finish_run_record(
                    session, rec, status="failed", success=0, fail=len(rows),
                    detail=fetch_detail(
                        reason="ownership_unsettled",
                        unsettled=len(unsettled),
                        excluded=n_excluded,
                        projects=[str(r.get("project_name") or "") for r, _ in unsettled],
                        # ⭐ **结构化「未命中清单」**（`TAIL-29`-② 弹窗的**唯一数据源**）：
                        #    只记「判定与显示需要的字段」—— ⛔ **不暂存整批数据**
                        #    （用户裁定 `B`：补完关键词**再抓一次**，那时自动命中并落库）。
                        unresolved=[
                            {
                                "project_name": str(r.get("project_name") or ""),
                                "doc_name": str((r.get("fields") or {}).get("BillName") or ""),
                                "bill_no": str(r.get("bill_no") or ""),
                                "kind": d.kind,
                                "shell_id": d.shell_id,
                            }
                            for r, d in unsettled
                        ]),
                    error_message=message,
                )
            raise MustReportError(message) from exc

        # 行序号 → 归属（**剔除行恒为 None**）；按**原顺序**落库，不打乱行序语义
        ownership_of: dict[int, int | None] = {i: d.target_id for i, _, d in judged}

        with session_scope() as session:
            rec = create_run_record(session, run_type="fetch", target=year_month, total=len(rows),
                                    started_at=t0)
            created = updated = 0
            for i, row in enumerate(rows):
                is_new, changed = apply_fetched_row(session, row,
                                                    ownership_id=ownership_of.get(i),
                                                    rules=rules)
                if is_new:
                    created += 1
                elif changed:
                    updated += 1
            upserted = created + updated
            finish_run_record(
                session, rec, status="success", success=upserted, fail=0,
                # ⭐ **成功也要写标记**（`TAIL-41` 的关键一条）：它就是"最近一次"—— 没有 `reason`
                #    ⇒ 读侧据此判定"本次已走完 ⇒ 没有未命中清单"（⛔ 不再回溯更早那条）。
                detail=fetch_detail(created=created, updated=updated, total=len(rows),
                                    excluded=n_excluded),
            )
        return len(rows), upserted

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
                "reason": o.reason,
                "pdf_path": o.pdf_path,
            }
            for o in result.outcomes
        ]
    }
    status = "success" if not result.failed else ("failed" if not result.success else "partial")
    error_message = "" if not result.failed else "未产出单号：" + "、".join(result.unprinted_bill_nos)
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
