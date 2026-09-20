"""`MOD-07` 收发结存 · **抓取编排**（`API-02`：导出 → 解析 → 幂等落库 → 执行记录）。

依据：
- 《说明书》**§5.3.2**（交付形态）· **§9.2**（报表类按核算年月；**抓取只允许单月**）
  · **§3.6**（接口不可用 ⇒ **降级为手动 Excel 导入**并**显式说明**）· **§9.5**（导入幂等）
- 《技术栈选型分析》**§9.8**（`rep_id` / `dataSetId` / 项目参数 **`pc`** / **`reportName` = 收发结存表**）
- 用户裁定 **D9**：抓取一律手动（无定时）· **失败不得自动重试登录** · 抓前须**二次确认并告知会强踢**

⭐ **陌生仓库**（导出里有、项目档案里没有）⇒ **自动建档 / 扶正**（《说明书》§2.4.2 **链路 B**，
   `ACC-PRJ-AUTO-001`）：**复用本次同一个 i8 会话**取一次仓库名单（**不额外登录、不重复强踢**），
   再交 `MOD-01` 的 `recovery.recover_unknown_warehouses` 能扶正就扶正、扶不了就按全名新建
   —— **不要求用户点任何东西**。
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
    unknown_warehouses as shared_unknown_warehouses,
)
from app.mod01_projects.repository import export_phids
from app.mod02_i8 import fetch_task, report_export
from app.mod02_i8.client import I8Client, serialize_fetch
from app.mod02_i8.repository import save_run_record
from app.mod02_i8.sources import load_warehouse_rows
from app.mod07_setl import importer
from app.mod07_setl.repository import upsert_month

TABLE = "setl_detail"         # 同表抓取串行锁的键（D9）
SPEC_KEY = "setl"             # `app.core.config.I8_REPORTS` 里的登记键
CONFIRM_TOKEN = fetch_task.CONFIRM_TOKEN          # 唯一存放处 = `mod02_i8.fetch_task`
KICK_WARNING = fetch_task.KICK_WARNING


def build_plan(year_month: str) -> dict:
    """抓取计划：**只允许单月**（§9.2）⇒ 复用 `report_export.single_month` 的四个独立值。"""
    y1, m1, y2, m2 = report_export.single_month(year_month)
    return {"ym": f"{int(y1):04d}-{int(m1):02d}", "start": (y1, m1), "end": (y2, m2)}


def project_ids(s: Session) -> str:
    """导出用的项目 id 串 —— 实体在 `MOD-01`（`repository.export_phids`：**保序去重**），此处只是**薄名**。

    ⚠️ 别在本模块再写一份拼接：壳与其下的**具体小微**共享同一个 `phid`，不去重就会把项目导出两遍
       （`ACC-PRJ-AUTO-001/001-03`；真机实测 2026-09-17）。
    """
    return export_phids(s)


def unknown_warehouses(s: Session, rows: list[dict]) -> list[str]:
    """导出里出现、但**项目档案里没有**的仓库（§2.5「陌生仓库」）—— 实体在 `MOD-01`，此处只是**薄名**。"""
    return shared_unknown_warehouses(s, rows)


def _load_wh_rows(client) -> list[dict] | None:
    """取一次**仓库名单**（`API-05`，**复用本次登录会话**）—— 实体在 `mod02_i8.sources`，此处只是**薄名**。"""
    return load_warehouse_rows(client)


def _wh_loader(wh_rows):
    """把「已经取到的名单」包成 `recovery` 要的 loader（取不到 ⇒ 抛，由编排转成降级说明）。"""
    def _load() -> list[dict]:
        if wh_rows is None:
            raise RuntimeError("仓库名单（API-05）本次没取到")
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
    """跑一次抓取（**人工触发**）→ 结果字典。

    ⚠️ 失败 ⇒ **降级为手动 Excel 导入并显式说明**（§3.6），**绝不自动重试登录**（D9）。
    ⚠️ 走到网络之前就失败的（未确认 / 非单月 / 无 phid / 报表登记不全）⇒ **不写执行记录**（那是用法错误）。
    ⚠️ 导出**结构完好但一行数据都没有** ⇒ **不动本地数据**，显式报出（防"空导出把已有数据清空"）。
    """
    # ⚠️ **耗时的起点**：必须在任何导出 / 网络动作**之前**（见 `save_run_record` 的 `started_at` 那段）
    t0 = datetime.now()
    plan = build_plan(year_month)                       # 非单月 ⇒ 这里就抛
    if not confirmed:
        raise MustReportError(f"抓取前必须二次确认：{KICK_WARNING}")

    ids = project_ids(s)
    report_export.require_ready(SPEC_KEY)               # 登记不全（如 reportName 未定稿）⇒ 显式拒
    operator = operator or current_operator()
    client_factory = client_factory or (lambda: I8Client(allow_kick=True))
    export = export or (lambda c, ym, ids_: report_export.export(
        c, spec_key=SPEC_KEY, year_month=ym, proj_ids=ids_))

    target = f"{SPEC_KEY} {plan['ym']}（{len(ids.split(','))} 个项目）"
    wh_rows: list[dict] | None = None
    try:
        with serialize_fetch(TABLE):                    # 同表串行（D9）
            client = client_factory()
            try:
                content = export(client, plan["ym"], ids)
                wh_rows = _load_wh_rows(client)          # ⭐ 顺手取仓库名单（链路 B 建档要用；失败⇒None）
            finally:
                close = getattr(client, "close", None)
                if callable(close):
                    close()
        rows = importer.parse_rows(content, ym=plan["ym"])
    except Exception as exc:                            # noqa: BLE001 —— 一律降级，不静默
        notice = fetch_task.degrade_to_excel(exc)
        run = save_run_record(s, **fetch_task.fetch_record_payload(
            object_desc=target, success=0, fail=1,        # fail=1 ⇒ status=failed（这一批失败）
            error_message=f"{type(exc).__name__}: {exc}"),
            detail=record_detail(), operator=operator,    # ⭐ 「待人工」清单：本次没有 ⇒ 写空（见 pending 口径 1）
            started_at=t0)
        return {"ok": False, "degraded": True, "message": notice["message"],
                "excel_import_available": True, "ym": plan["ym"],
                "run_record_id": getattr(run, "id", None)}

    if not rows:
        run = save_run_record(s, **fetch_task.fetch_record_payload(
            object_desc=target, success=0, fail=0),
            detail=record_detail(), operator=operator,    # 一行都没抓到 ⇒ 没有待人工
            started_at=t0)
        return {"ok": False, "degraded": False, "empty": True, "ym": plan["ym"],
                "message": (f"{plan['ym']} 的导出里**一行明细都没有** ⇒ **未改动本地数据**"
                            "（不拿空结果去清已有数据）—— 请核对导出条件后再抓。"),
                "run_record_id": getattr(run, "id", None)}

    stats = upsert_month(s, ym=plan["ym"], rows=rows)
    unknown = unknown_warehouses(s, rows)
    # ⭐ 链路 B：遇陌生仓库 ⇒ **自动**建档 / 扶正（无感；失败降级，不拖垮抓取）
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
           "build_plan", "project_ids", "unknown_warehouses", "run_fetch"]
