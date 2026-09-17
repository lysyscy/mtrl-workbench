"""`MOD-07` 收发结存 · **抓取编排**（`API-02`：导出 → 解析 → 幂等落库 → 执行记录）。

依据：
- 《说明书》**§5.3.2**（交付形态）· **§9.2**（报表类按核算年月；**抓取只允许单月**）
  · **§3.6**（接口不可用 ⇒ **降级为手动 Excel 导入**并**显式说明**）· **§9.5**（导入幂等）
- 《技术栈选型分析》**§9.8**（`rep_id` / `dataSetId` / 项目参数 **`pc`** / **`reportName` = 收发结存表**）
- 用户裁定 **D9**：抓取一律手动（无定时）· **失败不得自动重试登录** · 抓前须**二次确认并告知会强踢**

⚠️ **陌生仓库**（导出里有、项目档案里没有）**不自动建档**（不臆造），只在回执里**显式列出** ——
   §5.3 的口径是「找不到即陌生仓库 ⇒ 触发建档 / 扶正」，建档动作归 `MOD-01` 的同步入口。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod02_i8 import fetch_task, report_export
from app.mod02_i8.client import I8Client, serialize_fetch
from app.mod02_i8.repository import save_run_record
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
    """导出用的项目 id 串（**由本地项目档案提供**，§9.8）—— 空则报错，不臆造。"""
    from app.mod01_projects.repository import all_projects

    ids = [str(p.phid) for p in all_projects(s) if str(getattr(p, "phid", "") or "").strip()]
    if not ids:
        raise MustReportError(
            "本地项目档案里没有可用 phid（i8 项目编号）⇒ 无法按项目导出。"
            "请先「同步常用项目列表」（API-06）建档。"
        )
    return ",".join(ids)


def unknown_warehouses(s: Session, rows: list[dict]) -> list[str]:
    """导出里出现、但**项目档案里没有**的仓库（§5.3「陌生仓库」）—— **只报不建**。"""
    from app.mod01_projects.repository import all_projects

    known = {str(getattr(p, "warehouse_name", "") or "") for p in all_projects(s)}
    seen = {str(r.get("warehouse_name") or "") for r in rows if r.get("warehouse_name")}
    return sorted(seen - known)


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
    try:
        with serialize_fetch(TABLE):                    # 同表串行（D9）
            client = client_factory()
            try:
                content = export(client, plan["ym"], ids)
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
            operator=operator)
        return {"ok": False, "degraded": True, "message": notice["message"],
                "excel_import_available": True, "ym": plan["ym"],
                "run_record_id": getattr(run, "id", None)}

    if not rows:
        run = save_run_record(s, **fetch_task.fetch_record_payload(
            object_desc=target, success=0, fail=0), operator=operator)
        return {"ok": False, "degraded": False, "empty": True, "ym": plan["ym"],
                "message": (f"{plan['ym']} 的导出里**一行明细都没有** ⇒ **未改动本地数据**"
                            "（不拿空结果去清已有数据）—— 请核对导出条件后再抓。"),
                "run_record_id": getattr(run, "id", None)}

    stats = upsert_month(s, ym=plan["ym"], rows=rows)
    unknown = unknown_warehouses(s, rows)
    run = save_run_record(s, **fetch_task.fetch_record_payload(
        object_desc=target, success=len(rows), fail=0), operator=operator)
    return {"ok": True, "degraded": False, "ym": plan["ym"], "rows": len(rows),
            "stats": stats, "unknown_warehouses": unknown,
            "run_record_id": getattr(run, "id", None)}


__all__ = ["TABLE", "SPEC_KEY", "CONFIRM_TOKEN", "KICK_WARNING",
           "build_plan", "project_ids", "unknown_warehouses", "run_fetch"]
