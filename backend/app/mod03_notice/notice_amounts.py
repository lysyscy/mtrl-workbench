"""Notice amount edits own current facts; callers never round-trip a full manual row."""
from app.core.errors import MustReportError
from app.mod03_notice import repository as repo
from app.mod03_notice.notice_actions import apply_stat_change
from app.mod03_notice.notice_manual_actions import assert_manual_editable, manual_amounts


def save_amount(session, notice_id: int, *, field: str, value: object, changed_by: str) -> dict:
    """Change one amount, preserving every unrelated fact and the existing stat trace rules."""
    receipt = {"ok": True, "notice_id": notice_id, "field": field}
    if field in ("stat_settle", "stat_paid"):
        trace, message = apply_stat_change(session, notice_id, field=field, value=value,
                                           changed_by=changed_by)
        receipt.update(changed=trace is not None, message=message)
        if trace is not None:
            receipt.update(before=str(trace.before), after=str(trace.after), label=trace.label)
        return receipt
    if field != "amount_approved":
        raise MustReportError("请选择审批金额、统计结算金额或统计付款金额")

    # Refresh under the same row lock used by payment/stat changes before checking ceilings.
    row = repo.get_notice(session, notice_id, with_for_update={"key_share": True}, populate_existing=True)
    if row is None:
        raise MustReportError(f"通知书 {notice_id} 不存在")
    assert_manual_editable(row)
    approved, _, _ = manual_amounts(value, row.stat_settle, row.stat_paid)
    before = row.amount_approved
    changed = before != approved
    if changed:
        repo.update_manual_notice(session, row, {"amount_approved": approved})
    return {**receipt, "changed": changed, "before": str(before), "after": str(approved),
            "label": "审批金额", "message": f"审批金额已由 {before} 改为 {approved}" if changed else "审批金额没有变化"}
