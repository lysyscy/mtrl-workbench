"""`MOD-05` **历史付款流水导入** —— 前端壳用的 **JSON API**（口径主人 =《说明书》§4.4.6 / §4.4.7）。

⚠️ **为什么有它**（`TAIL-27` · `§19` 四个暂留件收口）：本页的能力原先**只有服务端渲染页**
   （`import_view.py` ＋ `import_router.py` 的三个 PRG）有 —— 壳里**零入口** ⇒ 那页删不得。
   本件把三步（**① 列说明 → ② 预览 → ③ 确认导入 ＋ 核对报告**）原样搬成 JSON：
   ⛔ **判定与落库一行没变** —— 解析在 `importer.py`、落库与重算在 `repository.py`（唯一出口），
   本层只做编排 ＋ 转形。
⚠️ **预览不写库**：解析结果暂存到 `core.preview_store`（`artifacts/import_preview/<token>.json`），
   确认时凭 token 取回 —— 预览阶段**一个字节都不落库**（`ACC-FLOW-IMPORT-001/001-04`）。
⚠️ 恒 **HTTP 200 ＋ `ok` 标志**：解析失败 / 预览过期 / 未匹配都是**可预期的结果**，
   后端的**中文原因**要原样交到界面上（⛔ 不许变成 `HTTP 400` 一句英文）。
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, File, UploadFile

from app.core import preview_store
from app.core.db import session_scope
from app.core.identity import current_operator
from app.mod05_flow import importer, repository as repo

router = APIRouter(tags=["mod05-import-api"])


def _known(s) -> dict[str, int]:
    """`单据号 -> notice_id`（精确匹配用；只读，故**预览阶段也安全**）。"""
    return {str(n.bill_no or "").strip(): int(n.id)
            for n in repo.notice_rows(s) if str(n.bill_no or "").strip()}


def _payload(plan: importer.ImportPlan) -> dict:
    """预览结果 → 可暂存的纯数据（**不含密钥**；`batch` 在预览这一刻定死，确认时沿用）。"""
    return {
        "batch": importer.next_batch(),
        "skipped_header": plan.skipped_header,
        "unknown_methods": plan.unknown_methods,
        "anomalies": plan.anomalies,
        "unmatched": plan.unmatched,
        "rows": [{"line": r.line, "bill_no": r.bill_no, "amount": str(r.amount),
                  "pay_date": r.pay_date, "pay_method": r.pay_method, "remark": r.remark,
                  "notice_id": r.notice_id} for r in plan.rows],
    }


def _plan_of(payload: dict) -> importer.ImportPlan:
    """暂存结果 → `ImportPlan`（确认时重建；**不重新解析文件**）。"""
    plan = importer.ImportPlan(
        skipped_header=payload.get("skipped_header", False),
        unknown_methods=list(payload.get("unknown_methods") or []),
        anomalies=list(payload.get("anomalies") or []),
        unmatched=list(payload.get("unmatched") or []),
    )
    for r in payload.get("rows") or []:
        plan.rows.append(importer.ParsedRow(
            line=int(r["line"]), bill_no=str(r["bill_no"]),
            amount=Decimal(str(r["amount"])), pay_date=str(r["pay_date"]),
            pay_method=str(r.get("pay_method") or ""), remark=str(r.get("remark") or ""),
            notice_id=int(r.get("notice_id") or 0),
        ))
    return plan


def preview_of(plan: importer.ImportPlan) -> dict:
    """预览四块（`ACC-FLOW-IMPORT-001/001-04`：将写入 / 未匹配 / 异常 / 未识别付款方式）。

    ⚠️ 行只给前 **300** 行（与旧页同口径）：预览是给人**过目**的，不是数据导出 ——
       真正的全量已随 token 暂存，确认时按原样落库。
    """
    return {
        "writable": plan.writable,
        "skipped_header": plan.skipped_header,
        "unknown_methods": list(plan.unknown_methods),
        "anomalies": list(plan.anomalies),
        "unmatched": list(plan.unmatched),
        "rows": [{"bill_no": r.bill_no, "amount": f"{r.amount:.2f}", "pay_date": r.pay_date,
                  "pay_method": r.pay_method, "remark": r.remark} for r in plan.rows[:300]],
    }


@router.get("/api/m05/import/meta")
def api_meta() -> dict:
    """列契约（A–E 逐列提示什么）＋ 行数上限 —— 壳侧「① 列说明」那块的**唯一数据源**。

    ⚠️ 契约本尊 = `importer.COLUMNS`（§4.4.6 的固定列序）⇒ ⛔ 壳里不许再抄一份列名。
    """
    return {"ok": True, "columns": [[str(a), str(b), bool(c)] for a, b, c in importer.COLUMNS],
            "max_rows": int(importer.MAX_ROWS)}


@router.post("/api/m05/import/parse")
async def api_parse(file: UploadFile = File(...)) -> dict:
    """解析上传的 `.xlsx` → **预览四块**（⚠️ **不写库**）。"""
    try:
        raw = importer.read_workbook(await file.read())
        plan = importer.parse_rows(raw)
        with session_scope() as s:
            plan = importer.split_by_match(plan, _known(s))
        token = preview_store.save(_payload(plan))
        return {"ok": True, "token": token, "preview": preview_of(plan)}
    except Exception as exc:                              # noqa: BLE001
        from app.core.errors import MustReportError

        why = exc.message if isinstance(exc, MustReportError) else f"{type(exc).__name__}: {exc}"
        return {"ok": False, "message": f"解析失败：{why}"}


@router.post("/api/m05/import/confirm")
def api_confirm(body: dict | None = None) -> dict:
    """凭 token 取回解析结果 → **落库**（记批次）→ 给**核对报告**（§4.4.6，含超付单列）。"""
    from app.core.errors import MustReportError

    try:
        token = str((body or {}).get("token") or "")
        payload = preview_store.load(token)
        plan = _plan_of(payload)
        batch = str(payload.get("batch") or importer.next_batch())
        with session_scope() as s:
            out = importer.commit(s, plan, batch=batch, operator=current_operator())
            report = importer.check_report(s, out["batch"])
        return {
            "ok": True,
            "message": f"已导入 {out['written']} 条（批次 {out['batch']}）—— "
                       "「统计付款金额」已按已付金额重算（§4.4.7）",
            "written": int(out["written"]), "batch": str(out["batch"]), "report": report,
        }
    except MustReportError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:                              # noqa: BLE001
        return {"ok": False, "message": f"导入失败：{type(exc).__name__}: {exc}"}


@router.post("/api/m05/import/rollback")
def api_rollback(body: dict | None = None) -> dict:
    """**整批回滚**（置撤销 ＋ 留痕，**不物理删**）→ 再给核对报告。"""
    from app.core.errors import MustReportError

    try:
        batch = str((body or {}).get("batch") or "")
        with session_scope() as s:
            out = importer.rollback(s, batch, changed_by=current_operator())
            report = importer.check_report(s, out["batch"])
        return {
            "ok": True,
            "message": f"批次 {out['batch']} 已整批回滚：撤销 {out['revoked']} 条"
                       f"（该批另有 {out['kept']} 条本就已撤销）—— 可以重新上传修正后的文件",
            "revoked": int(out["revoked"]), "batch": str(out["batch"]), "report": report,
        }
    except MustReportError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:                              # noqa: BLE001
        return {"ok": False, "message": f"回滚失败：{type(exc).__name__}: {exc}"}


__all__ = ["router", "preview_of", "_known", "_payload", "_plan_of"]
