"""`MOD-11` 集采台账 · **抓取编排**（`API-04`：抓合同 → **同步常用项目** → 匹配 → 落库 → 回执）。

依据：用户 **2026-09-19** 的三条裁定 ——
1. 抓取**只做人工点击**（无定时；与 `D9` 一致）；
2. ⭐ **集采抓取也要纳入「全自动建档」的一环**（原文）⇒ 抓完**先跑一次「同步常用项目列表」**，
   **再**判"这个项目要不要"；
3. 匹配口径 = **付款通知书那一套**（`norm_full_name` 归一化后**精确相等**，⛔ 不包含 / 不模糊 / 无兜底）。

⚠️ **为什么顺序不能反**（这是本模块存在的理由）：i8 的「常用项目列表」才是"要管的项目"的**权威名单**，
本地档案只是它的**镜像**。若拿旧档案直接判 ⇒ 会把**该纳管的项目误判成"不需要"**，而且是**静默漏掉**
（最坏的一类错）。而此刻本机档案恰好是新的 ⇒ 接不接结果一样 ⇒ **只有接上才防得住那个将来**。

⚠️ **安全绳**（照 `mod08_inv.fetch_service` / `recovery` 的既有纪律）：
- 同步那一步**失败绝不拖垮抓取**（合同数据与档案是两件事）⇒ **降级进回执显式说明**，继续用**现有档案**匹配；
- 回执**逐条说清**：未审批丢弃几条 · 匹配上几条 · 匹配不上哪些项目（**禁静默**）。

⚠️ 与 `mod08` 的一处**刻意不同**：那边是"陌生**仓库** ⇒ 扶正"，走 `recovery`；
集采**没有仓库**，有的只是项目全名 ⇒ 走 `sync_service`（"同步常用项目 ⇒ 建档"）。
"""

from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod01_projects.domain import norm_full_name
from app.mod01_projects.pending import record_detail
from app.mod01_projects.repository import all_projects
from app.mod01_projects.sync_service import sync_and_archive
from app.mod02_i8 import fetch_task
from app.mod02_i8.client import I8Client, serialize_fetch
from app.mod02_i8.contract_source import ContractFetcher
from app.mod02_i8.repository import save_run_record
from app.mod02_i8.sources import CommonProjectSource, load_warehouse_rows
from app.mod11_jc import repository as R

#: 同表抓取串行锁的键（`D9`：同一张表抓取互斥）。
TABLE = "jc_contract"

#: 抓前**二次确认**（`D9`）—— 常量在 `mod02_i8.fetch_task`（**唯一存放处**，各抓取点共用）；
#: 这里再导出一份，保持既有引用不变（同 `mod08`）。
CONFIRM_TOKEN = fetch_task.CONFIRM_TOKEN
KICK_WARNING = fetch_task.KICK_WARNING


def match_projects(rows: list[dict], projects: list) -> dict:
    """抓取行 → 按**项目全名**分堆（`norm_full_name` 归一化后**精确相等** · ⛔ 不模糊）。

    ⭐ 口径与 `recovery.hits_of_full` **一致**（那是"命中档案行"的唯一出口）—— 本函数是它**只读的镜像**：
    这里不落库、不改档案，所以⛔ 不调 `plan_recovery`（那是"陌生仓库扶正"的入口；集采没有仓库）。

    ⚠️ **同一全名命中多行**（档案里可能真有重复，如"第四工程公司2026年小微项目"）⇒ 取**第一条**
    并计入 `multi` ⇒ **报出来**（⛔ 不静默替人挑一行）。
    """
    by_norm: dict[str, list] = {}
    for p in projects or ():
        by_norm.setdefault(norm_full_name(str(getattr(p, "name_full", "") or "")), []).append(p)

    matched: list[dict] = []
    unmatched: list[dict] = []
    multi = 0
    for row in rows or ():
        hits = by_norm.get(norm_full_name(str(row.get("project_name") or ""))) or []
        if hits:
            if len(hits) > 1:
                multi += 1
            matched.append({**row, "project_id": int(hits[0].id)})
        else:
            unmatched.append(row)
    return {"matched": matched, "unmatched": unmatched, "multi": multi}


def _tally(rows: list[dict], key: str) -> list[dict]:
    """按某字段计数（去重后按条数降序）—— 回执里的**匹配预览**用。"""
    counts: dict[str, int] = {}
    for r in rows or ():
        name = str(r.get(key) or "(无项目)").strip()
        counts[name] = counts.get(name, 0) + 1
    return [{"name": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]


def default_loaders(client):
    """生产取数件：常用项目（`API-06`）＋ 仓库名单（`API-05`），**复用同一个 i8 会话**。

    ⚠️ 与 `mod08` 同口径：**不额外登录、不重复强踢**（`API-05` 那份由 `sources.load_warehouse_rows` 封装）。
    """
    return (lambda: CommonProjectSource(client).fetch(),
            lambda: load_warehouse_rows(client) or [])


def run_fetch(
    s: Session,
    *,
    confirmed: bool,
    operator: str = "",
    client_factory: Callable = None,        # type: ignore[assignment]
    fetch: Callable | None = None,          # type: ignore[type-arg]
    sync: Callable | None = None,           # type: ignore[type-arg]
    loaders: tuple[Callable, Callable] | None = None,
) -> dict:
    """跑一次抓取（**人工触发**）⇒ 回执字典。

    ⚠️ 走到网络**之前**就失败的（未二次确认）⇒ **不写执行记录**（那是用法错误，不是业务失败）；
    之后任何一步失败 ⇒ **降级进回执**（禁静默），**绝不自动重试登录**（`D9`）。
    """
    if not confirmed:
        raise MustReportError(f"抓取前必须二次确认：{KICK_WARNING}")

    operator = operator or current_operator()
    client_factory = client_factory or (lambda: I8Client(allow_kick=True))
    loaders_given = loaders is not None

    rows: list[dict] = []
    dropped = 0
    sync_result: dict = {}
    degraded = ""
    try:
        with serialize_fetch(TABLE):
            client = client_factory()
            try:
                fetcher = ContractFetcher(client)
                if fetch is None:
                    rows = fetcher.fetch_all()
                else:
                    rows = fetch(client)
                dropped = int(getattr(fetcher, "last_unapproved", 0) or 0)
                # ⭐ **先同步常用项目列表**（复用同一会话）—— 失败**不拖垮**抓取，只降级
                load_common, load_wh = loaders if loaders_given else default_loaders(client)
                do_sync = sync or sync_and_archive       # ⚠️ 可注入（测试不连 i8）
                try:
                    sync_result = do_sync(s, load_common=load_common, load_warehouses=load_wh)
                except Exception as exc:                        # noqa: BLE001 —— 降级，不抛
                    sync_result = {"degraded": True,
                                   "message": f"常用项目同步失败：{type(exc).__name__}: {exc}"
                                              "（本次仍按**现有档案**匹配；可稍后重抓一次）"}
                    s.rollback()
            finally:
                close = getattr(client, "close", None)
                if callable(close):
                    close()
    except Exception as exc:                                    # noqa: BLE001 —— 一律降级，不抛
        notice = fetch_task.degrade_to_excel(exc)
        run = save_run_record(s, **fetch_task.fetch_record_payload(
            object_desc=f"{TABLE} 全量", success=0, fail=1,
            error_message=f"{type(exc).__name__}: {exc}"),
            detail=record_detail(), operator=operator)
        return {"ok": False, "degraded": True, "message": notice["message"],
                "excel_import_available": True, "run_record_id": getattr(run, "id", None)}

    # ⭐ **再匹配**（档案已被上一步补过）
    m = match_projects(rows, all_projects(s))

    # ⭐ 分开落库：一张合同必有项目（§6.4.1）⇒ 只落**匹配上**的；匹配不上 = i8 常用列表里也没有 = 不需要
    stats = {"inserted": 0, "refreshed": 0, "skipped": 0}
    by_pid: dict[int, list[dict]] = {}
    for row in m["matched"]:
        by_pid.setdefault(int(row["project_id"]), []).append(row)
    for pid, group in by_pid.items():
        part = R.upsert_fetched_contracts(s, project_id=pid, rows=group)
        for k in stats:
            stats[k] += int(part.get(k) or 0)

    run = save_run_record(s, **fetch_task.fetch_record_payload(
        object_desc=f"{TABLE} 全量（{len(rows)} 条）",
        success=len(m["matched"]), fail=0),
        detail=record_detail(), operator=operator)
    return {
        "ok": True, "degraded": False,
        "fetched": len(rows), "dropped_unapproved": dropped,
        "matched": len(m["matched"]), "unmatched": len(m["unmatched"]), "multi": m["multi"],
        "stats": stats,
        # ⭐ **匹配预览**（落库前就该让人看见的那两块；这里随回执一起回，壳直接用）
        "matched_projects": _tally(m["matched"], "project_name"),
        "unmatched_projects": _tally(m["unmatched"], "project_name"),
        "sync": {k: v for k, v in (sync_result or {}).items() if k != "created"},
        "run_record_id": getattr(run, "id", None),
        "message": (
            f"抓取 {len(rows)} 条（未审批丢弃 {dropped}）· 匹配上 {len(m['matched'])} 条"
            f"（新增 {stats['inserted']} / 刷新 {stats['refreshed']}）· "
            f"匹配不上 {len(m['unmatched'])} 条（按口径 = 不纳入，未落库）"
            + (f" · ⚠️ {sync_result.get('message')}" if sync_result.get("degraded") else "")
        ),
    }


__all__ = ["TABLE", "CONFIRM_TOKEN", "KICK_WARNING",
           "match_projects", "default_loaders", "run_fetch"]
