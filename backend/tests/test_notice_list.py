"""付款通知书**列表**（§4.2 · §4.2.5 · §4.4.2）的验收断言 —— `ACC-PAY-LIST-001`。

判据点守的是**列表这层**：分类筛选四档（含专用**剔除视图**）· 剔除与撤单默认隐藏 ·
**三金额**与「付款金额」派生列 · **付款状态两态**且判定基准 = 审批金额 · 年月闭区间与项目多选 · 计数分档。
⚠️ `ACC-PAY-IA-001` 管的是**页面骨架 / 排序**（§4.1.2），`ACC-PAY-AMT-001` 管的是**字段结构**
   —— 列表的筛选 / 计数 / 行视图归本用例，别把判据点交叉挂过去。

口径出处：《说明书》§4.2.2（**「分类=剔除」是专用视图**）· §4.2.5（三金额与派生列）· §4.4.2（付款状态两态）。
"""

from __future__ import annotations

from decimal import Decimal

from app.mod03_notice.list_view import (
    CATEGORY_ALL,
    CATEGORY_EXCLUDE,
    NoticeFilters,
    NoticeRow,
    count_rows,
    filter_rows,
)
from app.mod05_flow.domain import (
    CATEGORY_JC,
    CATEGORY_MATERIAL,
    CATEGORY_MECH,
    PAY_STATUS_PAID,
    PAY_STATUS_UNPAID,
)


def _row(**kw) -> NoticeRow:
    base = dict(
        notice_id=1, doc_date="2026-09-05", bill_no="B1", bill_name="材料款结算单",
        project_name="甲项目", category=CATEGORY_MATERIAL, biz_type="付其他供应商款",
        payee="某供应商", input_by="王潜森",
        amount_approved=Decimal("10000"), amount_paid=Decimal("0"),
        stat_settle=Decimal("10000"), stat_paid=Decimal("10000"),
        approve_status="已批",
        excluded=False, exclude_source="", i8_revoked=False, ownership_id=11,
    )
    base.update(kw)
    return NoticeRow(**base)


# ---------------------------------------------------------------- 四金额与状态


def test_付款金额是派生列():
    """§4.2.5：列表「付款金额」= 审批金额 − 已付金额（**不是那四个金额之一**）。"""
    r = _row(amount_approved=Decimal("10000.00"), amount_paid=Decimal("3000.00"))
    assert r.pay_amount == Decimal("7000.00")


def test_付款状态两态且基准是审批金额():
    """§4.4.2：已付金额 ≥ **审批金额** ⇒ 已付清；「统计付款金额」不参与判定。"""
    assert _row(amount_approved=Decimal("100"), amount_paid=Decimal("100")).pay_status == PAY_STATUS_PAID
    assert _row(amount_approved=Decimal("100"), amount_paid=Decimal("99")).pay_status == PAY_STATUS_UNPAID
    # 统计付款金额再大也不影响状态
    r = _row(amount_approved=Decimal("100"), amount_paid=Decimal("0"), stat_paid=Decimal("9999"))
    assert r.pay_status == PAY_STATUS_UNPAID


# ---------------------------------------------------------------- 默认隐藏剔除 / 撤单


def test_默认视图不出现剔除与撤单行():
    rows = [
        _row(notice_id=1),
        _row(notice_id=2, excluded=True, exclude_source="rule"),
        _row(notice_id=3, i8_revoked=True),
    ]
    shown = filter_rows(rows, NoticeFilters(period="2026-09"))
    assert [r.notice_id for r in shown] == [1]


def test_分类筛选四档():
    rows = [
        _row(notice_id=1, category=CATEGORY_MATERIAL),
        _row(notice_id=2, category=CATEGORY_MECH),
        _row(notice_id=3, category=CATEGORY_JC),
    ]
    assert [r.notice_id for r in filter_rows(rows, NoticeFilters(period="2026-09"))] == [1, 2, 3]
    assert [r.notice_id for r in filter_rows(rows, NoticeFilters(period="2026-09", category=CATEGORY_MECH))] == [2]
    assert [r.notice_id for r in filter_rows(rows, NoticeFilters(period="2026-09", category=CATEGORY_JC))] == [3]


# ---------------------------------------------------------------- 「分类 = 剔除」专用视图


def test_剔除视图不受审批状态与付款状态约束():
    """§4.2.2 明文：切到「分类 = 剔除」时**不再受审批状态 / 付款状态筛选约束**。

    ⚠️ 否则默认的「付款状态 = 未付清」会把剔除行全挡掉 —— 该视图形同失效。
    """
    rows = [
        _row(notice_id=1, excluded=True, exclude_source="manual",
             approve_status="未批"),
        _row(notice_id=2, excluded=True, exclude_source="rule",
             approve_status="已批"),
    ]
    f = NoticeFilters(
        period="2026-09", category=CATEGORY_EXCLUDE,
        approve_status="已批", pay_status=PAY_STATUS_UNPAID,     # 这两个约束**应当被忽略**
    )
    assert [r.notice_id for r in filter_rows(rows, f)] == [1, 2]


def test_剔除视图同时给出剔除与撤单行且分档():
    rows = [
        _row(notice_id=1),
        _row(notice_id=2, excluded=True, exclude_source="manual"),
        _row(notice_id=3, excluded=True, exclude_source="rule"),
        _row(notice_id=4, i8_revoked=True),
    ]
    shown = filter_rows(rows, NoticeFilters(period="2026-09", category=CATEGORY_EXCLUDE))
    assert [r.notice_id for r in shown] == [2, 3, 4]                    # 有效行不进来
    # **按来源分档**（口径要求"不混作一谈"）
    assert [r.exclude_bucket for r in shown] == ["manual", "rule", "revoked"]
    assert [r.exclude_reason for r in shown] == ["人工批量剔除", "规则命中", "i8 已撤单"]

    # 撤单优先于剔除标记（撤单是 i8 侧的事实）
    both = _row(notice_id=5, i8_revoked=True, excluded=True, exclude_source="rule")
    assert both.exclude_bucket == "revoked" and both.exclude_reason == "i8 已撤单"


# ---------------------------------------------------------------- 时间与项目


def test_年月闭区间与项目多选():
    rows = [
        _row(notice_id=1, doc_date="2026-08-31"),
        _row(notice_id=2, doc_date="2026-09-01"),
        _row(notice_id=3, doc_date="2026-09-30"),
        _row(notice_id=4, doc_date="2026-10-01"),
    ]
    # 单月（闭区间两端都要在内）
    assert [r.notice_id for r in filter_rows(rows, NoticeFilters(period="2026-09"))] == [2, 3]
    # 跨月
    assert [r.notice_id for r in filter_rows(rows, NoticeFilters(period="2026-08~2026-09"))] == [1, 2, 3]
    # 整年
    assert [r.notice_id for r in filter_rows(rows, NoticeFilters(period="2026"))] == [1, 2, 3, 4]
    # 空 = 全部（含无日期的行也放行）
    rows2 = rows + [_row(notice_id=5, doc_date="")]
    assert [r.notice_id for r in filter_rows(rows2, NoticeFilters(period=""))] == [1, 2, 3, 4, 5]

    # 项目多选（按注入的 key 函数）
    mixed = [_row(notice_id=1, project_name="甲"), _row(notice_id=2, project_name="乙")]
    key = lambda r: r.project_name  # noqa: E731
    got = filter_rows(mixed, NoticeFilters(period="2026-09", project_ids=("乙",)), project_key=key)
    assert [r.notice_id for r in got] == [2]


# ---------------------------------------------------------------- 计数


def test_计数含剔除分档与撤单():
    rows = [
        _row(notice_id=1),
        _row(notice_id=2),
        _row(notice_id=3, excluded=True, exclude_source="manual"),
        _row(notice_id=4, excluded=True, exclude_source="rule"),
        _row(notice_id=5, i8_revoked=True),
    ]
    c = count_rows(rows, shown=[rows[0], rows[1]])
    assert (c.shown, c.effective, c.excluded, c.revoked) == (2, 2, 2, 1)
    assert c.excluded_by == {"人工": 1, "规则": 1}
    text = c.text()
    assert "有效 2 条" in text and "剔除 2 条" in text and "i8 已撤单 1 条" in text
