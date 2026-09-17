"""`MOD-08` 库存单据明细 · **抓取编排**（`API-03`：导出 → 解析 → 幂等落库 → 执行记录）。

依据：
- 《说明书》**§3.4**（导出条件 = 核算年月 + 项目）· **§9.2**（报表类按核算年月；**抓取只允许单月**）
  · **§3.6**（接口不可用 ⇒ **降级为手动 Excel 导入**并**显式说明**）· **§9.5**（导入幂等）
- 《技术栈选型分析》**§9.8**（接口形态：起止年月四个独立值 · `xmid` · `reportName=null`）
- 用户裁定 **D9**：**抓取一律手动**（无定时）· **失败不得自动重试登录** · 抓前须**二次确认并告知会强踢**

⛔ 本模块**不落「是否作废」**（`NG-06`）—— 由 `importer` 在解析阶段丢弃。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod02_i8 import fetch_task, report_export
from app.mod02_i8.client import I8Client, serialize_fetch
from app.mod02_i8.repository import save_run_record
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
    """导出用的项目 id 串（**由本地项目档案提供**，§9.8）—— 空则报错，不臆造。"""
    from app.mod01_projects.repository import all_projects

    ids = [str(p.phid) for p in all_projects(s) if str(getattr(p, "phid", "") or "").strip()]
    if not ids:
        raise MustReportError(
            "本地项目档案里没有可用 phid（i8 项目编号）⇒ 无法按项目导出。"
            "请先「同步常用项目列表」（API-06）建档。"
        )
    return ",".join(ids)


def group_by_scope(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """按「**核算年月 ＋ 仓库名**」分组（幂等刷新的范围）。"""
    out: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (str(row.get("ym") or ""), str(row.get("warehouse_name") or ""))
        out.setdefault(key, []).append(row)
    return out


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

    ⚠️ 失败 ⇒ **降级为手动 Excel 导入并显式说明**（§3.6），**绝不自动重试登录**（D9）。
    ⚠️ 只要走到网络之前就失败的（未确认 / 非单月 / 无 phid），**不写执行记录**也**不降级**（那是用法错误）。
    """
    plan = build_plan(year_month)                 # 非单月 ⇒ 这里就抛
    if not confirmed:
        raise MustReportError(f"抓取前必须二次确认：{KICK_WARNING}")

    ids = project_ids(s)
    operator = operator or current_operator()
    client_factory = client_factory or (lambda: I8Client(allow_kick=True))
    export = export or (lambda c, ym, ids_: report_export.export(
        c, spec_key=SPEC_KEY, year_month=ym, proj_ids=ids_))

    target = f"{SPEC_KEY} {plan['ym']}（{len(ids.split(','))} 个项目）"
    try:
        with serialize_fetch(TABLE):             # 同表串行（D9）
            client = client_factory()
            try:
                content = export(client, plan["ym"], ids)
            finally:
                close = getattr(client, "close", None)
                if callable(close):
                    close()
        rows = importer.parse_rows(content)
    except Exception as exc:                      # noqa: BLE001 —— 一律降级，不静默
        notice = fetch_task.degrade_to_excel(exc)
        run = save_run_record(s, **fetch_task.fetch_record_payload(
            object_desc=target, success=0, fail=1,          # fail=1 ⇒ status=failed（这一批失败）
            error_message=f"{type(exc).__name__}: {exc}"),
            operator=operator)
        return {"ok": False, "degraded": True, "message": notice["message"],
                "excel_import_available": True, "run_record_id": getattr(run, "id", None)}

    stats = {"inserted": 0, "updated": 0, "deleted": 0, "kept_with_adjustment": 0}
    for (ym, warehouse), group in group_by_scope(rows).items():
        part = upsert_details(s, ym=ym, warehouse=warehouse, rows=group)
        for k in stats:
            stats[k] += part[k]

    run = save_run_record(s, **fetch_task.fetch_record_payload(
        object_desc=target, success=len(rows), fail=0), operator=operator)
    return {"ok": True, "degraded": False, "ym": plan["ym"], "rows": len(rows),
            "stats": stats, "run_record_id": getattr(run, "id", None)}


__all__ = ["TABLE", "SPEC_KEY", "CONFIRM_TOKEN", "KICK_WARNING",
           "build_plan", "project_ids", "group_by_scope", "run_fetch"]
