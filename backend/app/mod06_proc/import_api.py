"""`MOD-06` **过程资料历史导入** —— 前端壳用的 **JSON API**（口径主人 =《说明书》§5.2.5 ①②）。

⚠️ **为什么有它**（`TAIL-27` · `§19` 四个暂留件收口）：本页原先只有服务端渲染页 ＋ 三条 PRG
   （`import_view.py` ＋ `router.py` 的 `/m06/import*`）⇒ 壳里**零入口**，那页删不得。
   本件把三步原样搬成 JSON；⛔ **判定与落库一行没变** —— 解析在 `importer.py`、
   写历史段在 `importer.commit`、候选项目在 `service.projects_of`（唯一出口）。
⚠️ **预览不写库**：与付款域导入**共用同一份载具**（`core.preview_store`，`§5.2.5 ②` 明写「复用同一套」）。
⚠️ ⛔ **机械 6 列不导入**（全段手录，§5.2.5 ③）—— 解析结果里显式列出被忽略的机械列给人看。
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, File, Form, UploadFile

from app.core import preview_store
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod06_proc import importer
from app.mod06_proc import domain as D
from app.mod06_proc.service import build_import_data

router = APIRouter(tags=["mod06-import-api"])


def _data_of(warehouse: str = "") -> dict:
    """历史导入页的**页面数据**（项目候选 / 当前项目 / 截止核算月 / 已登记批次）。"""
    with session_scope() as s:
        data = build_import_data(s, warehouse=str(warehouse or ""))
    return {
        "projects": list(data["projects"]),
        "warehouse": str(data["warehouse"] or ""),
        "cutoff_ym": str(data["cutoff_ym"] or ""),
        "batches": [str(getattr(b, "batch_no", "") or "") for b in data["batches"]],
    }


def _payload(plan: importer.ImportPlan, *, warehouse: str) -> dict:
    """预览结果 → 可暂存的纯数据（**不含密钥**；`batch` 在预览这一刻定死）。"""
    return {
        "warehouse": warehouse,
        "batch": importer.next_batch(),
        "rows": [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in row.items()}
                 for row in plan.rows],
        "anomalies": plan.anomalies,
        "ignored_mech": plan.ignored_mech,
        "unknown_headers": plan.unknown_headers,
        "default_cutoff": plan.default_cutoff,
    }


def _plan_of(payload: dict) -> importer.ImportPlan:
    """暂存结果 → `ImportPlan`（确认时重建；**不重新解析文件**）。"""
    plan = importer.ImportPlan(
        anomalies=list(payload.get("anomalies") or []),
        ignored_mech=list(payload.get("ignored_mech") or []),
        unknown_headers=list(payload.get("unknown_headers") or []),
    )
    for row in payload.get("rows") or []:
        plan.rows.append({k: (Decimal(str(v)) if k != "ym" else str(v)) for k, v in row.items()})
    return plan


def _preview_of(plan: importer.ImportPlan, *, warehouse: str) -> dict:
    """预览块（**与旧页同口径**：月份清单 ＋ 异常行 ＋ 列提示 ＋ 默认截止月；行只给前 300）。"""
    return {
        "warehouse": warehouse,
        "writable": plan.writable,
        "months": list(plan.months),
        "anomalies": list(plan.anomalies),
        "ignored_mech": list(plan.ignored_mech),
        "unknown_headers": list(plan.unknown_headers),
        "default_cutoff": str(plan.default_cutoff or ""),
        "rows": [{k: (f"{v:.2f}" if isinstance(v, Decimal) else v) for k, v in row.items()}
                 for row in plan.rows[:300]],
    }


@router.get("/api/m06/import/data")
def api_data(pj: str = "") -> dict:
    """历史导入页的取数口（壳 `V.m06imp` 的**唯一数据源**）。"""
    return {"ok": True, **_data_of(pj)}


@router.get("/api/m06/import/meta")
def api_meta() -> dict:
    """列说明那两行（**材料列清单从域口径出**，⛔ 壳里不许再抄一份）。"""
    mats = [c["label"] for c in D.PROC_COLUMNS if c["key"] in D.MATERIAL_KEYS]
    return {"ok": True, "material_labels": mats, "mech_labels": list(D.MECH_COLUMNS)}


@router.post("/api/m06/import/parse")
async def api_parse(file: UploadFile = File(...), pj: str = Form("")) -> dict:
    """解析上传的 `.xlsx` → **预览**（⚠️ **一个字节都不写库**）。"""
    try:
        plan = importer.parse_sheet(await file.read())
        data = _data_of(pj)
        if not data["warehouse"]:
            raise MustReportError("还没有可导入的项目 —— 先在「库存单据」页抓一次库存单据明细。")
        token = preview_store.save(_payload(plan, warehouse=data["warehouse"]))
        return {"ok": True, "token": token, "data": data,
                "preview": _preview_of(plan, warehouse=data["warehouse"])}
    except MustReportError as exc:
        return {"ok": False, "message": str(exc), "data": _data_of(pj)}
    except Exception as exc:                                    # noqa: BLE001
        return {"ok": False, "message": f"解析失败：{type(exc).__name__}: {exc}",
                "data": _data_of(pj)}


@router.post("/api/m06/import/confirm")
def api_confirm(body: dict | None = None) -> dict:
    """凭 token 取回解析结果 → **写历史段 ＋ 记批次** → 给**核对报告**。"""
    try:
        payload = preview_store.load(str((body or {}).get("token") or ""))
        plan = _plan_of(payload)
        warehouse = str((body or {}).get("pj") or payload.get("warehouse") or "")
        cutoff = str((body or {}).get("cutoff_ym") or "")
        batch = str(payload.get("batch") or importer.next_batch())
        with session_scope() as s:
            out = importer.commit(s, plan, warehouse=warehouse, batch=batch,
                                  operator=current_operator(), cutoff_ym=cutoff)
            report = importer.check_report(s, warehouse=warehouse, batch_no=out["batch"],
                                           cutoff_ym=out["cutoff_ym"])
        return {
            "ok": True,
            "message": f"已导入 {out['rows']} 个月（批次 {out['batch']}）· 截止核算月 "
                       f"{out['cutoff_ym'] or '（空）'} —— 历史段材料列改用本批快照；正式段未受影响",
            "batch": str(out["batch"]), "report": report, "data": _data_of(warehouse),
        }
    except MustReportError as exc:
        return {"ok": False, "message": str(exc), "data": _data_of()}
    except Exception as exc:                                    # noqa: BLE001
        return {"ok": False, "message": f"导入失败：{type(exc).__name__}: {exc}", "data": _data_of()}


@router.post("/api/m06/import/rollback")
def api_rollback(body: dict | None = None) -> dict:
    """**整批回滚**（置 `rolled_back` ＋ 留痕，**不物理删**）→ 再给核对报告。"""
    try:
        batch = str((body or {}).get("batch") or "")
        warehouse = str((body or {}).get("pj") or "")
        with session_scope() as s:
            count = importer.rollback(s, batch_no=batch)
            data = build_import_data(s, warehouse=warehouse)
            report = importer.check_report(s, warehouse=data["warehouse"], batch_no=batch,
                                           cutoff_ym=data["cutoff_ym"])
        return {
            "ok": True,
            "message": f"批次 {batch} 已整批回滚：{count} 行不再计入历史段（留痕、未物理删）"
                       "—— 可以重新上传修正后的文件",
            "report": report, "data": _data_of(warehouse),
        }
    except MustReportError as exc:
        return {"ok": False, "message": str(exc), "data": _data_of()}
    except Exception as exc:                                    # noqa: BLE001
        return {"ok": False, "message": f"回滚失败：{type(exc).__name__}: {exc}", "data": _data_of()}


__all__ = ["router"]
