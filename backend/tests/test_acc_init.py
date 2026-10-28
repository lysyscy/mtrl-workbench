"""现行初始化入口：付款期初、过程资料机械手录、集采及库存补抓。"""

from __future__ import annotations

import pathlib
import re

from decimal import Decimal

import pytest

import app
from app.core.errors import MustReportError
from app.core.nav import NAV
from app.main import create_app
from app.mod02_i8 import report_export
from app.mod05_flow.domain import (
    CATEGORY_JC, CATEGORY_MATERIAL, CATEGORY_MECH,
    OpeningView, build_ledger, debt_by_category, total_debt,
)
from app.mod06_proc.models import ProcMechManual
from app.mod06_proc.repository import load_mech, save_mech
from tests.m03_action_helpers import FakeWriteSession, _notice
from tests.m06_helpers import WAREHOUSE, FakeSession, xlsx_bytes


def _paths() -> set[str]:
    """全站**已注册**的路由路径。

    ⚠️ 本仓 FastAPI 把 `include_router` 收成 `_IncludedRouter`（`path` 为空）⇒
       **不能**直接遍历 `app.routes` 取路径（会漏掉除 `_PAGES` 静态页外的全部）。
       走 `openapi()` 的 `paths` —— 它就是「实际注册了什么」的权威视图。
    """
    return set(create_app().openapi()["paths"])


# ============================================================ 付款域 · 期初占位行（i6 时代）


def test_期初占位行可手填且按其分类并入():
    """§9.7 第 1 行：更早（i6 时代）单据少、不抓取 ⇒ **期初占位行手填**这条路必须保留。

    ⚠️ 口填的期初**按其分类并入**辅材 / 机械，**不单列第四类**（与 `ACC-FLOW-DEBT-001` 同一条口径，
    本点只从「初始化入口」这一层再钉一次：**没有通知书也能录**）。
    """
    op = OpeningView(category=CATEGORY_MATERIAL, project_id=1, cutoff_ym="2025-11",
                     settle_amount=Decimal("1000.00"), paid_amount=Decimal("400.00"))
    by = debt_by_category([], [op])                     # 一条通知书都没有 ⇒ 全靠期初
    assert by[CATEGORY_MATERIAL] == Decimal("600.00")   # 期初按其分类并入辅材
    assert set(by) == {CATEGORY_MATERIAL, CATEGORY_MECH, CATEGORY_JC}


def test_期初与i8期间流水不重叠且台账自截止月起排行():
    """§9.7 第 1 / 2 行：两条路**不重叠** —— 期初是**一段截止年月**，其后从**次月**起逐月连续。"""
    op = OpeningView(category=CATEGORY_MATERIAL, project_id=1, cutoff_ym="2025-11",
                     settle_amount=Decimal("1000.00"), paid_amount=Decimal("400.00"))
    monthly = {
        "2025-10": {"settle": Decimal("999.00"), "pay": Decimal("999.00")},   # 早于截止月：不得进台账
        "2025-12": {"settle": Decimal("50.00"), "pay": Decimal("10.00")},
    }
    rows = build_ledger(category=CATEGORY_MATERIAL, monthly=monthly, opening=op)

    assert rows[0].month == "2025-11" and rows[0].is_opening is True
    assert rows[0].other_expense == Decimal("1000.00") and rows[0].payment == Decimal("400.00")
    assert [r.month for r in rows[1:]] == ["2025-12"]                     # 自**次月**起，逐月连续
    assert all(r.month != "2025-10" for r in rows)                        # 截止月之前不重复出行
    assert [r for r in rows if r.is_opening] == [rows[0]]                 # 期初只出现一次（不重复计入）


# ============================================================ 付款域 · i8 期间的两条入口


def test_过程资料机械手录入口保留():
    assert '/api/m06/mech' in _paths()
    st = FakeSession({ProcMechManual: []})
    save_mech(st, ym='2025-12', warehouse=WAREHOUSE, values={'mech_0': Decimal('100.00')})
    assert [r['mech_0'] for r in load_mech(st)] == [Decimal('100.00')]


# ============================================================ 库存单据 · 补抓历史月份


def test_库存单据可补抓历史月份():
    """§9.7 第 5 行：库存单据**从 i8 补抓历史月份**（不是只能抓当月）。

    ⚠️ 补抓**只允许单月** ⇒ 起止年月恒等；且年份必须取**该月所属年**（踩过的坑：补抓历史月份时用当前年）。
    ⚠️ 「抓取动作」细判据归 `ACC-INV-FETCH-001`，本点只钉**入参可指向过去月份**。
    """
    assert report_export.single_month("2025-12") == ("2025", "12", "2025", "12")
    for bad in ("2025-12,2026-01", "2025", ""):        # 跨月 / 整年 / 空：一律拒绝
        with pytest.raises(MustReportError):
            report_export.single_month(bad)
    # ⚠️ 2026-09-19（`§19` 批 2）：原先断言两个 **PRG** 路由（`/m08/fetch-dialog`·`/m08/fetch`）存在；
    #    旧页删除（`D18`）后那条路走 **JSON API**（壳在用）⇒ 按 claim（"库存单据能从 i8 补抓"）改指 API。
    assert "/api/m08/fetch" in _paths()


# ============================================================ 原则 · 不重走审批
