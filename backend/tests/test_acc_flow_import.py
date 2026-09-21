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
    """**落库前必须预览 ⇒ 预览阶段不得写库**：解析 / 匹配 / **预览四块**都**不接受会话参数**。

    （结构不变式：`importer` 里只有 `commit` / `rollback` / `check_report` 接会话。）
    ⚠️ 2026-09-21（`§19` 四个暂留件收口）：预览页搬进新壳 ⇒ 四块由 `import_api.preview_of`
       （**纯函数**）产出 JSON、壳 `V.m05imp` 逐块渲染 —— 本用例改指那份 JSON ＋ 用壳源码
       钉住"四块都画出来 + 确认时把 token 带回去"（同「形态变、判据不变」）。
    """
    from app.mod05_flow.import_api import preview_of

    for fn in (importer.parse_rows, importer.split_by_match, importer.normalize_method,
               importer.parse_amount, importer.parse_date, preview_of):
        names = set(inspect.signature(fn).parameters)
        assert not (names & {"s", "session"}), f"{fn.__name__} 不该接触会话"

    plan = importer.split_by_match(
        importer.parse_rows(_rows(
            ["FKTZS2026090466", "100.00", "2026-09-03", "电汇", ""],
            ["FKTZS9999999999", "200.00", "2026-09-03", "", ""],
            ["FKTZS2026090465", "-1", "2026-09-03", "", ""],
        )), {"FKTZS2026090466": 7})
    pv = preview_of(plan)
    # 四块**都在**（少一块 = 某一类问题用户根本看不见）
    assert pv["writable"] == 1
    assert [u["bill_no"] for u in pv["unmatched"]] == ["FKTZS9999999999"]
    assert [a["reason"] for a in pv["anomalies"]] and pv["unknown_methods"] == []
    assert isinstance(pv["rows"], list) and pv["rows"][0]["bill_no"] == "FKTZS2026090466"

    # 而壳侧必须把四块**都画出来**，并且确认时把 token 带回去（token 存壳的 `IMP05` 状态里）
    from tests.shell_src import SHELL            # noqa: PLC0415  ← `P4`① 读取点收敛

    for must in ("尚未写库", "未匹配清单", "异常清单", "未识别的付款方式"):
        assert must in SHELL, f"壳的导入页少了这一块：{must}"
    assert "IMP05.token = r.token" in SHELL and "token: IMP05.token" in SHELL, \
        "壳没把预览 token 存下来 / 确认时没带回去（确认会拿不到预览结果）"


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

    from tests.shell_src import SHELL  # noqa: PLC0415  ← `P4`① 读取点收敛

    assert "over: !!x.is_overpaid," in SHELL, "壳没接后端的超付标志（或自己另算了一份）"
    assert "${n.over?" in SHELL and ">超付</span>" in SHELL, \
        "「超付」标记没挂在通知书行上 ⇒ claim 的「该单挂提醒」没有落点"


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
