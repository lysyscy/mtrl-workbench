"""`TAIL-467`：欠款页**一个请求只装配一次事实**，且与原路径逐值（含顺序）相等。

⚠️ 本文件守的是**两件互不相干的事**，故意不合成一条：

1. **装配次数**（`test_欠款页一个请求只装配一次`）：同一请求里通知书视图 / 期初调整 /
   项目索引 / 机械有效值 / 集采行**各只取一次** —— 这是本票的全部收益来源，改回去就该红。
2. **等值**（其余四条）：一次装配喂出来的响应与老路径**逐值 + 键序**相同；集采合计与集采域
   的唯一出口 `mod11_jc.service.debt_of_ledger` 保持标签与金额；事实不跨请求留存。

⚠️ 期望值是**按夹具语义独立写的**（`m05_helpers.dataset()`：辅材 1000−200 ＋ 500−0 ＋ 期初 100 =
1400；机械 0−300 = −300；无归属 50 单列），⛔ 不是把实现里的数抄一遍。
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

from app.mod05_flow import router
from app.mod05_flow import service as M5
from tests.m05_helpers import FakeSession, dataset

# ---------------------------------------------------------------- 1. 装配次数（离线）


def test_欠款页一个请求只装配一次(monkeypatch):
    """一个 `/api/m05/debt` ⇒ 五类事实各取一次；返回值与老路径逐值相同。"""
    from app.mod06_proc import service as proc
    from app.mod11_jc import service as M11

    counts: dict[str, int] = {}

    def counted(name, fn):
        def wrapper(*args, **kwargs):
            counts[name] = counts.get(name, 0) + 1
            return fn(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(M5, "notice_debt_views",
                        counted("notice_debt_views", M5.notice_debt_views))
    monkeypatch.setattr(M5.repo, "list_openings",
                        counted("list_openings", M5.repo.list_openings))
    monkeypatch.setattr(M5, "project_index", counted("project_index", M5.project_index))
    monkeypatch.setattr(proc, "load_mech", counted("load_mech", proc.load_mech))
    monkeypatch.setattr(M11, "build_list", counted("build_list", M11.build_list))
    # ⛔ 老路径的这两个装配件若被再次调用，就等于重复装配 ⇒ 直接判红
    monkeypatch.setattr(M5, "opening_views",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("重复装配期初")))
    monkeypatch.setattr(M5, "mechanical_settlements",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("重复装配机械")))

    @contextmanager
    def borrowed():
        yield FakeSession(dataset())

    monkeypatch.setattr(router, "session_scope", borrowed)
    data = router.get_debt_data()()

    assert counts == {"notice_debt_views": 1, "list_openings": 1, "project_index": 1,
                      "load_mech": 1, "build_list": 1}

    # 夹具语义的独立期望：辅材合计含**无归属**那一行（1000−200 ＋ 500−0 ＋ 期初 100 ＋ 无归属 50
    # = 1450 —— 分类合计覆盖全部未剔除行，无归属只在**按项目**那一侧单列）；机械 0−300 = −300。
    assert [(c["category"], c["amount"]) for c in data["by_category"]] == [
        ("material", "1450.00"), ("mechanical", "-300.00"), ("jc", "0.00")]
    assert data["total"] == "1150.00"
    assert data["by_project_category"] == [
        {"project": "甲公司项目", "jc": "0.00", "material": "1400.00", "mech": "-300.00"},
        {"project": "待指定归属", "jc": "0.00", "material": "50.00", "mech": "0.00"},
    ]


def test_一次装配与老路径逐值相等_离线():
    """`facts=` 路径 vs 老路径：欠款组装与总欠款表**整份逐值 + 键序**相同。"""
    old_debt = M5.build_debt_live(FakeSession(dataset()))
    new_debt = M5.build_debt_live(FakeSession(dataset()),
                                  facts=M5.assemble_debt_facts(FakeSession(dataset())))
    assert new_debt == old_debt
    assert list(new_debt) == list(old_debt)

    old_total = M5.total_debt_rows(FakeSession(dataset()))
    new_total = M5.total_debt_rows(FakeSession(dataset()),
                                   facts=M5.assemble_debt_facts(FakeSession(dataset())))
    assert new_total == old_total
    assert [r["project"] for r in new_total["items"]] == [r["project"] for r in old_total["items"]]


# ---------------------------------------------------------------- 2. 等值（真库快照）


def test_集采预装配事实保持标签与负数():
    """预装配输入仍由集采域判断纳入标签和金额，不重新取数。"""
    from app.mod11_jc import service as M11
    from app.mod11_jc.models import TAG_IN

    rows = [{"tag": TAG_IN, "debt": "12.30"}, {"tag": TAG_IN, "debt": "-2.20"},
            {"tag": "exclude", "debt": "999.00"}]
    assert M11.debt_of_ledger(None, rows=rows) == Decimal("10.10")


def test_真库快照上事实路径与老路径逐值相等():
    """同一快照：`facts=` 与老路径产出的欠款组装 / 总欠款表逐值 + 行序相同。"""
    from app.core.db import session_scope

    with session_scope() as session:
        facts = M5.assemble_debt_facts(session)
        assert M5.build_debt_live(session, facts=facts) == M5.build_debt_live(session)
        new_total = M5.total_debt_rows(session, facts=facts)
        old_total = M5.total_debt_rows(session)
        assert new_total == old_total
        assert [r["project"] for r in new_total["items"]] == [r["project"] for r in old_total["items"]]
        assert new_total["jc_skipped"] == old_total["jc_skipped"]
        # 机械两列同源：一次装配用的 `load_mech(with_sources=False)` 不能改变数值
        assert M5._mech_totals_of(facts.mech_by_month) == M5.mechanical_totals(session)
        session.rollback()


def test_事实不跨请求留存(rollback_db):
    """装配结果只在**本次**请求里有效：改库后重新装配必须拿到新值（⛔ 不是缓存）。"""
    from app.core.db import session_scope
    from app.mod03_notice.models import PaymentNotice

    with session_scope() as session:
        notice = PaymentNotice(ph_id="__tail467_facts__", doc_date="2026-10-26",
                               category="", stat_settle=Decimal("11.00"), stat_paid=Decimal("0.00"),
                               excluded=False, fields={})
        session.add(notice)
        session.flush()
        first = M5.assemble_debt_facts(session)
        mine = [r for r in first.rows if r.notice_id == notice.id]
        assert [(r.settle_stat, r.pay_stat) for r in mine] == [(Decimal("11.00"), Decimal("0.00"))]

        notice.stat_settle = Decimal("12.50")
        session.flush()

        second = M5.assemble_debt_facts(session)
        mine2 = [r for r in second.rows if r.notice_id == notice.id]
        assert [(r.settle_stat, r.pay_stat) for r in mine2] == [(Decimal("12.50"), Decimal("0.00"))]
        session.rollback()
