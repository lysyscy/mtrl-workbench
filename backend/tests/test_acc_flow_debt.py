"""`ACC-FLOW-DEBT-001`（欠款统计）6 个判据点的验收断言。"""

from __future__ import annotations

from pathlib import Path

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


def test_期初不单列成第四类():
    openings = [
        OpeningView(CATEGORY_MATERIAL, 1, "2026-07", to_money("50"), to_money("0")),
        OpeningView(CATEGORY_MECH, 1, "2026-07", to_money("80"), to_money("0")),
    ]
    d = debt_by_category([], openings, mech_settle_total=to_money("0"))
    assert set(d.keys()) == {CATEGORY_MATERIAL, CATEGORY_MECH, CATEGORY_JC}   # **只有三类**
    assert d[CATEGORY_MATERIAL] == to_money("50")     # 辅材期初并入辅材
    assert d[CATEGORY_MECH] == to_money("80")         # 机械期初并入机械


def test_集采欠款不在本域计算只作合计展示():
    # 本域不接收"集采通知书行"的结算/付款贡献
    rows = [_view(CATEGORY_JC, "999", "999")]
    d = debt_by_category(rows, [], mech_settle_total=to_money("0"))
    assert d[CATEGORY_MATERIAL] == to_money("0")      # 集采行**不落进**辅材池
    assert d[CATEGORY_MECH] == to_money("0")
    # 集采值只能由外部（集采台账）注入，用于合计展示
    d2 = debt_by_category([], [], jc_debt=to_money("123"))
    assert d2[CATEGORY_JC] == to_money("123")


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


def test_剔除记录不计入欠款():
    rows = [
        _view(CATEGORY_MATERIAL, "1000", "0"),
        _view(CATEGORY_MATERIAL, "99999", "0", excluded=True),   # 剔除 ⇒ 不计
    ]
    d = debt_by_category(rows, [], mech_settle_total=to_money("0"))
    assert d[CATEGORY_MATERIAL] == to_money("1000")
    assert debt_by_project(rows)[1] == to_money("1000")


def test_集采欠款必须由装配层注入不许恒零(monkeypatch):
    """⭐ `TAIL-100`：**「集采由外部注入」这件事，注入方真的存在**。

    ⚠️ 为什么要有这一条（`001-03` 钉不住它）：`001-03` 只钉了**域内核**「集采值由 `jc_debt` 参数给」
       —— 而"**谁给**"没人管。实测的后果：`build_debt(s)` 在**生产两个调用点**都不传 `jc_debt`
       ⇒ 看板与欠款页的「集采欠款」**恒 ¥0.00**（真值 7444 万级，页面还完全看不出来）。
    ⇒ 本点只钉**装配**那一层：`build_debt_live` 在**不给** `jc_debt` 时必须**现取**（走集采域出口），
       且**显式给了就听给的**（⛔ 不硬塞）。
    """
    import app.mod11_jc.service as M11
    from app.mod05_flow import service as S
    # 把一个"没有通知书、没有期初、没有档案"的空场景喂进去 ⇒ 剩下唯一变量就是集采那一格
    monkeypatch.setattr(S, "notice_debt_views", lambda _s: [])
    monkeypatch.setattr(S, "opening_views", lambda _s: [])
    monkeypatch.setattr(S, "project_index", lambda _s: {})
    monkeypatch.setattr(M11, "debt_of_ledger", lambda _s: to_money("123"))

    got = _jc_amount(S.build_debt_live(object()))
    assert got == "123.00", f"不传 jc_debt ⇒ 必须**现取**集采台账的欠款（实测 {got} —— 恒 0 就是这个 bug）"

    got2 = _jc_amount(S.build_debt_live(object(), jc_debt=to_money("7")))
    assert got2 == "7.00", "显式给了就听给的（⛔ 不硬塞）"

    # ⭐ 结构面（堵"端点又绕开装配出口"这条路）：两个生产调用点都必须走 `build_debt_live`
    be = Path(__file__).resolve().parents[1] / "app"
    for rel, why in (("mod05_flow/router.py", "看板/欠款页端点"),
                     ("mod03_notice/notice_actions.py", "手改统计金额的欠款重算回执")):
        src = (be / rel).read_text(encoding="utf-8")
        assert "build_debt_live" in src, f"{why}（{rel}）没走装配出口 ⇒ 它那一处的「集采欠款」会回到恒 0"


def _jc_amount(data: dict) -> str:
    """取 `by_category` 里「集采」那一格的金额（字符串）。"""
    hit = [c for c in data["by_category"] if c["category"] == CATEGORY_JC]
    assert len(hit) == 1, f"「集采」那一格有 {len(hit)} 个 —— 结构变了"
    return str(hit[0]["amount"])
