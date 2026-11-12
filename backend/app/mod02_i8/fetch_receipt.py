"""Read the public fields of a saved fetch receipt without re-evaluating business rules."""
import re

from app.mod02_i8.repository import run_record_out


def fetch_receipt(run) -> dict | None:
    if run.run_type != "fetch":
        return None
    detail = run.detail if isinstance(run.detail, dict) else {}
    target = run.target.strip()
    if detail.get("notice_fetch") or target.startswith("付款通知书 ") or re.fullmatch(r"\d{4}-\d{2}", target):
        source = "notices"
        scope = target.removeprefix("付款通知书 ")
        summary = {key: detail.get(key) for key in ("total", "created", "updated", "excluded")}
        if all(type(detail.get(key)) is int and detail[key] >= 0 for key in ("created", "updated")):
            summary["written"] = detail["created"] + detail["updated"]
        items = detail.get("unresolved")
        if detail.get("notice_fetch") and run.status in ("success", "partial"):
            summary["unsettled"] = run.fail_count
        item_keys = ("bill_no", "project_name", "doc_name", "reason")
        warning = ""
    else:
        source = next((name for prefix, name in (
            ("setl ", "settlement"), ("收发结存表", "settlement"),
            ("inv ", "inventory"), ("库存单据明细表", "inventory"),
        ) if target.startswith(prefix)), None)
        if source is None:
            return None
        scope = re.sub(r"^(?:setl |inv |收发结存表\s*|库存单据明细表\s*)", "", target)
        stats = detail.get("report_stats")
        stats = stats if isinstance(stats, dict) else {}
        preserved = "kept_manual" if source == "settlement" else "kept_with_adjustment"
        summary = {key: stats.get(key) for key in ("inserted", "updated", "deleted", preserved)}
        if run.status == "success":
            summary["total"] = run.success_count
        items = detail.get("promote_pending")
        recovery = detail.get("report_recovery")
        if isinstance(recovery, dict):
            summary.update({key: recovery.get(key) for key in ("promote", "create", "unsettled")})
        elif items and isinstance(items, list) and run.status == "success":
            summary["unsettled"] = len(items)
        item_keys = ("warehouse_name", "full_name", "owner_full_name", "reason")
        warning = detail.get("report_warning") or ""

    record = run_record_out(run)
    return {
        "id": record.id,
        "source": source,
        "status": "empty" if detail.get("report_empty") else record.status,
        "scope": scope,
        "started_at": record.started_at,
        "duration_seconds": record.duration_seconds,
        "summary": summary,
        "items": [{key: row.get(key) for key in item_keys} for row in items[:200] if isinstance(row, dict)]
        if isinstance(items, list) else None,
        "warning": warning,
        "error_message": record.error_message if record.status == "failed" else "",
    }
