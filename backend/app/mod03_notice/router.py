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
from app.mod01_projects import repository as proj_repo
from app.mod01_projects.domain import (
    OwnershipDecision,
    append_keyword_dedup,
    candidates_of,
    ensure_batch_settled,
    i8_warehouse_lookup,
    needs_archive,
    resolve_ownership,
    validate_keyword_in_doc,
)
from app.mod01_projects.models import TYPE_SMALL
from app.mod01_projects.repository import all_projects
from app.mod02_i8 import wh_cache
from app.mod02_i8.client import I8Client
from app.mod02_i8.notice_source import NoticeDetailFetcher, NoticeFetcher  # 取数归 MOD-02（2026-09-15 归位）
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.classify import DEFAULT_RULES, decide_placement, rows_needing_ownership
from app.mod03_notice.domain import still_unsettled
from app.mod03_notice.rules_repository import effective_rules
from app.mod03_notice.merge import apply_placement_to_new, plan_merge
from app.mod03_notice.repository import (
    create_run_record,
    fetch_detail,
    finish_run_record,
    get_notice_by_ph_id,
    get_notices_by_ids,
    latest_unresolved,
    list_notices,
    list_stat_traces,
    notice_as_dict,
    upsert_notice,
)
from app.mod03_notice.schemas import (
    AssignRequest,
    AssignResponse,
    BatchRequest,
    BatchResponse,
    FetchRequest,
    FetchResponse,
    ItemOutcomeOut,
    PrinterSettingRequest,
    PrinterSettingResponse,
    UnresolvedResponse,
    WarehouseCheckOut,
    WarehouseCheckRequest,
)
from app.mod03_notice.service import MODE_PRINT, BatchResult, run_batch
from app.mod03_notice.print.design import DesignFetcher
from app.mod03_notice.print.dispatch import dispatch_pdf as print_dispatch, list_printers
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

        # ⭐ 2026-09-18 **用户口述授权**：「打印你设置的不能强踢？不要设置这个，**强踢就强踢**，
        #    我打印的时候会看着的，不会受损失」⇒ 打印这条链路**允许强踢**（`allow_kick=True`）。
        #    ⚠️ `D9` 的原意是"**不许悄悄踢**"（要有人在场、要显式授权）—— 打印**本来就是人工点击、
        #    人就在机器旁** ⇒ 这里就是那次显式授权；⛔ 抓取那条链路仍按各自入参（默认不踢）。
        client = I8Client(allow_kick=True)
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
                # ⭐ 2026-09-18（`TAIL-46`-②）：投递走**通道分流**（`auto` = IPP → 系统驱动 → RAW 9100；
                #    设置里选的通道**当场生效** —— 分流器每次都现读设置）。⛔ 这里不再是裸 `send_pdf`。
                dispatch_pdf=(print_dispatch if mode == MODE_PRINT else None),
            )
        finally:
            renderer.close()
            client.close()

        _persist_run(run_type=run_type, target=target, result=result)
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
        client = I8Client(allow_kick=allow_kick)
        try:
            rows = NoticeFetcher(client).fetch_month(year_month)
        except Exception as exc:  # noqa: BLE001
            with session_scope() as session:
                rec = create_run_record(session, run_type="fetch", target=year_month, total=0)
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
            rec = create_run_record(session, run_type="fetch", target=year_month, total=len(rows))
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


# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 4** 遗留①）：**死路由已删** ——
#    `GET /api/m03/notices`（"m03 页表格数据源 / 勾选打印的对象"）＋ 它的取数器 `get_notice_lister()`。
#    它的**唯一消费者是旧静态页 `m03.html`**（2026-09-19 `§19` 批 4.5 已删，授权 `D18`）⇒ 删除前实测：
#    全仓只有 `notice_router.py` 里一句**注释**提到它，壳 / 测试 / `tools/*_expected.txt` **都没有引用** ✓。
#    ⛔ 别再注册"给旧静态页用的取数端点" —— 新页面要么进**新壳**（`web/index.html`），要么走**模块路由的服务端渲染**。


# --------------------------------------------------------------- 路由


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


@router.get("/notices/unresolved", response_model=UnresolvedResponse)
def unresolved_notices() -> UnresolvedResponse:
    """**最近一次付款通知书抓取**的未命中清单 ＋ 该壳下的候选小微（`TAIL-29`-② 弹窗的数据源）。

    ⭐ **弹窗的唯一数据源** —— ⛔ 不暂存整批抓取数据（用户 2026-09-18 裁定 `B`：
       补完关键词**再抓一次**，那时 `resolve_ownership` 会自动命中并落库，库里不留半成品）。
    ⚠️⚠️ **两层"新鲜度"**（`TAIL-41` 修复，2026-09-18）：
       ① **只认最近一次抓取**（`repository.latest_unresolved`）：抓取**成功之后**就不该再有清单；
       ② 清单里每一条还要**按当前档案现算**（`domain.still_unsettled`）—— 用户可能**刚补过词 /
          刚建过小微**，那些行**已经能归属了** ⇒ **当场不再出现**（否则对着已解决的清单白干）。
    """
    with session_scope() as session:
        projects = all_projects(session)
        items = still_unsettled(latest_unresolved(session), projects)
        out = [
            {
                **it,
                "candidates": (
                    candidates_of(int(it["shell_id"]), projects) if it.get("shell_id") else []
                ),
            }
            for it in items
        ]
    return UnresolvedResponse(items=out)


@router.post("/notices/ownership-assign", response_model=AssignResponse)
def assign_ownership(req: AssignRequest) -> AssignResponse:
    """把「关键词」补到某个具体小微名下（**去重追加**）⇒ 用户**再抓一次**即自动命中（链路 C）。

    口径（§2.5.1 链路 C · 原型 `ownOk` 三态）：
    - ⛔ 关键词**必须出现在单据名里**（`validate_keyword_in_doc`）—— **填不出说明不是它**（不猜）
    - **选已有小微** ⇒ `append_keyword_dedup` 追加（**只动 `match_keywords`**，别的字段一律不碰）
    - **属于新小微** ⇒ 壳 ＋ 仓库名 ＋ 关键词；⚠️ **已归档的壳下不许新建**
      （新小微必然「在建」⇒ 会当场破坏「壳归档 ⇔ 小微全归档」；该判定由 `create_project` 内部出口负责，此处只把它翻译成中文回执）
    - ⛔ 本端点**不写任何通知书数据** —— 本批已被拒、库里没有它的行（§2.7.4）

    ⚠️ 本动作**只补档案**，补完必须**再抓一次**（回执里讲清这一点，别让用户以为已经落库）。
    """
    try:
        keyword = validate_keyword_in_doc(req.keyword, req.doc_name)
    except MustReportError as exc:
        return AssignResponse(ok=False, message=str(exc))

    with session_scope() as session:
        projects = all_projects(session)

        if req.small_id:
            small = next((p for p in projects if p.id == req.small_id), None)
            if small is None:
                return AssignResponse(ok=False, message=f"具体小微 {req.small_id} 不存在")
            proj_repo.set_keywords(
                session, small, append_keyword_dedup(small.match_keywords, keyword)
            )
            label = small.disp or small.warehouse_name or small.name_full
            return AssignResponse(
                ok=True,
                message=(
                    f"关键词「{keyword}」已去重追加到 <b>{label}</b>。"
                    "请**再抓一次** —— 这次会自动命中并落库。"
                ),
            )

        name = (req.new_small_name or "").strip()
        if not name:
            return AssignResponse(ok=False, message="新建小微需要填「仓库名」")
        shell = next((p for p in projects if p.id == req.shell_id), None)
        if shell is None:
            return AssignResponse(ok=False, message="壳未建档 ⇒ 必须先有壳后有微（链路 A）")
        try:
            proj_repo.create_project(
                session,
                project_type=TYPE_SMALL,
                name_full=shell.name_full,
                warehouse_name=name,
                parent_shell_id=shell.id,
                match_keywords=[keyword],
            )
        except MustReportError as exc:      # 已归档的壳下不许新建 —— 原样把原因给用户
            return AssignResponse(ok=False, message=str(exc))
        return AssignResponse(
            ok=True,
            message=(
                f"已建档并归集：<b>{name}</b>（关键词「{keyword}」）。"
                "请**再抓一次** —— 这次会自动命中并落库。"
            ),
        )


def _wh_loader_dep() -> Callable[..., list[dict]]:
    """仓库名单取数（`API-05`）—— ⚠️ **局部导入** `mod02_i8.router`（与 `get_fetch_executor` 同款，
    避开模块级循环依赖）；测试用 `app.dependency_overrides[_wh_loader_dep]` 注入桩（**不连 i8**）。"""
    from app.mod02_i8.router import get_warehouse_rows  # noqa: PLC0415

    return get_warehouse_rows()


@router.post("/notices/warehouse-check", response_model=WarehouseCheckOut)
def warehouse_check(
    req: WarehouseCheckRequest,
    wh_loader: Callable[..., list[dict]] = Depends(_wh_loader_dep),
) -> WarehouseCheckOut:
    """**兜底前先跑一次 i8 仓库名单**（`TAIL-39` · 用户 2026-09-18 口述裁定）。

    原话：「**在兜底前，系统的设计里应该有去仓库跑了一环这个逻辑，而且如果跑完没结果要在界面上提醒用户**」。
    为什么要这一环：链路 C 的兜底 = **手填仓库名**新建具体小微 ⇒ 用户若**凭猜**填，就留下一条与 i8 不符的
    **假档案行**；日后 i8 真建了仓库 ⇒ 系统**再建一行**（重复）。

    ⚠️ **只读**：不落库、不建档（名单本身也不留档 —— 与 `POST /api/m02/sync/warehouses` 同一口径）；
       判定走 `mod01_projects.domain.i8_warehouse_lookup`（**唯一出口**），本层只组装回执。
    ⚠️ 取名单**要登录 i8**、可能**强踢**在线用户 ⇒ `allow_kick` 默认 `False`，壳侧必须**二次确认之后**才传 `True`（`D9`）。
    ⚠️ **禁静默**：取不到 ⇒ `degraded=True` ＋ 中文说明，⛔ **不许把"没取到"说成"名单里没有"**（那是两回事）。
    """
    name = str(req.warehouse_name or "").strip()
    if not name:
        return WarehouseCheckOut(warehouse_name="", degraded=True, message="请先填「仓库名」再查")

    cached_at = ""
    head = ""
    try:
        rows = wh_loader(req.allow_kick)
    except Exception as exc:                              # noqa: BLE001
        # ⭐ `TAIL-39`：抓不到 ⇒ **回退到上一次的名单**接着判（缓存是优化、不是功能），
        #    但**必须说清"这是几点抓的"** —— ⛔ 不许把旧名单说成刚抓的（`wh_cache` 纪律 2）。
        rows, cached_at = wh_cache.load()
        if not rows:
            return WarehouseCheckOut(
                warehouse_name=name,
                degraded=True,
                message=(
                    f"没取到 i8 仓库名单：{type(exc).__name__}: {exc}"
                    "（⚠️ 这只是**没查到**，**不等于名单里没有**；也没有可用的上次名单 —— 可稍后重试）"
                ),
            )
        head = (f"⚠️ 这次**没取到**名单（{type(exc).__name__}）⇒ 下面用的是 "
                f"**{cached_at or '未知时间'}** 那份缓存（{len(rows)} 条）：<br>")

    info = i8_warehouse_lookup(name, rows)
    total = int(info["total"])
    if info["found"]:
        owners = info["owners"]
        more = "（⚠️ 同名挂多条全名 ⇒ 要人来定，系统不替选）" if len(owners) > 1 else ""
        return WarehouseCheckOut(
            warehouse_name=name,
            found=True,
            owners=owners,
            total=total,
            from_cache=bool(cached_at),
            cached_at=cached_at,
            message=head + (
                f"i8 名单里**有**「{name}」，挂在 "
                + ("、".join(f"「{o}」" for o in owners) if owners else "（名单里这行没写所属项目）")
                + f" 下{more}（名单共 {total} 条）"
            ),
        )
    return WarehouseCheckOut(
        warehouse_name=name,
        found=False,
        total=total,
        from_cache=bool(cached_at),
        cached_at=cached_at,
        message=head + (
            f"⚠️ i8 名单里**没有**「{name}」（名单共 {total} 条）—— 若现在按这个名字建具体小微，"
            "日后 i8 真建了这个仓库，系统会**再建一行**（重复）。**要建请显式确认**。"
        ),
    )


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


@router.get("/settings/printers", response_model=list[str])
def list_local_printers() -> list[str]:
    """本机装了驱动的打印机名（给设置弹窗选 —— 选「系统驱动」通道时**名字要一字不差**）。

    ⚠️ 拿不到就回**空表**（没装 `pywin32` / 不是 Windows）：说明"给不了提示"，⛔ 不是错误、⛔ 不猜名字。
    """
    return list_printers()


@router.get("/settings/printer", response_model=PrinterSettingResponse)
def get_printer_setting() -> PrinterSettingResponse:
    """打印机设置当前值（设置弹窗回填用）—— **地址 ＋ 出纸通道 ＋ 打印机名**（`TAIL-46`-③）。"""
    s = get_settings()
    return PrinterSettingResponse(
        printer_ipp_url=s.printer_ipp_url,
        print_mode=s.print_mode or "auto",
        printer_name=s.printer_name or "",
    )


@router.put("/settings/printer", response_model=PrinterSettingResponse)
def set_printer_setting(req: PrinterSettingRequest) -> PrinterSettingResponse:
    """修改打印机设置（SETUP-001）：写 `.env` + `cache_clear()` ⇒ **即时生效、无需重启**。

    ⚠️ 三项**一起写**；任一项非法 ⇒ **一个字都不写**（先校验后落盘 —— 不许出现"地址改了、通道没改"的半套）。
    """
    out = apply_printer_setting(
        req.printer_ipp_url, mode=req.print_mode, printer_name=req.printer_name
    )
    return PrinterSettingResponse(**out)


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
