"""`MOD-05` 历史付款流水导入 —— 路由（**§4.4.6**）。

⚠️ 薄层：解析 / 校验在 `importer.py`，落库与重算在 `repository.py`（**重算唯一出口**）。
⚠️ **预览不写库**：解析结果暂存到 `artifacts/import_preview/<token>.json`，
   确认时凭 token 取回 —— 预览阶段**一个字节都不落库**。
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import HTMLResponse

from app.core import preview_store
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod05_flow import importer, repository as repo
from app.mod05_flow.import_view import render_import_page

router = APIRouter(tags=["mod05-import"])


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


# ---------------------------------------------------------------- 页面


@router.get("/m05/import", response_class=HTMLResponse)
def page(message: str = "", kind: str = "ok") -> HTMLResponse:
    """导入页（三步走 ＋ 列说明）。"""
    return HTMLResponse(render_import_page(message=message, kind=kind))


# ---------------------------------------------------------------- ① 解析并预览（不写库）


@router.post("/m05/import/preview", response_class=HTMLResponse)
async def preview(file: UploadFile = File(...)) -> HTMLResponse:
    """解析上传的 `.xlsx` → **预览四块**（⚠️ **不写库**）。"""
    try:
        data = await file.read()
        raw = importer.read_workbook(data)
        plan = importer.parse_rows(raw)
        with session_scope() as s:
            plan = importer.split_by_match(plan, _known(s))
        token = preview_store.save(_payload(plan))
        preview_payload = {
            "writable": plan.writable,
            "skipped_header": plan.skipped_header,
            "unknown_methods": plan.unknown_methods,
            "anomalies": plan.anomalies,
            "unmatched": plan.unmatched,
            "rows": [{"bill_no": r.bill_no, "amount": f"{r.amount:.2f}", "pay_date": r.pay_date,
                      "pay_method": r.pay_method, "remark": r.remark} for r in plan.rows],
        }
        return HTMLResponse(render_import_page(preview=preview_payload, token=token))
    except MustReportError as exc:
        return HTMLResponse(render_import_page(message=exc.message, kind="err"))
    except Exception as exc:                              # noqa: BLE001
        return HTMLResponse(render_import_page(
            message=f"解析失败：{type(exc).__name__}: {exc}", kind="err"))


# ---------------------------------------------------------------- ② 确认导入（写库 ＋ 重算）


@router.post("/m05/import/confirm", response_class=HTMLResponse)
def confirm(token: str = Form(...)) -> HTMLResponse:
    """凭 token 取回解析结果 → **落库**（记批次）→ 给**核对报告**。"""
    try:
        payload = preview_store.load(token)
        plan = _plan_of(payload)
        batch = str(payload.get("batch") or importer.next_batch())
        with session_scope() as s:
            out = importer.commit(s, plan, batch=batch, operator=current_operator())
            report = importer.check_report(s, batch)
        return HTMLResponse(render_import_page(
            message=f"已导入 {out['written']} 条（批次 {out['batch']}）—— "
                    f"「统计付款金额」已按已付金额重算（§4.4.7）",
            kind="ok", report=report))
    except MustReportError as exc:
        return HTMLResponse(render_import_page(message=exc.message, kind="err"))
    except Exception as exc:                              # noqa: BLE001
        return HTMLResponse(render_import_page(
            message=f"导入失败：{type(exc).__name__}: {exc}", kind="err"))


# ---------------------------------------------------------------- ③ 整批回滚


@router.post("/m05/import/rollback", response_class=HTMLResponse)
def rollback(batch: str = Form(...)) -> HTMLResponse:
    """**整批回滚**（置撤销 ＋ 留痕，**不物理删**）→ 再给核对报告。"""
    try:
        with session_scope() as s:
            out = importer.rollback(s, batch, changed_by=current_operator())
            report = importer.check_report(s, batch)
        return HTMLResponse(render_import_page(
            message=f"批次 {out['batch']} 已整批回滚：撤销 {out['revoked']} 条"
                    f"（该批另有 {out['kept']} 条本就已撤销）—— 可以重新上传修正后的文件",
            kind="wn", report=report))
    except MustReportError as exc:
        return HTMLResponse(render_import_page(message=exc.message, kind="err"))
    except Exception as exc:                              # noqa: BLE001
        return HTMLResponse(render_import_page(
            message=f"回滚失败：{type(exc).__name__}: {exc}", kind="err"))


__all__ = ["router"]
