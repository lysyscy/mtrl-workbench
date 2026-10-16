"""`ACC-PLAN-UI-001`（计划页筛选 / 删除 / 行内改列）8 个判据点的验收断言。

依据：《说明书》§4.3.3（数据入口与可手改列）· §4.3.4（审查结果 6 种 + 筛选两档归并）
      · §4.3.6（历史保留 / 列表内删除）· §4.3.7（10 号截止 = 生效窗口）。
"""

from __future__ import annotations

import pytest

from app.core.errors import MustReportError
from app.core.money import to_money
from app.mod04_plan.domain import (
    ALL_RESULTS,
    BUCKET_ALL,
    BUCKET_MATCHED,
    BUCKET_UNMATCHED,
    FILTER_BUCKETS,
    R_AMOUNT_MISMATCH,
    R_MATCHED,
    R_NO_DOC,
    NoticeAmounts,
)
from app.mod04_plan.plan_ui import (
    AFFECTED_TABLES,
    FILTER_FIELDS,
    PERIOD_SCOPE,
    delete_impact,
    delete_rows,
    filter_plan_rows,
    inline_edit,
    inline_editable_columns,
    period_filter_is_shared_control,
    period_filter_modes,
    re_match,
    window_button,
)
from app.mod05_flow.domain import NoticeDebtView, debt_by_category
from app.mod05_flow.models import CATEGORY_MATERIAL
from tests.acc_plugin import acc


def _setup():
    """4 行计划 + 逐行审查结果（键 = 计划行 id）。"""
    rows = [
        {"id": 1, "year_month": "2026-08", "project_key": "A"},
        {"id": 2, "year_month": "2026-08", "project_key": "B"},
        {"id": 3, "year_month": "2026-07", "project_key": "A"},
        {"id": 4, "year_month": "2026-08", "project_key": "A"},
    ]
    results = {1: R_MATCHED, 2: R_AMOUNT_MISMATCH, 3: R_MATCHED, 4: R_NO_DOC}
    return rows, results


def _ids(rows):
    return [r["id"] for r in rows]


def _key(r):
    return r["project_key"]


def _notice_view() -> NoticeDebtView:
    return NoticeDebtView(
        notice_id=1, doc_date="2026-08-10", category=CATEGORY_MATERIAL,
        settle_stat=to_money("500.00"), pay_stat=to_money("100.00"), ownership_id=9,
    )


@acc("ACC-PLAN-UI-001", "001-01")
def test_筛选栏三项齐备且年月走统一控件():
    assert FILTER_FIELDS == ("year_month", "project_ids", "audit_bucket")
    assert period_filter_modes() == ("月", "跨月", "年", "全部")   # 四种模式，不新造控件
    assert period_filter_is_shared_control() is True              # 复用全站唯一的核算年月控件
    assert PERIOD_SCOPE == "plan"                                 # 调用点声明（导入/抓取只给「月」）
    rows, results = _setup()
    f = lambda **kw: _ids(filter_plan_rows(rows, results, project_key=_key, **kw))  # noqa: E731
    assert f(year_month="2026-08") == [1, 2, 4]
    assert f(year_month="2026-08", project_ids=("A",)) == [1, 4]      # 项目可多选
    assert f(year_month="2026-08", project_ids=("A", "B")) == [1, 2, 4]
    assert f(year_month="2026-07~2026-08") == [1, 2, 3, 4]            # 跨月 = 闭区间
    assert f(year_month="2026") == [1, 2, 3, 4]
    assert f(year_month="") == [1, 2, 3, 4]                           # 全部


@acc("ACC-PLAN-UI-001", "001-02")
def test_审查结果判定六种但筛选只归并两档():
    assert len(ALL_RESULTS) == 6
    assert FILTER_BUCKETS == (BUCKET_ALL, BUCKET_MATCHED, BUCKET_UNMATCHED)
    # 细分判定不得出现在筛选档里（只做粗筛）
    for r in ALL_RESULTS:
        if r != R_MATCHED:
            assert r not in FILTER_BUCKETS
    rows, results = _setup()
    matched = filter_plan_rows(rows, results, year_month="2026-08",
                               audit_bucket=BUCKET_MATCHED, project_key=_key)
    unmatched = filter_plan_rows(rows, results, year_month="2026-08",
                                 audit_bucket=BUCKET_UNMATCHED, project_key=_key)
    assert _ids(matched) == [1]
    assert _ids(unmatched) == [2, 4]              # 「未匹配」= 其余 5 种
    assert _ids(matched) + _ids(unmatched) == [1, 2, 4]


@acc("ACC-PLAN-UI-001", "001-03")
def test_行内可改列立刻落库且不留痕():
    assert set(inline_editable_columns(R_MATCHED)) == {"pay_date", "pay_method", "remark"}
    for col, val in (("pay_date", "2026-08-15"), ("pay_method", "承兑"), ("remark", "已核")):
        e = inline_edit(row_id=1, column=col, value=val, allowed=inline_editable_columns(R_MATCHED))
        assert e.persisted is True          # 立刻落库
        assert e.trace is None              # ⚠️ **不留痕**（不属 §9.3 留痕范围）
        assert e.value == val
    # 审查结果 / 金额 / 派生列都不在可改集合里
    for bad in ("audit_result", "flow_amount", "planned_amount", "paid_amount", "不存在的列"):
        with pytest.raises(MustReportError):
            inline_edit(row_id=1, column=bad, value="1", allowed=inline_editable_columns(R_MATCHED))


@acc("ACC-PLAN-UI-001", "001-04")
def test_单据号只对未匹配行开放且再次匹配触发重判():
    assert "doc_no" in inline_editable_columns(R_AMOUNT_MISMATCH)
    assert "doc_no" in inline_editable_columns(R_NO_DOC)
    assert "doc_no" not in inline_editable_columns(R_MATCHED)     # 完全匹配行只读
    with pytest.raises(MustReportError):
        inline_edit(row_id=1, column="doc_no", value="D9", allowed=inline_editable_columns(R_MATCHED))
    # 未匹配行改完单据号 ⇒ 点「再次匹配」重判（同一审查引擎）
    notices = {"D9": NoticeAmounts(doc_no="D9", approved=to_money("100.00"), paid=to_money("0.00"))}
    row = {"id": 4, "year_month": "2026-08", "doc_no": "D9",
           "flow_amount": to_money("100.00"), "planned_amount": to_money("100.00")}
    r = re_match(row, notices)
    assert r.notice_id == 4 and r.doc_no == "D9"
    assert r.result == R_MATCHED
    # 改后又查不到 ⇒ 回到「单据号查不到」，不是静默通过
    r2 = re_match({**row, "doc_no": "NOPE"}, notices)
    assert r2.result == "单据号查不到"


@acc("ACC-PLAN-UI-001", "001-05")
def test_逐行删除只删该行且勾选集合同步收敛():
    rows, _ = _setup()
    rows2, picked2 = delete_rows(rows, targets=[1], picked={1, 2, 3}, confirmed=True)
    assert _ids(rows2) == [2, 3, 4]                # 只删该行
    assert picked2 == {2, 3}                       # 行数与勾选集合同步收敛
    # 批量删除同款
    rows3, picked3 = delete_rows(rows, targets=[2, 4], picked={1, 2, 3, 4}, confirmed=True)
    assert _ids(rows3) == [1, 3] and picked3 == {1, 3}
    # 删不存在的行不出错
    rows4, picked4 = delete_rows(rows, targets=[999], picked={1}, confirmed=True)
    assert _ids(rows4) == [1, 2, 3, 4] and picked4 == {1}


@acc("ACC-PLAN-UI-001", "001-06")
def test_删除前必须列出影响范围且确认后才执行():
    rows, results = _setup()
    imp = delete_impact(rows, [2, 4], results)
    assert [i.row_id for i in imp] == [2, 4]
    for item in imp:
        assert item.seq is not None          # 行号
        assert item.year_month               # 所属年月
        assert item.result                   # 审查结果
    assert imp[0].year_month == "2026-08" and imp[0].result == R_AMOUNT_MISMATCH
    assert imp[1].result == R_NO_DOC
    assert imp[0].seq == 2 and imp[1].seq == 4
    # 未经确认不得执行
    with pytest.raises(MustReportError):
        delete_rows(rows, targets=[2], picked=set(), confirmed=False)


@acc("ACC-PLAN-UI-001", "001-07")
def test_删除只影响付款计划表():
    assert AFFECTED_TABLES == ("plan_row",)          # 只影响付款计划表
    notices = [_notice_view()]
    debt_before = debt_by_category(notices, [])
    rows, _ = _setup()
    delete_rows(rows, targets=[1, 2, 3, 4], picked=set(), confirmed=True)
    # 通知书与欠款统计**一点不动**
    assert notices == [_notice_view()]
    assert debt_by_category(notices, []) == debt_before
    assert list(debt_before.keys()) == [CATEGORY_MATERIAL, "mechanical", "jc"]


@acc("ACC-PLAN-UI-001", "001-08")
def test_按计划勾选按钮恒可点且月份可选():
    """⭐ 2026-10-08 用户裁定：**不再按日期禁用、月份改为可选**。

    原口径是"每月 10 号 → 月底才可点、月份定死当月"（§4.3.2 生效窗口）。取消的理由：
    那条窗口只是**制度上的习惯**，制度本身也只约束人、不拦系统（§4.3.7「系统不做任何拦截或标记」），
    做成**按钮置灰**反而挡住正常补勾（用户 2026-10-08 报障）。
    ⚠️ `reason` 键**保留**（装配层与页面都读它）；`ym` 只用于回显。
    """
    for arg in ("", "2026-10"):
        b = window_button(arg)
        assert b["enabled"] is True, f"按钮又被按日期/别的条件禁用了（arg={arg!r}）"
        assert b["reason"] == "", f"不该再有「不可点的原因」（arg={arg!r}）：{b['reason']!r}"
    assert window_button("2026-10")["label"] == "按 2026-10 付款计划勾选", "回显没带所选月份"
    assert window_button("")["label"] == "按付款计划勾选", "没月份时也该给出可读的按钮文案"
    # ⛔ 旧口径的基础件已删（留着就会有人又拿它把按钮置灰 —— 那正是这次报障）
    from app.mod04_plan import domain as _d
    assert not hasattr(_d, "in_effective_window"), "`in_effective_window` 还在（会复活按日期禁用）"
    assert not hasattr(_d, "WINDOW_START_DAY"), "`WINDOW_START_DAY` 还在（= 那个 10 号的门槛）"
