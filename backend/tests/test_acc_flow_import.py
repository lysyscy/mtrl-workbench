"""历史付款流水导入（§4.4.6）＋「统计付款金额」重算（§4.4.7）—— 离线自检（**不连库**）。

对应判据：
- `ACC-FLOW-IMPORT-001`（解析 / 校验 / **未匹配必报** / **落库前预览**）
- `ACC-FLOW-IMPORT-002`（一条一笔 · 来源可辨 · **付款方式可空不兜底** · 备注）
- `ACC-FLOW-IMPORT-003`（**幂等**：同批先整批回滚再写 ＋ **核对报告**）
- `ACC-PAY-STAT-002`（默认值 = 已付金额 · 付款/撤销/导入后重算 · 手改保留 · 超付照实）
- `ACC-PAY-AMT-001`（**三金额**结构；原「付款金额（源）」已取消）
"""

from __future__ import annotations

import inspect
from datetime import date, datetime
from decimal import Decimal

from app.mod03_notice.models import NoticeStatLog, PaymentNotice
from app.mod05_flow import importer, repository as repo
from app.mod05_flow.domain import effective_total
from app.mod05_flow.models import (
    FLOW_EFFECTIVE,
    FLOW_REVOKED,
    FLOW_SOURCE_IMPORTED,
    FLOW_SOURCE_MANUAL,
    PaymentFlow,
    PAY_METHODS,
)
from tests.acc_plugin import acc
from tests.m04_helpers import FakeSession
from tests.m03_action_helpers import FakeWriteSession, _notice

APPROVED = Decimal("10000.00")


def _rows(*rows) -> list[list]:
    return [list(r) for r in rows]


# ============================================================ ACC-FLOW-IMPORT-001


@acc("ACC-FLOW-IMPORT-001", "001-01")
def test_按列位置解析并自动跳过表头():
    """A 单据号 · B 付款金额 · C 付款时间 · D 付款方式 · E 备注 —— **按位置取**。"""
    plan = importer.parse_rows(_rows(
        ["单据号", "付款金额", "付款时间", "付款方式", "备注"],          # 表头
        ["FKTZS2026090466", 12800, date(2026, 9, 3), "现汇", "首款"],
    ))
    assert plan.skipped_header is True
    assert plan.writable == 1
    r = plan.rows[0]
    assert (r.bill_no, r.amount, r.pay_date, r.pay_method, r.remark) == (
        "FKTZS2026090466", Decimal("12800.00"), "2026-09-03", "现汇", "首款")


@acc("ACC-FLOW-IMPORT-001", "001-02")
def test_单据号本地不存在必须列入未匹配清单不得静默丢弃():
    plan = importer.parse_rows(_rows(
        ["FKTZS2026090466", "100.00", "2026-09-03", "", ""],
        ["FKTZS9999999999", "200.00", "2026-09-03", "", ""],
    ))
    out = importer.split_by_match(plan, {"FKTZS2026090466": 7})
    assert [r.bill_no for r in out.rows] == ["FKTZS2026090466"]
    assert out.rows[0].notice_id == 7
    assert [u["bill_no"] for u in out.unmatched] == ["FKTZS9999999999"]


@acc("ACC-FLOW-IMPORT-001", "001-03")
def test_非法行进异常清单且不入库():
    plan = importer.parse_rows(_rows(
        ["FKTZS2026090466", "0", "2026-09-03", "", ""],          # 金额必须 > 0
        ["FKTZS2026090465", "100", "不是日期", "", ""],           # 日期不可解析
        ["", "100", "2026-09-03", "", ""],                       # 单据号为空
        ["FKTZS2026090464", "100", "2026-09-03", "", ""],        # 唯一合法行
    ))
    assert plan.writable == 1 and plan.rows[0].bill_no == "FKTZS2026090464"
    assert len(plan.anomalies) == 3
    assert all(a["reason"] for a in plan.anomalies)


@acc("ACC-FLOW-IMPORT-001", "001-04")
def test_解析与预览是纯函数_只有提交才碰会话():
    """**落库前必须预览 ⇒ 预览阶段不得写库**：解析 / 匹配这两个阶段**不接受会话参数**。

    （结构不变式：`importer` 里只有 `commit` / `rollback` / `check_report` 接会话。）
    """
    for fn in (importer.parse_rows, importer.split_by_match, importer.normalize_method,
               importer.parse_amount, importer.parse_date):
        names = set(inspect.signature(fn).parameters)
        assert not (names & {"s", "session"}), f"{fn.__name__} 不该接触会话"
    # 预览页必须把「将写入 / 未匹配 / 异常 / 未识别付款方式」四块都显示出来
    from app.mod05_flow.import_view import render_import_page

    plan = importer.split_by_match(
        importer.parse_rows(_rows(
            ["FKTZS2026090466", "100.00", "2026-09-03", "电汇", ""],
            ["FKTZS9999999999", "200.00", "2026-09-03", "", ""],
            ["FKTZS2026090465", "-1", "2026-09-03", "", ""],
        )), {"FKTZS2026090466": 7})
    html = render_import_page(
        preview={"writable": plan.writable, "skipped_header": False,
                 "unknown_methods": plan.unknown_methods, "anomalies": plan.anomalies,
                 "unmatched": plan.unmatched,
                 "rows": [{"bill_no": r.bill_no, "amount": f"{r.amount:.2f}",
                           "pay_date": r.pay_date, "pay_method": r.pay_method,
                           "remark": r.remark} for r in plan.rows]},
        token="t0ken")
    for must in ("尚未写库", "未匹配清单", "异常清单", "未识别的付款方式"):
        assert must in html, must
    assert 'name="token"' in html and "t0ken" in html       # 确认按钮带得回 token


@acc("ACC-FLOW-IMPORT-001", "001-05")
def test_未识别的付款方式取值必须在预览里列出来():
    plan = importer.parse_rows(_rows(
        ["FKTZS2026090466", "100.00", "2026-09-03", "微信红包", ""],
    ))
    assert plan.unknown_methods == ["微信红包"]              # 列出来给人过目（不静默）
    assert plan.rows[0].pay_method == "其他"                 # 归入「其他」
    assert "微信红包" in plan.rows[0].remark                 # 原文不丢


# ============================================================ ACC-FLOW-IMPORT-002


def _session(notices, flows=(), traces=()) -> FakeWriteSession:
    return FakeWriteSession({PaymentNotice: list(notices), PaymentFlow: list(flows),
                             NoticeStatLog: list(traces)})


@acc("ACC-FLOW-IMPORT-002", "002-01")
@acc("ACC-FLOW-IMPORT-002", "002-02")
@acc("ACC-FLOW-IMPORT-002", "002-04")
def test_一条付款一条流水_来源可辨_备注落库():
    s = _session([_notice(7)])
    plan = importer.split_by_match(
        importer.parse_rows(_rows(
            ["FKTZS2026090466", "100.00", "2026-09-03", "现汇", "首款"],
            ["FKTZS2026090466", "200.00", "2026-09-20", "承兑", "尾款"],
        )), {"FKTZS2026090466": 7})
    out = importer.commit(s, plan, batch="IMP-1", operator="科室用户")
    assert out["written"] == 2
    flows = [f for f in s.by_model[PaymentFlow]]
    assert len(flows) == 2                                   # 一次付款一条独立流水
    assert [f.amount for f in flows] == [Decimal("100.00"), Decimal("200.00")]
    assert {f.source for f in flows} == {FLOW_SOURCE_IMPORTED}
    assert {f.import_batch for f in flows} == {"IMP-1"}
    assert [f.remark for f in flows] == ["首款", "尾款"]


@acc("ACC-FLOW-IMPORT-002", "002-03")
def test_付款方式为空必须存空不得兜底现汇():
    s = _session([_notice(7)])
    plan = importer.split_by_match(
        importer.parse_rows(_rows(["FKTZS2026090466", "100.00", "2026-09-03", "", ""])),
        {"FKTZS2026090466": 7})
    importer.commit(s, plan, batch="IMP-2")
    assert s.by_model[PaymentFlow][0].pay_method == ""      # ⚠️ 不是「现汇」（事实记录不得编造）
    # 而**付款动作**那条路径仍然兜底「现汇」（两条口径互不干扰）
    manual = repo.create_flow(s, notice_id=7, project_id=None, amount="1.00",
                              pay_date="2026-09-03")
    assert manual.source == FLOW_SOURCE_MANUAL and manual.pay_method == "现汇"


@acc("ACC-FLOW-IMPORT-002", "002-05")
def test_付款方式能归类的归一_归不进记其他且原文留备注():
    assert importer.normalize_method("电汇") == ("现汇", True)
    assert importer.normalize_method("银行承兑汇票") == ("承兑", True)
    assert importer.normalize_method("供应链金融") == ("供应链", True)
    assert importer.normalize_method("") == ("", True)             # 空 = 合法留白，不算未识别
    assert importer.normalize_method("以物抵债") == ("其他", False)
    assert set(PAY_METHODS) == {"现汇", "承兑", "供应链", "其他"}


# ============================================================ ACC-FLOW-IMPORT-003


@acc("ACC-FLOW-IMPORT-003", "003-01")
@acc("ACC-FLOW-IMPORT-003", "003-02")
def test_同批重导先整批回滚_置撤销且留痕_不物理删():
    s = _session([_notice(7)])
    plan = importer.split_by_match(
        importer.parse_rows(_rows(["FKTZS2026090466", "100.00", "2026-09-03", "", ""])),
        {"FKTZS2026090466": 7})
    importer.commit(s, plan, batch="IMP-3", operator="科室用户")
    before = list(s.by_model[PaymentFlow])
    out = importer.rollback(s, "IMP-3", changed_by="科室用户")
    assert out == {"batch": "IMP-3", "revoked": 1, "kept": 0}
    assert len(s.by_model[PaymentFlow]) == len(before) == 1       # **不物理删**
    assert s.by_model[PaymentFlow][0].status == FLOW_REVOKED
    assert s.by_model[PaymentFlow][0].revoke_reason               # 原因留痕


@acc("ACC-FLOW-IMPORT-003", "003-03")
def test_不同批次互不影响():
    s = _session([_notice(7)])
    for batch, amt in (("IMP-A", "100.00"), ("IMP-B", "200.00")):
        plan = importer.split_by_match(
            importer.parse_rows(_rows(["FKTZS2026090466", amt, "2026-09-03", "", ""])),
            {"FKTZS2026090466": 7})
        importer.commit(s, plan, batch=batch)
    importer.rollback(s, "IMP-A")
    by_batch = {f.import_batch: f.status for f in s.by_model[PaymentFlow]}
    assert by_batch == {"IMP-A": FLOW_REVOKED, "IMP-B": FLOW_EFFECTIVE}


@acc("ACC-FLOW-IMPORT-003", "003-04")
def test_导入后给出核对报告_列出该批月份里没有流水的通知书():
    s = _session([
        _notice(7, bill_no="FKTZS2026090466", doc_date="2026-09-03"),
        _notice(8, bill_no="FKTZS2026090467", doc_date="2026-09-11"),   # 这张漏记了
        _notice(9, bill_no="FKTZS2026080100", doc_date="2026-08-11"),   # 别的月份，不该进来
    ])
    plan = importer.split_by_match(
        importer.parse_rows(_rows(["FKTZS2026090466", "100.00", "2026-09-03", "", ""])),
        {"FKTZS2026090466": 7})
    importer.commit(s, plan, batch="IMP-4")
    report = importer.check_report(s, "IMP-4")
    assert report["months"] == ["2026-09"]
    assert report["count"] == 1
    assert report["rows"][0]["bill_no"] == "FKTZS2026090467"


@acc("ACC-FLOW-IMPORT-003", "003-01")
def test_批次号可复现且带日期():
    b = importer.next_batch(at=datetime(2026, 9, 16, 12, 0, 0))
    assert b == "IMP-20260916120000"


# ============================================================ ACC-PAY-STAT-002


@acc("ACC-PAY-STAT-002", "002-01")
def test_统计付款金额默认值等于已付金额():
    s = _session([_notice(7, stat_paid=Decimal("0.00"))],
                 flows=[PaymentFlow(id=1, notice_id=7, amount=Decimal("300.00"),
                                    status=FLOW_EFFECTIVE)])
    assert repo.sync_stat_paid(s, 7) == Decimal("300.00")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("300.00")


@acc("ACC-PAY-STAT-002", "002-02")
def test_付款后自动重算():
    s = _session([_notice(7, stat_paid=Decimal("0.00"))])
    repo.create_flow(s, notice_id=7, project_id=None, amount="250.00", pay_date="2026-09-03")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("250.00")


@acc("ACC-PAY-STAT-002", "002-03")
def test_撤销付款后自动重算_回退():
    s = _session([_notice(7, stat_paid=Decimal("0.00"))])
    flow = repo.create_flow(s, notice_id=7, project_id=None, amount="250.00",
                            pay_date="2026-09-03")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("250.00")
    repo.revoke(s, flow, reason="记错了", changed_by="科室用户")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("0.00")


@acc("ACC-PAY-STAT-002", "002-04")
def test_导入历史流水后自动重算():
    s = _session([_notice(7, stat_paid=Decimal("0.00"))])
    plan = importer.split_by_match(
        importer.parse_rows(_rows(
            ["FKTZS2026090466", "100.00", "2026-09-03", "", ""],
            ["FKTZS2026090466", "200.00", "2026-09-20", "", ""],
        )), {"FKTZS2026090466": 7})
    importer.commit(s, plan, batch="IMP-5")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("300.00")


@acc("ACC-PAY-STAT-002", "002-05")
def test_手改过的行不被自动重算覆盖():
    trace = NoticeStatLog(id=1, notice_id=7, field="stat_paid",
                          before_amount=Decimal("0.00"), after_amount=Decimal("6000.00"),
                          changed_by="科室用户", changed_at=datetime(2026, 9, 10, 9, 0, 0))
    s = _session([_notice(7, stat_paid=Decimal("6000.00"))], traces=[trace])
    repo.create_flow(s, notice_id=7, project_id=None, amount="250.00", pay_date="2026-09-03")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("6000.00")   # 人工值原样保留


@acc("ACC-PAY-STAT-002", "002-06")
def test_实付超过审批金额照实写入不封顶():
    """⚠️ 与 §4.4.4「付款动作禁止超付」不冲突：那条约束**动作**，事实不得篡改。"""
    s = _session([_notice(7, stat_paid=Decimal("0.00"), amount_approved=APPROVED)])
    repo.create_flow(s, notice_id=7, project_id=None, amount="12000.00", pay_date="2026-09-03")
    assert s.by_model[PaymentNotice][0].stat_paid == Decimal("12000.00")   # 照实、不封顶
    # 而**付款动作**那条路仍然禁止超付（本用例只保证导入/事实路径不被封顶）
    assert effective_total([{"status": FLOW_EFFECTIVE, "amount": Decimal("12000.00")}]) == Decimal("12000.00")


# ============================================================ ACC-PAY-AMT-001


@acc("ACC-PAY-AMT-001", "001-01")
@acc("ACC-PAY-AMT-001", "001-02")
def test_金额字段结构是三金额且付款金额为派生列():
    from app.mod03_notice.domain import SOURCE_FIELDS, STAT_FIELDS, THREE_AMOUNT_FIELDS, derived_pay_amount

    assert len(THREE_AMOUNT_FIELDS) == 3
    assert SOURCE_FIELDS == ("amount_approved",)              # ⭐ 唯一 i8 源字段
    assert STAT_FIELDS == ("stat_settle", "stat_paid")
    assert not hasattr(PaymentNotice, "pay_amount_src")       # 原字段**已取消**
    assert derived_pay_amount(APPROVED, Decimal("8000.00")) == Decimal("2000.00")
    cols = {c.name for c in PaymentNotice.__table__.columns}
    assert "pay_amount_src" not in cols and "stat_paid" in cols


@acc("ACC-PAY-AMT-001", "001-03")
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
