"""再次导入合并规则（§4.2.7）的验收断言 —— `ACC-PAY-MERGE-001`。

`MOD-03` 能力 5（再次导入合并 / 越界提醒 / i8 撤单退出统计）此前无用例认领，2026-09-16 立此用例。
⚠️ `ACC-PAY-AMT-001` 只 cover「**不再产出**付款金额（源）」这一条，**不**覆盖合并规则本身。

口径出处：《说明书》§4.2.7（含"判据 = 留痕"与"越界只提醒不改数"）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.mod03_notice.domain import F_STAT_PAID, F_STAT_SETTLE, StatTrace
from app.mod03_notice.merge import PROTECTED, plan_merge
from tests.acc_plugin import acc


def _trace(notice_id: int, field: str, before: str, after: str) -> StatTrace:
    return StatTrace(
        notice_id=notice_id, field=field, before=Decimal(before), after=Decimal(after),
        changed_by="SCY980803", changed_at=datetime(2026, 9, 15, 10, 0),
    )


def _current(**kw) -> dict:
    base = {
        "id": 1, "ph_id": "P1", "bill_no": "B1", "bill_type": "material",
        "project_name": "甲项目", "approve_status": "已批", "doc_date": "2026-08-31",
        "biz_type": "付其他供应商款", "payee": "某供应商", "input_by": "王潜森",
        "amount_approved": Decimal("10000.00"),
        "stat_settle": Decimal("10000.00"), "stat_paid": Decimal("10000.00"),
        "category": "material", "excluded": False, "exclude_source": "",
        "i8_revoked": False, "revoked_joint": False, "ownership_id": 11,
        "fields": {"BillNo": "B1"},
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------- 源字段跟随


@acc("ACC-PAY-MERGE-001", "001-01")
def test_源字段跟随i8新值():
    cur = _current()
    inc = {"amount_approved": Decimal("12000.00"),
           "biz_type": "付设备租赁款", "doc_date": "2026-08-31"}
    plan = plan_merge(cur, inc, [], notice_id=1)
    assert plan.values["amount_approved"] == Decimal("12000.00")      # 跟随
    assert plan.values["biz_type"] == "付设备租赁款"                  # 跟随
    assert "doc_date" not in plan.values                              # 值没变 ⇒ 不写


@acc("ACC-PAY-MERGE-001", "001-02")
def test_统计金额未手改则跟随新审批金额():
    cur = _current()
    inc = {"amount_approved": Decimal("8000.00")}
    plan = plan_merge(cur, inc, [], notice_id=1)
    # 无留痕 ⇒ 两个统计字段都跟着调到 8000
    assert plan.values[F_STAT_SETTLE] == Decimal("8000.00")
    assert plan.values[F_STAT_PAID] == Decimal("8000.00")
    assert plan.alerts == []


@acc("ACC-PAY-MERGE-001", "001-03")
def test_统计金额手改过则保留人工值():
    cur = _current(stat_settle=Decimal("9000.00"), stat_paid=Decimal("9000.00"))
    traces = [_trace(1, F_STAT_SETTLE, "10000.00", "9000.00")]
    plan = plan_merge(cur, {"amount_approved": Decimal("8000.00")}, traces, notice_id=1)
    # 手改过的统计结算**保留 9000**（现值已是它 ⇒ 正确行为是"不动它"）；
    # 没手改的那个**跟随**新审批金额 ⇒ **两个字段各判各的**
    assert F_STAT_SETTLE not in plan.values
    assert plan.values[F_STAT_PAID] == Decimal("8000.00")


@acc("ACC-PAY-MERGE-001", "001-04")
def test_越界只提醒绝不代替用户改写():
    cur = _current(stat_settle=Decimal("9500.00"), stat_paid=Decimal("9500.00"))
    traces = [
        _trace(1, F_STAT_SETTLE, "10000.00", "9500.00"),
        _trace(1, F_STAT_PAID, "10000.00", "9500.00"),
    ]
    plan = plan_merge(cur, {"amount_approved": Decimal("8000.00")}, traces, notice_id=1)
    # **保留人工值**（"不动它"就是保留）—— 绝不自动下调
    assert F_STAT_SETTLE not in plan.values and F_STAT_PAID not in plan.values
    # 但必须挂提醒（提醒与"写不写"无关）
    assert len(plan.alerts) == 2
    assert "已超过新的审批金额" in plan.alerts[0] and "保留人工值" in plan.alerts[0]


@acc("ACC-PAY-MERGE-001", "001-05")
def test_审批金额没变就什么都不做():
    """⭐「**值没变就不动**」—— 审批金额没变 ⇒ **连重算都不做**（不是"重算后恰好值相同"）。

    ⚠️ 判据必须**盯住"不做重算"本身**：只断言 `changed is False` 是不够的
       —— 下层还有 `if not _same(current, new_value)` 这道闸，它会把"其实重算了"掩盖成"没写"
       （实测：把 `if not _same(approved_old, approved_new)` 改成 `if True` 后，
        原断言仍然通过 ⇒ 假绿）。
    """
    from app.mod03_notice import merge as M

    calls: list = []
    real = M.stat_value_on_reimport

    def _spy(**kw):
        calls.append(kw)
        return real(**kw)

    M.stat_value_on_reimport = _spy
    try:
        cur = _current()
        plan = M.plan_merge(cur, {"amount_approved": Decimal("10000.00")}, [], notice_id=1)
    finally:
        M.stat_value_on_reimport = real

    assert plan.changed is False and plan.alerts == []
    assert calls == [], f"审批金额没变 ⇒ 不该调用重算，实际调了 {len(calls)} 次"


@acc("ACC-PAY-MERGE-001", "001-06")
def test_审批金额调大时未手改值跟着涨():
    """这是"跟随"的应有结果（本就等于新审批金额），不是 bug。"""
    cur = _current()
    plan = plan_merge(cur, {"amount_approved": Decimal("15000.00")}, [], notice_id=1)
    assert plan.values[F_STAT_SETTLE] == Decimal("15000.00")
    assert plan.alerts == []          # 跟随不会越界 ⇒ 无提醒


# ---------------------------------------------------------------- 被保护的字段


@acc("ACC-PAY-MERGE-001", "001-07")
def test_分类剔除撤单归属一律不被覆盖():
    cur = _current(category="mechanical", excluded=True, exclude_source="manual",
                   i8_revoked=True, ownership_id=11)
    inc = {
        "amount_approved": Decimal("12000.00"),
        # 就算 incoming 里带了这些键（比如抓取侧算出来的），也**一个都不许写**
        "category": "material", "excluded": False, "exclude_source": "",
        "i8_revoked": False, "ownership_id": 99,
    }
    plan = plan_merge(cur, inc, [], notice_id=1)
    for key in PROTECTED:
        assert key not in plan.values, key
    # 但源字段照常跟随
    assert plan.values["amount_approved"] == Decimal("12000.00")


# ---------------------------------------------------------------- 新行的初始赋值


@acc("ACC-PAY-MERGE-001", "001-08")
def test_新行初始赋值含分类剔除与统计两金额初值():
    """§4.2.5：**新行**的统计结算金额 = 审批金额、统计付款金额 = 付款金额（源）。

    ⚠️ 少了这一步，新抓回来的行两个统计字段会是 0 ⇒ 欠款统计直接算错（真机联调时踩到过）。
    """
    from app.mod03_notice.classify import decide_placement
    from app.mod03_notice.merge import apply_placement_to_new

    incoming = {
        "ph_id": "P9", "biz_type": "付其他供应商款", "payee": "某公司",
        "amount_approved": Decimal("5000.00"),
    }
    values = apply_placement_to_new(decide_placement(incoming), incoming,
                                    paid_total=Decimal("4800.00"))
    assert values["category"] == "material"          # §4.2.3 第 ③ 支
    assert values["excluded"] is False and values["exclude_source"] == ""
    assert values[F_STAT_SETTLE] == Decimal("5000.00")     # = 审批金额
    assert values[F_STAT_PAID] == Decimal("4800.00")       # ⭐ = **已付金额**（流水汇总，§4.4.7）


@acc("ACC-PAY-MERGE-001", "001-09")
def test_新行命中剔除也照样给统计初值():
    """被剔除的行**仍然**要有统计初值 —— 剔除只是"不进日常统计"，不是"字段留空"。"""
    from app.mod03_notice.classify import decide_placement
    from app.mod03_notice.merge import apply_placement_to_new

    incoming = {
        "ph_id": "P8", "biz_type": "付劳务公司款", "payee": "某公司",
        "amount_approved": Decimal("300.00"),
    }
    values = apply_placement_to_new(decide_placement(incoming), incoming)
    assert values["excluded"] is True and values["exclude_source"] == "rule"
    assert values[F_STAT_SETTLE] == Decimal("300.00")
    assert values[F_STAT_PAID] == Decimal("0.00")          # 新单无流水 ⇒ 已付 = 0（§4.4.7）
