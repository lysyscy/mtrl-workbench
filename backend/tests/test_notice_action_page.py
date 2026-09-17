"""`MOD-03` **页面渲染面**的验收断言（操作列 / 草稿行 / 查看关联页 / 统计可改格）。

- `ACC-PAY-ACTION-001` —— 「操作」列（撤销付款就近入口 / 多条转跳流水页）· 查看关联只读页 ⇒ `§4.4.5`
- `ACC-PAY-MANUAL-001` —— 操作列只在手动行给编辑删除 · 草稿行统计结算与录入人只读 ⇒ `§4.2.6`
- `ACC-PAY-STAT-001`   —— 统计两列是行内可改格、手改过黄底（判据 = 留痕）⇒ `§4.5.3` / `§4.2.7`

⚠️ 2026-09-16 自 `test_notice_actions.py` 拆出（**断言一字未改**）。
"""

from __future__ import annotations

from decimal import Decimal

from app.mod03_notice.notice_page import render_trace_page
from tests.acc_plugin import acc
from tests.m03_action_helpers import (
    _cell_of, _notice, _render, _render_with_traces, _row_of,
)


# ============================================================ 操作列（R18）与草稿行


@acc("ACC-PAY-MANUAL-001", "001-06")
def test_操作列_i8行无编辑删除_手动行才有():
    html = _render([_notice(1, ph_id="3700000000123", is_manual=False),
                    _notice(2, ph_id="MANUAL-abc", is_manual=True)])
    i8 = _row_of(html, "B1")
    manual = _row_of(html, "B2")
    # i8 行：不得出现编辑 / 删除（§9.3 源数据只读）
    assert "/m03/notices/delete" not in i8 and "edit=" not in i8
    assert "手动</span>" not in i8
    assert ">—<" in i8                                    # 一个条件都不满足 ⇒ 「—」
    # 手动行：「手动」徽标 + 编辑 / 删除
    assert "手动</span>" in manual
    assert "/m03/notices/delete" in manual
    assert 'name="edit" value="2"' in manual                 # 编辑 = 原地变草稿行（POST /m03/notices/draft）


@acc("ACC-PAY-ACTION-001", "001-01")
def test_操作列_有生效流水才出撤销付款():
    flows = {1: [{"id": 7, "flow_no": "FL1", "amount": "100.00", "pay_date": "2026-09-09",
                  "pay_method": "现汇", "status": "effective", "revoke_reason": ""}]}
    html = _render([_notice(1)], flows)
    assert "撤销付款" in html and 'name="reason"' in html       # 1 条 ⇒ 就地展开撤销窗（原因必填）
    # 已撤销的流水**不算**生效 ⇒ 不出撤销入口
    revoked = {1: [{"id": 7, "flow_no": "FL1", "amount": "100.00", "pay_date": "2026-09-09",
                    "pay_method": "现汇", "status": "revoked", "revoke_reason": "填错"}]}
    assert "撤销付款" not in _render([_notice(1)], revoked)


@acc("ACC-PAY-ACTION-001", "001-02")
def test_操作列_多条生效流水改为跳转流水页():
    flows = {1: [
        {"id": 7, "flow_no": "FL1", "amount": "100.00", "pay_date": "2026-09-09",
         "pay_method": "现汇", "status": "effective", "revoke_reason": ""},
        {"id": 8, "flow_no": "FL2", "amount": "200.00", "pay_date": "2026-09-10",
         "pay_method": "承兑", "status": "effective", "revoke_reason": ""},
    ]}
    html = _render([_notice(1)], flows)
    assert "/m05?notice_id=1" in html                    # 跳到 MOD-05 并筛到这一张单
    assert "逐条撤销" in html                             # **不提供一键撤全部**（R18）


@acc("ACC-PAY-ACTION-001", "001-04")
def test_查看关联页是纯只读且流水子表含已撤销():
    """§4.4.5 / R18：「查看关联」是**只读反查**页 —— 零副作用，且流水子表**含已撤销那几条**。"""
    data = {
        "bill_no": "B1", "doc_date": "2026-09-05", "bill_name": "材料款结算单",
        "project_name": "甲项目", "category": "material", "approve_status": "已批",
        "stat_settle": "10000.00", "stat_paid": "5000.00", "approve_amount": Decimal("10000.00"),
        "is_manual": False, "i8_revoked": False,
        "flows": [
            {"flow_no": "FL1", "pay_date": "2026-09-09", "amount": "3000.00",
             "pay_method": "现汇", "status": "effective", "status_label": "生效",
             "revoke_reason": "", "revoked_at": ""},
            {"flow_no": "FL2", "pay_date": "2026-09-10", "amount": "2000.00",
             "pay_method": "承兑", "status": "revoked", "status_label": "已撤销",
             "revoke_reason": "填错", "revoked_at": "2026-09-11 10:00"},
        ],
    }
    html = render_trace_page(data)
    # 已撤销那条**照样列出来**（含原因与时间）—— 不是"只看生效"
    assert "FL1" in html and "FL2" in html
    assert "填错" in html and "2026-09-11 10:00" in html
    # ⚠️ 已付金额 = **生效流水汇总**（已撤销的不计入）⇒ 3000 而非 5000。
    #    ⭐ 必须**绑到「已付金额」那一格**去取值 —— 整页 `in` 会被「统计付款金额 5000.00」
    #       顺手喂饱（实测：把实现改成"全部流水汇总"（=5000）后整页断言**仍然通过**）。
    paid_cell = _cell_of(html, "已付金额（生效流水汇总）")
    assert paid_cell == "3000.00", f"已付金额应只算生效流水，实际 = {paid_cell!r}"
    assert _cell_of(html, "统计付款金额") == "5000.00"       # 另一格不受影响（两格是两件事）

    # **零副作用**：不得出现任何写路径（表单 / 动作端点）
    for bad in ("<form", "/m03/notices/delete", "/m03/notices/save",
                "/m03/notices/category", "/m03/pay", "/m03/notices/stat"):
        assert bad not in html, f"只读页不该出现写路径：{bad}"
    assert "纯只读" in html                                # 页面自己讲明


@acc("ACC-PAY-ACTION-001", "001-05")
def test_查看关联页不臆造集采取值():
    """⭐ 集采台账（`MOD-11`）**尚未落地** ⇒ 该页必须显示「—」并注明，**不得臆造空串或假值**。

    ⚠️ 必须**绑到那一格**：整页 `in "集采实际供应商"` 只命中**标签**（页面上本来就有），
       把取值换成臆造空串后**照样绿** —— 实测（本件 `001-05` 曾如此；反向灵敏度 ⑫ 复现）。
    """
    html = render_trace_page({"bill_no": "B1", "category": "jc", "flows": []})
    supplier = _cell_of(html, "集采实际供应商")
    assert supplier.startswith("—"), f"未落地应显示「—」，实际 = {supplier!r}"
    assert "MOD-11" in supplier and "尚未落地" in supplier   # 注明原因，而不是留白
    assert _cell_of(html, "集采合同关联").startswith("—")     # 同一件事的第二格（不得只改一格）
    assert "该行还没有付款流水" in html                      # 空态有提示行


@acc("ACC-PAY-MANUAL-001", "001-07")
def test_草稿行_统计结算只读且录入人只读():
    html = _render([_notice(1)], draft={})
    assert 'class="draftrow"' in html
    assert "0.00 恒为 0" in html                          # §4.2.6：恒 0 且不可改（不是输入框）
    assert 'name="stat_settle"' not in html
    assert 'name="input_by"' not in html                  # 录入人不由手填
    assert "＋ 手动新增通知书" in html                     # 增行模式入口在卡片头/批量条


# ============================================================ 能力 11 · 统计金额手改（§4.5.3）


@acc("ACC-PAY-STAT-001", "001-08")
def test_统计两列是行内可改格():
    html = _render([_notice(1)])
    assert 'name="v_1_stat_settle"' in html and 'name="v_1_stat_paid"' in html
    assert 'name="target" value="1:stat_settle"' in html        # 整页共用一个表单，靠 target 指明格子
    assert 'class="cell num"' in html
    assert 'class="cell num ed"' not in html                    # 没手改过 ⇒ 不黄底（R8）


@acc("ACC-PAY-STAT-001", "001-09")
def test_手改过的统计格是黄底():
    from datetime import datetime

    from app.mod03_notice.domain import StatTrace

    traces = {1: [StatTrace(notice_id=1, field="stat_paid", before=Decimal("10000.00"),
                            after=Decimal("8000.00"), changed_by="张三", changed_at=datetime.now())]}
    html = _render_with_traces([_notice(1)], traces)
    assert 'class="cell num ed"' in html                        # 判据 = **留痕**（§4.2.7）
    assert 'name="v_1_stat_settle"' in html
    assert 'class="cell num ed" form="f-stat" title' in html or 'ed' in html
