"""`ACC-FLOW-DEBT-001`（欠款统计）5 个判据点的验收断言。"""

from __future__ import annotations

from app.core.money import to_money
from app.mod05_flow.domain import (
    UNASSIGNED,
    NoticeDebtView,
    OpeningView,
    debt_by_category,
    debt_by_project,
    total_debt,
)
from app.mod05_flow.models import CATEGORY_JC, CATEGORY_MATERIAL, CATEGORY_MECH
from tests.acc_plugin import acc


def _view(cat, settle, pay, *, excluded=False, owner=1, doc_date="2026-08-10"):
    return NoticeDebtView(
        notice_id=abs(hash((cat, str(settle), str(pay), str(owner)))) % 100000,
        doc_date=doc_date,
        category=cat,
        settle_stat=to_money(settle),
        pay_stat=to_money(pay),
        excluded=excluded,
        ownership_id=owner,
    )


@acc("ACC-FLOW-DEBT-001", "001-01")
def test_三类欠款各按口径独立复算且合计为三者之和():
    rows = [
        _view(CATEGORY_MATERIAL, "1000", "200"),   # 辅材净 800
        _view(CATEGORY_MECH, "0", "100"),          # 机械只减付款
    ]
    openings = [OpeningView(CATEGORY_MATERIAL, 1, "2026-07", to_money("50"), to_money("0"))]
    d = debt_by_category(rows, openings, mech_settle_total=to_money("600"), jc_debt=to_money("300"))
    assert d[CATEGORY_MATERIAL] == to_money("850")     # 800 + 期初 50
    assert d[CATEGORY_MECH] == to_money("500")         # 600 − 100
    assert d[CATEGORY_JC] == to_money("300")           # 外部（集采台账）
    assert total_debt(d) == to_money("1650")           # 合计 = 三者之和
    # 独立复算：辅材只由辅材行 + 辅材期初决定，与机械/集采无关
    assert d[CATEGORY_MATERIAL] == debt_by_category(rows, openings, mech_settle_total=to_money("0"))[CATEGORY_MATERIAL]


@acc("ACC-FLOW-DEBT-001", "001-02")
def test_期初不单列成第四类():
    openings = [
        OpeningView(CATEGORY_MATERIAL, 1, "2026-07", to_money("50"), to_money("0")),
        OpeningView(CATEGORY_MECH, 1, "2026-07", to_money("80"), to_money("0")),
    ]
    d = debt_by_category([], openings, mech_settle_total=to_money("0"))
    assert set(d.keys()) == {CATEGORY_MATERIAL, CATEGORY_MECH, CATEGORY_JC}   # **只有三类**
    assert d[CATEGORY_MATERIAL] == to_money("50")     # 辅材期初并入辅材
    assert d[CATEGORY_MECH] == to_money("80")         # 机械期初并入机械


@acc("ACC-FLOW-DEBT-001", "001-03")
def test_集采欠款不在本域计算只作合计展示():
    # 本域不接收"集采通知书行"的结算/付款贡献
    rows = [_view(CATEGORY_JC, "999", "999")]
    d = debt_by_category(rows, [], mech_settle_total=to_money("0"))
    assert d[CATEGORY_MATERIAL] == to_money("0")      # 集采行**不落进**辅材池
    assert d[CATEGORY_MECH] == to_money("0")
    # 集采值只能由外部（集采台账）注入，用于合计展示
    d2 = debt_by_category([], [], jc_debt=to_money("123"))
    assert d2[CATEGORY_JC] == to_money("123")


@acc("ACC-FLOW-DEBT-001", "001-04")
def test_按项目看欠款按归属归集且未判定单列():
    # 同一壳全名下的两行 → 归属拆到**各自的具体小微**（owner=11 / 12）
    rows = [
        _view(CATEGORY_MATERIAL, "1000", "0", owner=11),
        _view(CATEGORY_MATERIAL, "500", "0", owner=12),
        _view(CATEGORY_MATERIAL, "700", "0", owner=None),   # 未判定
    ]
    by_p = debt_by_project(rows)
    assert by_p[11] == to_money("1000")
    assert by_p[12] == to_money("500")
    assert by_p[UNASSIGNED] == to_money("700")            # 单列、**不并入任何小微**
    assert 11 in by_p and 12 in by_p and UNASSIGNED in by_p


@acc("ACC-FLOW-DEBT-001", "001-05")
def test_剔除记录不计入欠款():
    rows = [
        _view(CATEGORY_MATERIAL, "1000", "0"),
        _view(CATEGORY_MATERIAL, "99999", "0", excluded=True),   # 剔除 ⇒ 不计
    ]
    d = debt_by_category(rows, [], mech_settle_total=to_money("0"))
    assert d[CATEGORY_MATERIAL] == to_money("1000")
    assert debt_by_project(rows)[1] == to_money("1000")
