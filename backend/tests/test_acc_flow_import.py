"""正常付款、撤销后的统计重算及三金额结构；原历史导入测试已归档。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.mod03_notice.models import NoticeStatLog, PaymentNotice
from app.mod05_flow import repository as repo
from app.mod05_flow.domain import effective_total
from app.mod05_flow.models import (
    FLOW_EFFECTIVE,
    FLOW_REVOKED,
    FLOW_SOURCE_IMPORTED,
    FLOW_SOURCE_MANUAL,
    PaymentFlow,
    PAY_METHODS,
)
from tests.m03_action_helpers import FakeWriteSession, _notice

APPROVED = Decimal("10000.00")




def _session(notices, flows=(), traces=()) -> FakeWriteSession:
    return FakeWriteSession({PaymentNotice: list(notices), PaymentFlow: list(flows),
                             NoticeStatLog: list(traces)})


# ============================================================ ACC-PAY-STAT-002


def test_统计付款金额默认值等于已付金额():
    s = _session([_notice(7, stat_paid=Decimal("0.00"))],
                 flows=[PaymentFlow(id=1, notice_id=7, amount=Decimal("300.00"),
                                    status=FLOW_EFFECTIVE)])
    assert repo.sync_stat_paid(s, 7) == Decimal("300.00")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("300.00")


def test_付款后自动重算():
    s = _session([_notice(7, stat_paid=Decimal("0.00"))])
    repo.create_flow(s, notice_id=7, project_id=None, amount="250.00", pay_date="2026-09-03")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("250.00")


def test_撤销付款后自动重算_回退():
    s = _session([_notice(7, stat_paid=Decimal("0.00"))])
    flow = repo.create_flow(s, notice_id=7, project_id=None, amount="250.00",
                            pay_date="2026-09-03")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("250.00")
    repo.revoke(s, flow, reason="记错了", changed_by="科室用户")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("0.00")


def test_手改过的行不被自动重算覆盖():
    trace = NoticeStatLog(id=1, notice_id=7, field="stat_paid",
                          before_amount=Decimal("0.00"), after_amount=Decimal("6000.00"),
                          changed_by="科室用户", changed_at=datetime(2026, 9, 10, 9, 0, 0))
    s = _session([_notice(7, stat_paid=Decimal("6000.00"))], traces=[trace])
    repo.create_flow(s, notice_id=7, project_id=None, amount="250.00", pay_date="2026-09-03")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("6000.00")   # 人工值原样保留


def test_实付超过审批金额照实写入不封顶():
    """claim 是**两半**：「实付合计 > 审批金额 ⇒ **照实写入** ＋ **该单挂提醒**（不得静默封顶、
    不得改写）」。

    ⚠️⚠️ **2026-09-21 补上第二半**：本用例原先**只断言了"照实写入"**（docstring 自己也写着
       "本用例只保证导入/事实路径不被封顶"）⇒ 而「**挂提醒**」当时**根本没实现**
       （全仓 `超付` 只有 `sync_stat_paid` 里一句注释"由调用侧挂提醒"，调用侧从没挂过）。
       ⇒ 判据绿着、功能缺着 —— 一条**假绿**，也是 `chain_audit` 那条红一直没被修掉的原因。
    ⚠️ 与 §4.4.4「付款动作禁止超付」不冲突：那条约束**动作**，事实不得篡改。
    """
    s = _session([_notice(7, stat_paid=Decimal("0.00"), amount_approved=APPROVED)])
    repo.create_flow(s, notice_id=7, project_id=None, amount="12000.00", pay_date="2026-09-03")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("12000.00")   # 照实、不封顶
    # 而**付款动作**那条路仍然禁止超付（本用例只保证导入/事实路径不被封顶）
    assert effective_total([{"status": FLOW_EFFECTIVE, "amount": Decimal("12000.00")}]) == Decimal("12000.00")
    _assert_overpay_reminder()


def _assert_overpay_reminder() -> None:
    """⭐ `002-06` 的后半句「**该单挂提醒**」—— 判定在后端、标记在壳，两头都要在。

    ⚠️ **`>` 不是 `>=`**：实付 == 审批金额 = 付清（§4.4.2 只有两态），**不是超付**。
    ⚠️ 判定做成**派生属性、不落库**（同 `pay_status`）：做成字段就给"字段值与事实不一致"留口子。
    """
    from app.mod03_notice.list_view import NoticeRow

    def over(paid: str, approved: str) -> bool:
        return NoticeRow(notice_id=1, amount_approved=Decimal(approved),
                         amount_paid=Decimal(paid)).is_overpaid

    assert over("12000.00", "10000.00") is True, "实付 > 审批 ⇒ 必须判超付（否则没人被提醒）"
    assert over("10000.00", "10000.00") is False, "实付 == 审批 = **付清**，不是超付（`>` 不是 `>=`）"
    assert over("8000.00", "10000.00") is False, "未超付被误判 ⇒ 满屏假提醒"

    # 后端把标志交给壳（⛔ 壳不许自己算 `amount_paid > amount_approved`）
    from app.mod03_notice.notice_api_router import _api_item
    row = NoticeRow(notice_id=1, amount_approved=Decimal("10000.00"), amount_paid=Decimal("12000.00"))
    assert _api_item({"notice_id": 1, "_row": row})["is_overpaid"] is True, \
        "API 没把「超付」交给壳 ⇒ 界面上永远没有那个提醒"




# ============================================================ ACC-PAY-AMT-001


def test_金额字段结构是三金额且付款金额为派生列():
    from app.mod03_notice.domain import SOURCE_FIELDS, STAT_FIELDS, THREE_AMOUNT_FIELDS, derived_pay_amount

    assert len(THREE_AMOUNT_FIELDS) == 3
    assert SOURCE_FIELDS == ("amount_approved",)              # ⭐ 唯一 i8 源字段
    assert STAT_FIELDS == ("stat_settle", "stat_paid")
    assert not hasattr(PaymentNotice, "pay_amount_src")       # 原字段**已取消**
    assert derived_pay_amount(APPROVED, Decimal("8000.00")) == Decimal("2000.00")
    cols = {c.name for c in PaymentNotice.__table__.columns}
    assert "pay_amount_src" not in cols and "stat_paid" in cols


def test_抓取映射不再产出付款金额源字段():
    from app.mod02_i8.notice_source import _map_record

    mapped = _map_record({
        "PhId": "3700000000000001", "BillNo": "FKTZS2026090466", "BillDt": "2026-09-03",
        "ApproveAmt": "12800.00", "ApplyAmt": "12800.00", "AppStatus": "1",
        "PhidRecPayType_EXName": "材料",
    })
    assert "pay_amount_src" not in mapped
    assert mapped["amount_approved"] == Decimal("12800.00")
    assert mapped["amount_paid"] == 0.0                       # 已付金额由流水派生（i8 不提供）
