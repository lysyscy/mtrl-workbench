"""TAIL-469：月报「按月装载」与提取「屏幕读模型」的等值回归（离线，不连库）。

三条判据，各自只钉一件实际风险：
① 月报改走 `repository.load_month_rows` 后，**表体与合计仍与「全量装载」逐值一致**
   （`domain.warehouse_rows` 的二次月筛没被绕过）；
② 提取的屏幕读模型 `/api/m07/extract-screen` 与完整出口 `/api/m07/extract` 的
   `annual` / `balances` **逐值同一份**，完整出口一项不少（`amounts` / `annual_totals` / `kinds`）；
③ `extract_amounts` 的调用内记忆化**只省重复判定**，取数与合计与独立复算一致。
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

from app.mod07_setl import api as setl_api
from app.mod07_setl import domain as D
from app.mod07_setl import extract as X
from app.mod07_setl import repository as R
from app.mod07_setl import service as setl
from tests.m07_helpers import (EXTRACT_EXPECT, FakeSession, dataset, extract_dataset,
                               indep_amount_total, indep_extract_total, indep_warehouses)


class _Recorder(FakeSession):
    """记下 `execute` 收到的语句（桩不执行 WHERE ⇒ 只用来钉「按月装载」这件事写在语句里）。"""

    def __init__(self, by_model: dict | None = None) -> None:
        super().__init__(by_model)
        self.statements: list[str] = []

    def execute(self, stmt):  # noqa: ANN001
        self.statements.append(str(stmt))
        return super().execute(stmt)


# ------------------------------------------------------------ ① 月报：按月装载 ≡ 全量装载


def test_月报按月装载的表体与合计与全量装载逐值一致():
    """`load_month_rows` 少装载别的月份；**条目、行数与四列金额必须与全量装载逐值相同**
    （桩忽略 WHERE，正好证明 `warehouse_rows`/`rows_of` 的二次月筛仍在）。"""
    for ym in ("2026-08", "2026-07", "2026-06", "2026-05"):
        st = setl.parse_state({"period": ym})
        full = D.warehouse_rows(R.load_rows(FakeSession(dataset())), ym)
        got = setl.build_page_data(FakeSession(dataset()), st)["rows"]
        assert [r["warehouse"] for r in got] == [r["warehouse"] for r in full], ym
        for a, b in zip(got, full):
            assert {k: a[k] for k in ("rows", *D.AMOUNT_KEYS)} == {k: b[k] for k in ("rows", *D.AMOUNT_KEYS)}, ym

    data = setl.build_page_data(FakeSession(dataset()), setl.parse_state({"period": "2026-08"}))
    assert [r["warehouse"] for r in data["rows"]] == indep_warehouses("2026-08")
    for key in D.AMOUNT_KEYS:
        assert data["summary"][key] == indep_amount_total("2026-08", key)


def test_月报装载语句按月过滤而不是全表():
    """语句本身要带核算月的等值条件（索引 `setl_detail.ym`）；否则「按月装载」名不副实。"""
    session = _Recorder(dataset())
    setl.build_page_data(session, setl.parse_state({"period": "2026-08"}))
    assert session.statements, "月报一次 SQL 都没发"
    assert all("FROM setl_detail" in sql for sql in session.statements), session.statements
    assert any("setl_detail.ym = " in sql and "WHERE" in sql for sql in session.statements), session.statements


# ------------------------------------------------------------ ② 提取：屏幕读模型 vs 完整出口


@contextmanager
def _scope(session):
    yield session


def test_屏幕读模型与完整提取接口逐值同签名_只少屏幕不消费的三项(monkeypatch):
    """屏幕读模型 = 同一份 `annual`/`balances`；完整出口仍发 `amounts`/`annual_totals`/`kinds`。"""
    monkeypatch.setattr(setl_api, "session_scope", lambda: _scope(FakeSession(extract_dataset(with_balances=True))))
    full = setl_api.api_extract(year="2026", status="在建")
    screen = setl_api.api_extract_screen(year="2026", status="在建")

    assert set(screen) == {"annual", "balances"}, set(screen)
    assert screen["annual"] == full["annual"]
    assert screen["balances"] == full["balances"]
    # 完整出口的契约一项没少（导出与既有脚本仍读它们）
    assert set(full) == {"amounts", "annual", "annual_totals", "kinds", "balances"}
    for kind, by_wh in EXTRACT_EXPECT.items():
        for wh, months in by_wh.items():
            assert full["amounts"][kind][wh] == {m: v for m, v in months.items()}
    assert full["annual"]["焊材"]["rows"][0]["total"] == str(indep_extract_total(
        "焊材", full["annual"]["焊材"]["rows"][0]["warehouse"]))


def test_提取页年度网格与导出年度网格仍逐值一致且清单结余为手工录入值(monkeypatch):
    """`build_extract_data` 与 `build_extract_export` 各自算 annual（一个走复用参数、一个显式传 balances）
    ⇒ 两份必须逐值相同；「结余」只出现已录入的键（0 是合法值、未录入不出现）。"""
    page = setl.build_extract_data(FakeSession(extract_dataset(with_balances=True)),
                                   setl.parse_extract_state({"status": "全部", "ext_period": "2026"}))
    exported = setl.build_extract_export(FakeSession(extract_dataset(with_balances=True)),
                                         {"status": "全部", "period": "2026"})
    assert page["annual"] == exported["annual_grids"]
    balances = page["annual"]["焊材"]["rows"]
    by_wh = {r["warehouse"]: r["balance"] for r in balances}
    assert by_wh["甲仓"] == Decimal("1200.00") and by_wh["乙仓"] == Decimal("0.00")
    assert "丙仓" not in by_wh


# ------------------------------------------------------------ ③ 提取规则记忆化：只省重复判定


def test_提取规则记忆化与独立复算一致_近名不命中仍不命中():
    details = [d for wh, ym, name, amount, prop in
               [("甲仓", "2026-08", "焊条J422", "1000.00", "主材"),
                ("甲仓", "2026-08", "焊条J422", "1.00", "主材"),
                ("甲仓", "2026-08", "氧气瓶", "555.00", "辅材"),
                ("乙仓", "2026-08", "氧气", "100.00", "辅材")]
               for d in [{"warehouse": wh, "ym": ym, "resource_name": name, "in": Decimal(amount)}]]
    got = X.extract_amounts(details)
    # 同名两行 ⇒ 记忆化只记一次判定，但金额仍逐行累加
    assert got["焊材"]["甲仓"]["2026-08"] == Decimal("1001.00")
    # 白名单精确匹配：「氧气瓶」不是「氧气」（近名不命中没被记忆化改掉 ⇒ 甲仓连桶都不建）
    assert "甲仓" not in got["气体"]
    assert got["气体"]["乙仓"]["2026-08"] == Decimal("100.00")
    # 换规则立刻生效（不跨调用缓存）
    assert X.extract_amounts(details, X.extract_rules(gas=("氧气瓶",)))["气体"]["甲仓"]["2026-08"] == Decimal("555.00")
