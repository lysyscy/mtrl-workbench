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
- 已审批、未审批均参与写入；回执说明匹配、忽略与未完成归属的数量和项目。

⚠️ 与 `mod08` 的一处**刻意不同**：那边是"陌生**仓库** ⇒ 扶正"，走 `recovery`；
集采**没有仓库**，有的只是项目全名 ⇒ 走 `sync_service`（"同步常用项目 ⇒ 建档"）。
"""

from __future__ import annotations

# ⚠️ 2026-09-20：`run_fetch` 要取"动作开始前"的时刻给 `save_run_record`（见它的 `started_at` 那段
#    —— 不传 ⇒ 耗时恒 0，用户实测报过）
from contextlib import ExitStack
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.errors import MustReportError, human_reason
from app.core.identity import current_operator
from app.core.session import current_name
# ⚠️⚠️ 2026-09-20 补：`default_since` 里调了 `logger.warning(...)` 但**本文件从没有 logger**
#    ⇒ 一旦"库里最大合同日期"不是个合法日期（手改过 / 脏数据），那一步会抛
#    `NameError: name 'logger' is not defined` —— 而那句话的**本意**是"保守回落全量、并留个印子"。
#    ⇒ 静默地把"留痕"变成"炸掉"。已补 logger（与全仓同一口径：`get_logger()`）。
from app.core.logging import get_logger
from app.mod01_projects.domain import norm_full_name, resolve_ownership
from app.mod01_projects.pending import record_detail
from app.mod01_projects import service as P1S
from app.mod01_projects.sync_service import sync_and_archive
from app.mod02_i8 import fetch_task
from app.mod02_i8.client import serialize_fetch
from app.mod02_i8.browser_relay import open_i8_client
from app.mod02_i8.browser_session import (
    StrictSessionEnded,
    StrictSessionUnavailable,
    StrictTargetMismatch,
)
from app.mod02_i8.contract_source import ContractFetcher
from app.mod02_i8.notice_source import APPROVE_STATUS_DONE, APPROVE_STATUS_OTHER
from app.mod02_i8.repository import save_run_record
from app.mod02_i8.sources import CommonProjectSource, load_warehouse_rows
from app.mod11_jc import repository as R
from app.mod11_jc.models import KIND_PARTY_UNKNOWN

_APPROVAL_LABELS = {APPROVE_STATUS_DONE: "已审批", APPROVE_STATUS_OTHER: "未审批"}

#: 同表抓取串行锁的键（`D9`：同一张表抓取互斥）。
TABLE = "jc_contract"

#: 抓前**二次确认**（`D9`）—— 常量在 `mod02_i8.fetch_task`（**唯一存放处**，各抓取点共用）；
#: 这里再导出一份，保持既有引用不变（同 `mod08`）。
CONFIRM_TOKEN = fetch_task.CONFIRM_TOKEN
KICK_WARNING = fetch_task.KICK_WARNING

logger = get_logger()


def match_projects(rows: list[dict], projects: list) -> dict:
    """抓取行 → **项目归属**（⭐ 与付款通知书抓取**同一套**：唯一出口 = `mod01_projects.domain.resolve_ownership`）。

    ⚠️⚠️ **为什么不再"按全名精确相等取第一条"**（用户 2026-09-25 口径「**集采合同抓取和付款通知书抓取
    用同一套匹配逻辑**」＋ 同日实测）：
    **壳与具体小微共用同一个全名**（《说明书》§2.2 / §2.6）⇒ 拿全名去撞项目表**必然**命中 `[壳, 小微]` 两行，
    而壳**没有仓库、不进任何候选**（§2.7.4）⇒ 取到壳 = 那批合同在界面上「**没有项目**」、**欠款无从归集**
    （2026-09-25 实测 **23 条**）。这正是**铁律 §9.8-6**「先判断这个全名是不是壳，**不要直接拿全名去撞项目表**」要防的事。

    ⇒ 本函数**只做分堆**，判定一律委托 `resolve_ownership`（⛔ 本层不再自己判一遍 —— 判定只有一个主人）：
    · 普通项目全名 ⇒ `normal` ⇒ 落库
    · **壳全名 ＋ 单据名命中该壳下某一个小微** ⇒ `small` ⇒ **落到那个小微**（不弹窗）
    · 壳全名 ＋ 命中多个 / 一个都没命中 / 项目未建档 ⇒ `settled=False` ⇒ **不落库**，随回执与执行记录报出（**禁静默**）

    ⚠️ 「单据名」取 i8 原文 `fields.BillName`，与付款通知书**同一套 i8 单据名**（`jc_contract.bill_name` 就是它）。
    ⚠️ `recovery.hits_of_full` 那套是**材料侧（按仓库名）**的出口，集采**没有仓库** ⇒ 不适用；口径主人 = §2.5.1 / §9.8-6。
    """
    matched: list[dict] = []
    unmatched: list[dict] = []
    multi = 0
    for row in rows or ():
        d = resolve_ownership(
            name_full=str(row.get("project_name") or ""),
            doc_name=str((row.get("fields") or {}).get("BillName") or ""),
            projects=projects,
        )
        if not d.settled:
            # ⭐ `needs_choice` = 壳下命中小微**多个**（= 老口径里 `multi` 那批，但现在**不落库**、报出来让人选）
            if d.kind == "needs_choice":
                multi += 1
            unmatched.append({**row, "unsettled_kind": d.kind, "unsettled_reason": d.reason})
            continue
        matched.append({**row, "project_id": int(d.target_id)})     # ← 落的是**具体小微**（不是壳）
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


#: 增量抓的**回看天数**（默认起点 = 库里最大合同日期 − 这个数）。
SINCE_LOOKBACK_DAYS = 3


def default_since(s: Session) -> str:
    """增量抓的**默认起点**（`YYYY-MM-DD`）= 库里**最大合同日期 − 3 天**；库空 ⇒ `""`（= 全量）。

    ⭐ **为什么不另存"上次抓取日期"这个状态**：那要**再开一份状态**（新表 / 新设置项），
      而状态会**漂移** —— 清了库、换了机器、手改了数据 ⇒ 状态就**假了**，而且是静默地假。
      直接**从数据本身推**（`max(contract_date)`）⇒ **自愈**：台账在，起点就对。
    ⚠️ **必须往前推几天**：i8 里**增补合同会沿用原单据日期**（实测确有 `2024` 年的合同挂在近期单据下）
      ⇒ 起点卡在"最后一天"会**漏掉它们**。而落库按 `BillNo` **幂等** ⇒ 推早只是多拿几条、**不会重复插**。
    ⚠️ 库空（首次抓取）⇒ 回空串 ⇒ 走**全量**（~40 秒）；此后都是 **1~5 秒**。
    """
    from datetime import date, timedelta

    from sqlalchemy import func, select

    from app.mod11_jc.models import JcContract

    latest = str(s.execute(select(func.max(JcContract.contract_date))).scalar() or "").strip()[:10]
    if not latest:
        return ""
    try:
        return (date.fromisoformat(latest) - timedelta(days=SINCE_LOOKBACK_DAYS)).isoformat()
    except ValueError:
        # ⚠️ 日期不认 ⇒ **保守全量**（⛔ 不猜、也⛔ 不静默少抓 —— 少抓是最坏的一类错）
        logger.warning("合同日期 {:r} 不像日期 ⇒ 增量起点回落「全量」", latest)
        return ""


def run_fetch(
    *,
    confirmed: bool,
    operator: str = "",
    since: str | None = "",
    client_factory: Callable | None = None,
    fetch: Callable | None = None,
    sync: Callable | None = None,
    loaders: tuple[Callable, Callable] | None = None,
) -> dict:
    """Own the fetch transaction phases; external callbacks never borrow a Session.

    None selects the current incremental start; an empty string remains full fetch.
    Project sync, contract application and the receipt commit together. Ordinary
    sync failure rolls back only its savepoint; strict transport stops propagate.
    """
    if not confirmed:
        raise MustReportError(f"抓取前必须二次确认：{KICK_WARNING}")
    t0 = datetime.now()
    if since is None:
        with session_scope() as s:
            since = default_since(s)
    since = str(since or "")
    operator = operator or current_operator()
    client_factory = client_factory or (
        lambda: open_i8_client(allow_kick=True, owner=str(current_name()))
    )
    material_filled = material_blank = 0
    common_rows, warehouse_rows, sync_failure = [], [], None
    with ExitStack() as batch:
        try:
            # One table lock spans acquisition through commit, without a DB
            # connection while waiting for it or for any external response.
            batch.enter_context(serialize_fetch(TABLE))
            client = client_factory()
            try:
                fetcher = ContractFetcher(client)
                fetched_rows = fetcher.fetch_in_locked_batch(since=since) if fetch is None else fetch(client)
                with session_scope() as s:
                    rows, ignored_rows = split_ignored(s, fetched_rows)
                    known = R.existing_contract_nos(s, [str(r.get("contract_no") or "") for r in rows]) if fetch is None and rows else set()
                if fetch is None:
                    for row in rows:
                        no = str(row.get("contract_no") or "").strip()
                        if not no or no in known:
                            continue
                        name = fetcher.fetch_item_name(str((row.get("fields") or {}).get("PhId") or ""))
                        if name:
                            row["material_name"] = name
                            material_filled += 1
                        else:
                            material_blank += 1
                load_common, load_wh = loaders if loaders is not None else default_loaders(client)
                try:
                    common_rows, warehouse_rows = load_common(), load_wh()
                except (StrictSessionUnavailable, StrictTargetMismatch, StrictSessionEnded):
                    raise
                except Exception as exc:
                    sync_failure = exc
            finally:
                close = getattr(client, "close", None)
                if callable(close):
                    close()
        except (StrictSessionUnavailable, StrictTargetMismatch, StrictSessionEnded):
            raise
        except Exception as exc:
            notice = fetch_task.degrade_to_excel(exc)
            with session_scope() as s:
                run = save_run_record(s, **fetch_task.fetch_record_payload(
                    object_desc=f"{TABLE} 全量", success=0, fail=1,
                    error_message=f"{type(exc).__name__}: {exc}"),
                    detail={**record_detail(), **R.fetch_detail()},
                    operator=operator, started_at=t0)
            return {"ok": False, "degraded": True, "message": notice["message"],
                    "excel_import_available": True, "run_record_id": getattr(run, "id", None)}

        def common_snapshot():
            if sync_failure is not None:
                raise sync_failure
            return common_rows

        # Re-read local project/party/contract facts in the apply transaction;
        # replayed loaders contain ordinary values, never network operations.
        with session_scope() as s:
            R.lock_ignored_rules(s)
            current_rows, current_ignored = split_ignored(s, fetched_rows)
            if len(current_rows) != len(rows) or any(current is not previous for current, previous in zip(current_rows, rows)):
                raise MustReportError('集采剔除名单已变化，本次未写入合同；请重新抓取。')
            rows, ignored_rows = current_rows, current_ignored
            try:
                with s.begin_nested():
                    sync_result = (sync or sync_and_archive)(
                        s, load_common=common_snapshot, load_warehouses=lambda: warehouse_rows)
            except (StrictSessionUnavailable, StrictTargetMismatch, StrictSessionEnded):
                raise
            except Exception as exc:
                sync_result = {"degraded": True, "message": human_reason(
                    "常用项目同步失败", exc, next_step="本次仍按**现有档案**匹配；可稍后重抓一次")}

            # ⭐⭐ **甲方单位归类**（`M5-6b` · 用户 2026-09-20 口径）—— 落库前必须先有它：
            #    `upsert_fetched_contracts` 靠 `row["party_kind"]` 决定**金额落哪一列**。
            #    ⚠️ **没见过的甲方先落 `unknown` 等人指定**（⛔ 不静默当成"正常"），并**在回执里报出来**。
            # ⚠️⚠️ **必须排在 `match_projects` 之前**（2026-09-26 用户报障「抓取后那批合同还是没变」的**真因**）：
            #    `match_projects` 返回的是 **`{**row, project_id}` 造出来的新 dict** ⇒ 在它**之后**才打的
            #    `party_kind` 只落在**原 `rows`** 上，**副本里没有** ⇒ 落库看到的是 `unknown`
            #    ⇒ **永远走"正常甲方"分支** ⇒ 贸易公司合同的 i8 价被写进「合同金额」、贸易两列永远空
            #    （分类表里明明标着 `trade` —— 用户看到的就是这个）。
            new_parties = R.ensure_party_kinds(s, [str(r.get("party_name") or "") for r in rows])
            _kmap = R.party_kind_map(s)
            for _r in rows:
                _r["party_kind"] = _kmap.get(str(_r.get("party_name") or "").strip(), KIND_PARTY_UNKNOWN)

            # ⭐ **再匹配**（档案已被上一步补过）——⚠️ 这一步会**复制**行 dict ⇒ 所以它必须在**上面那段之后**
            m = match_projects(rows, P1S.all_projects(s))

            # ⭐ 分开落库：一张合同必有项目（§6.4.1）⇒ 只落**匹配上**的；匹配不上 = i8 常用列表里也没有 = 不需要
            stats = {"inserted": 0, "refreshed": 0, "skipped": 0}
            by_pid: dict[int, list[dict]] = {}
            for row in m["matched"]:
                by_pid.setdefault(int(row["project_id"]), []).append({
                    **row, "approve_status": _APPROVAL_LABELS.get(row.get("approve_status")),
                })
            for pid, group in by_pid.items():
                part = R.upsert_fetched_contracts(s, project_id=pid, rows=group)
                for k in stats:
                    stats[k] += int(part.get(k) or 0)

            run = save_run_record(s, **fetch_task.fetch_record_payload(
                object_desc=f"{TABLE} 全量（{len(rows)} 条）",
                success=len(m["matched"]), fail=0),
                # ⚠️ `record_detail()` 是**材料侧**的键（`promote_pending`，集采天然用不上）⇒ 在其后**追加集采自己的**
                #    未走完清单（`jc_unsettled`）：少了它，这些合同只会"静默地没落库"（⛔ 禁静默）。
                detail={**record_detail(),
                        **R.fetch_detail(
                            jc_unsettled_count=len(m["unmatched"]),
                            jc_ignored_count=len(ignored_rows),
                            jc_unsettled=[
                                {"contract_no": str(r.get("contract_no") or ""),
                                 "project_name": str(r.get("project_name") or ""),
                                 "doc_name": bill_name(r),
                                 "kind": r.get("unsettled_kind")}
                                for r in m["unmatched"][:200]       # 截断保护：回执不该被几千条撑爆
                            ],
                            jc_ignored=ignored_rows[:200])},
                operator=operator, started_at=t0)
            return {
                "ok": True, "degraded": False,
                "since": since,                                  # ⭐ 本次的日期起点（空 = 全量）
                "fetched": len(rows),
                # ⭐ 材料名的补数情况（⛔ 禁静默：补不上多少条必须让人看见）
                "material_filled": material_filled, "material_blank": material_blank,
                # ⭐ `M5-6b`：这一次**新遇到的甲方单位**（已落成"未指定"）—— ⛔ 必须报出来让人去指定，
                #    否则它们的金额会按"正常"落 `contract_amt`（可逆，但**不指定就一直不对**）。
                "new_parties": new_parties,
                # ⭐ `TAIL-96`：被剔除名单挡下的（⛔ 不静默 —— 得让人看见"哪些项目被当成不要的了"）
                "ignored": len(ignored_rows), "ignored_projects": _tally(ignored_rows, "project_name"),
                "matched": len(m["matched"]), "unmatched": len(m["unmatched"]), "multi": m["multi"],
                # ⭐ `TAIL-92`：没落库的按**归属类别**分开报（⛔ 禁静默 —— 得让人看出"卡在哪一步"）：
                #    `needs_keyword` = 壳认出来了、但单据名里没有该壳下任何小微的关键词（**最常见**，要人去指认/补词）
                #    `needs_choice`  = 命中了多个小微（要人挑一个）· `not_archived` = 项目还没建档
                "unsettled": _tally(m["unmatched"], "unsettled_kind"),
                "stats": stats,
                # ⭐ **匹配预览**（落库前就该让人看见的那两块；这里随回执一起回，壳直接用）
                "matched_projects": _tally(m["matched"], "project_name"),
                "unmatched_projects": _tally(m["unmatched"], "project_name"),
                "sync": {k: v for k, v in (sync_result or {}).items() if k != "created"},
                "run_record_id": getattr(run, "id", None),
                "message": (
                    f"抓取 {len(rows)} 条 · 匹配上 {len(m['matched'])} 条"
                    f"（新增 {stats['inserted']} / 刷新 {stats['refreshed']}）· "
                    f"归属未走完、未写入 {len(m['unmatched'])} 条（按口径 = 不纳入；清单见执行记录）"
                    + (f" · ⚠️ {sync_result.get('message')}" if sync_result.get("degraded") else "")
                ),
            }


__all__ = ["TABLE", "CONFIRM_TOKEN", "KICK_WARNING",
           "match_projects", "default_loaders", "run_fetch"]


def bill_name(row: dict) -> str:
    return str(row.get("bill_name") or (row.get("fields") or {}).get("BillName") or "")


def split_ignored(s: Session, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """保留原合同对象与顺序，另外返回剔除合同及命中条件的快照。"""
    rules = R.ignored_rules(s)
    if not rules:
        return rows, []
    by_number: dict[str, list[dict]] = {}
    by_project: dict[str, list[dict]] = {}
    for rule in rules:
        payload = R.ignore_rule_payload(rule)
        if rule.kind == "contract" and rule.contract_no:
            by_number.setdefault(rule.contract_no, []).append(payload)
        elif rule.kind in {"project", "keyword"} and (name := norm_full_name(rule.name_full)):
            by_project.setdefault(name, []).append(payload)

    candidates: list[tuple[str, dict]] = []
    ignored: dict[str, dict] = {}
    for row in rows or ():
        project = str(row.get("project_name") or "")
        number = str(row.get("contract_no") or "").strip()
        name = bill_name(row)
        matches = [*by_number.get(number, ()), *(
            rule for rule in by_project.get(norm_full_name(project), ())
            if rule["kind"] == "project" or (rule["bill_name_keyword"] and rule["bill_name_keyword"] in name)
        )]
        if matches:
            if number not in ignored:
                ignored[number] = {"contract_no": number, "project_name": project, "doc_name": name, "matches": matches}
            else:
                snapshot = ignored[number]["matches"]
                seen = {rule["id"] for rule in snapshot}
                snapshot.extend(rule for rule in matches if rule["id"] not in seen)
        else:
            candidates.append((number, row))
    return [row for number, row in candidates if number not in ignored], list(ignored.values())
