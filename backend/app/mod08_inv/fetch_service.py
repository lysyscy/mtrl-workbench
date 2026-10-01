"""`MOD-08` 库存单据明细 · **抓取编排**（`API-03`：导出 → 解析 → 幂等落库 → 执行记录）。

依据：
- 《说明书》**§3.4**（导出条件 = 核算年月 + 项目）· **§9.2**（报表类按核算年月；**抓取只允许单月**）
  · **§9.5**（导入幂等）。⚠️ **2026-09-22 用户裁定**：**「手动 Excel 导入」兜底已删** ——
   接口不可用 ⇒ **显式报错待人处理**（原因 + 请稍后重试），⛔ 不再指向手动导入（§3.6 降级口径作废）。
- 《技术栈选型分析》**§9.8**（接口形态：起止年月四个独立值 · `xmid` · `reportName=null`）
- 用户裁定 **D9**：**抓取一律手动**（无定时）· **失败不得自动重试登录** · 抓前须**二次确认并告知会强踢**

⛔ 本模块**不落「是否作废」**（`NG-06`）—— 由 `importer` 在解析阶段丢弃。

⭐ **陌生仓库**（导出里有、项目档案里没有）⇒ **自动建档 / 扶正**（《说明书》§2.4.2 **链路 B**，
   `ACC-PRJ-AUTO-001`）—— 与 `MOD-07` **共用同一份** `MOD-01.recovery`（**唯一出口**）；
   **复用本次同一个 i8 会话**取仓库名单（**不额外登录、不重复强踢**），**不要求用户点任何东西**。
⚠️ 这一步**失败绝不拖垮抓取**（数据此时**已入库**）⇒ 降级进回执并说明「可稍后重抓一次」。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.core.identity import current_operator
# ⚠️ 2026-09-20：`run_fetch` 要取"动作开始前"的时刻给 `save_run_record`（见它的 `started_at` 那段
#    —— 不传 ⇒ 耗时恒 0，用户实测报过）
from app.mod01_projects.pending import record_detail
from app.mod01_projects.recovery import (
    recover_unknown_warehouses,
    unknown_warehouses,
)
from app.mod01_projects.repository import export_phids
import logging

from app.mod02_i8 import fetch_task, report_export, source_cache

logger = logging.getLogger(__name__)
from app.mod02_i8.client import I8Client, serialize_fetch
from app.mod02_i8.repository import save_run_record
from app.mod02_i8.sources import load_warehouse_rows
from app.mod08_inv import importer
from app.mod08_inv.repository import upsert_details

TABLE = "inv_detail"          # 同表抓取串行锁的键（D9）
SPEC_KEY = "inv"              # `app.core.config.I8_REPORTS` 里的登记键

# ⭐ 抓前**二次确认**（D9）—— 常量已提到 `mod02_i8.fetch_task`（**唯一存放处**，各抓取点共用）；
#    这里**再导出一份**保持既有引用（`view` / 测试）不变。
CONFIRM_TOKEN = fetch_task.CONFIRM_TOKEN
KICK_WARNING = fetch_task.KICK_WARNING


def build_plan(year_month: str) -> dict:
    """抓取计划：**只允许单月**（§9.2）⇒ 复用 `report_export.single_month` 的四个独立值。"""
    y1, m1, y2, m2 = report_export.single_month(year_month)
    ym = f"{int(y1):04d}-{int(m1):02d}"
    return {"ym": ym, "start": (y1, m1), "end": (y2, m2)}


def project_ids(s: Session) -> str:
    """导出用的项目 id 串 —— 实体在 `MOD-01`（`repository.export_phids`：**保序去重**），此处只是**薄名**。

    ⚠️ 别在本模块再写一份拼接：壳与其下的**具体小微**共享同一个 `phid`，不去重就会把项目导出两遍
       （`ACC-PRJ-AUTO-001/001-03`；真机实测 2026-09-17）。
    """
    return export_phids(s)


def group_by_scope(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """按「**核算年月 ＋ 仓库名**」分组（幂等刷新的范围）。"""
    out: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (str(row.get("ym") or ""), str(row.get("warehouse_name") or ""))
        out.setdefault(key, []).append(row)
    return out


def _wh_loader(wh_rows):
    """把「已经取到的名单」包成 `recovery` 要的 loader（取不到 ⇒ 抛，由编排转成**降级说明**）。"""
    def _load() -> list[dict]:
        if wh_rows is None:
            raise RuntimeError("仓库名单本次没取到")
        return wh_rows

    return _load


def run_fetch(
    s: Session,
    *,
    year_month: str,
    confirmed: bool,
    operator: str = "",
    client_factory=None,
    export=None,
) -> dict:
    """跑一次抓取（**人工触发**）→ 返回结果字典（含降级说明 / 条数 / 执行记录 id）。

    ⚠️ 失败 ⇒ **显式报错待人处理**（原因 + 请稍后重试；⛔ 无手动兜底 —— 2026-09-22 用户裁定），**绝不自动重试登录**（D9）。
    ⚠️ 只要走到网络之前就失败的（未确认 / 非单月 / 无 phid），**不写执行记录**也**不降级**（那是用法错误）。
    """
    # ⚠️ **耗时的起点**：必须在任何导出 / 网络动作**之前**（见 `save_run_record` 的 `started_at` 那段）
    t0 = datetime.now()
    plan = build_plan(year_month)                 # 非单月 ⇒ 这里就抛
    if not confirmed:
        raise MustReportError(f"抓取前必须二次确认：{KICK_WARNING}")

    ids = project_ids(s)
    operator = operator or current_operator()
    client_factory = client_factory or (lambda: I8Client(allow_kick=True))
    export = export or (lambda c, ym, ids_: report_export.export(
        c, spec_key=SPEC_KEY, year_month=ym, proj_ids=ids_))

    target = f"{SPEC_KEY} {plan['ym']}（{len(ids.split(','))} 个项目）"
    wh_rows: list[dict] | None = None
    try:
        with serialize_fetch(TABLE):             # 同表串行（D9）
            client = client_factory()
            try:
                content = export(client, plan["ym"], ids)
                wh_rows = load_warehouse_rows(client)   # ⭐ 顺手取仓库名单（链路 B 建档要用；失败⇒None）
            finally:
                close = getattr(client, "close", None)
                if callable(close):
                    close()
        try:                                   # ⭐ 2026-09-21 用户裁定「抓取导出分开」：
            source_cache.save(SPEC_KEY, plan["ym"], content)   # 源文件按月存档 ⇒
        except OSError as cache_exc:           # 「含透视导出」只读这份缓存（⛔ 不再现场登 i8）。
            logger.warning("i8 源文件存档失败（不影响抓取）：%s", cache_exc)
        rows = importer.parse_rows(content)
    except Exception as exc:                      # noqa: BLE001 —— 一律降级，不静默
        notice = fetch_task.degrade_no_manual(exc)   # ⭐ m08 无手动兜底（2026-09-22 用户裁定）
        run = save_run_record(s, **fetch_task.fetch_record_payload(
            object_desc=target, success=0, fail=1,          # fail=1 ⇒ status=failed（这一批失败）
            error_message=f"{type(exc).__name__}: {exc}"),
            detail=record_detail(), operator=operator,      # ⭐ 「待人工」清单：本次没有 ⇒ 写空（pending 口径 1）
            started_at=t0)
        return {"ok": False, "degraded": True, "message": notice["message"],
                "run_record_id": getattr(run, "id", None)}

    stats = {"inserted": 0, "updated": 0, "deleted": 0, "kept_with_adjustment": 0}
    for (ym, warehouse), group in group_by_scope(rows).items():
        part = upsert_details(s, ym=ym, warehouse=warehouse, rows=group)
        for k in stats:
            stats[k] += part[k]

    # ⭐ 链路 B：遇陌生仓库 ⇒ **自动**建档 / 扶正（无感；失败降级，不拖垮抓取）
    unknown = unknown_warehouses(s, rows)
    recovery_result = recover_unknown_warehouses(
        s, unknown_wh=unknown, load_warehouse_rows=_wh_loader(wh_rows), operator=operator)

    run = save_run_record(s, **fetch_task.fetch_record_payload(
        object_desc=target, success=len(rows), fail=0),
        # ⭐ 「待人工」清单随抓取记录落库（`TAIL-30`-③）—— 回执里那句话**只出现一次**，
        #    而人要在 `m01` 上处理它 ⇒ 得先留住（读侧 = `pending.live_pending`）。
        detail=record_detail(recovery_result.get("unresolved_items")), operator=operator,
        started_at=t0)
    return {"ok": True, "degraded": False, "ym": plan["ym"], "rows": len(rows),
            "stats": stats, "unknown_warehouses": unknown, "recovery": recovery_result,
            "run_record_id": getattr(run, "id", None)}


__all__ = ["TABLE", "SPEC_KEY", "CONFIRM_TOKEN", "KICK_WARNING",
           "build_plan", "project_ids", "group_by_scope", "run_fetch"]
