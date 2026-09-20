"""`ACC-INIT-001` · 系统上线前的历史数据初始化（《说明书》§9.7 ＋ §7.6 指针）。

判据点归属：`MOD-13` 能力 9（此前无用例认领 —— 2026-09-17 补）。

⚠️ 本用例只钉「**入口存在** ＋ **初始化原则**」：
- ✅ `001-05`（过程资料**手录 ＋ Excel 上传**）—— 2026-09-17 入口落地（`/m06/mech` · `/m06/import*`）后**已绑**。
- ✅ `001-06`（集采台账手录）—— **2026-09-20 已钉**（原先写"对应的域尚未实现（M5）"，
  那是 09-17 的判断、**现已过期**：`m11` 上三个手录入口齐备）。
- 库存单据的**抓取动作**细判据归 `ACC-INV-FETCH-001`；本用例只钉「**过去月份可补抓**」这一点。
- ⚠️ `ACC-RPT-PROC-001` 管过程资料的**月度**口径，本用例管**上线前初始化**这一层，别交叉挂。
"""

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
from app.mod05_flow import importer
from app.mod05_flow.domain import (
    CATEGORY_JC, CATEGORY_MATERIAL, CATEGORY_MECH,
    OpeningView, build_ledger, debt_by_category, total_debt,
)
from app.mod06_proc import importer as proc_importer
from app.mod06_proc.models import ProcMechManual
from app.mod06_proc.repository import import_snapshot, load_cutoff, load_mech, save_mech
from tests.acc_plugin import acc
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


@acc("ACC-INIT-001", "001-01")
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


@acc("ACC-INIT-001", "001-02")
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


@acc("ACC-INIT-001", "001-03")
def test_i8期间两条入口都在_抓通知书与Excel导入历史流水():
    """§9.7 第 2 行：i8 侧**没有付款记录** ⇒ **Excel 是付款的唯一来源**；通知书走抓取。"""
    paths = _paths()
    assert "/api/m02/fetch/run" in paths                                  # 抓通知书
    assert {"/m05/import", "/m05/import/preview", "/m05/import/confirm"} <= paths   # Excel 导入三步
    assert "/m05/import/rollback" in paths                                # 同批整批回滚（初始化的纠错通道）


@acc("ACC-INIT-001", "001-05")
def test_过程资料手录与Excel上传两个入口都在():
    """§9.7 第 3 行：过程资料的**两条**初始化通道 —— **机械手录**（旁路表）＋ **Excel 上传**（定稿快照）。

    ⚠️ 它管的是**上线前初始化**这一层（「入口在不在、能不能直接落数」）；
       过程资料的**月度口径**归 `ACC-RPT-PROC-001/002` —— 别交叉挂。
    """
    paths = _paths()
    # ⚠️ 2026-09-18（`§19` 批 2）：PRG 版手录端点 `POST /m06/mech` 已随**过程资料页**删除（授权 `D18`）——
    #    它的 claim（「机械手录入口在」）**没删，搬到了壳**：`tests/test_wired_m06.py` 的
    #    「录机械费入口挂在 `BIND` 钩子」＋「后端机械写端点存在」（`POST /api/m06/mech` ✓）。
    #    ⚠️ 下面四条**仍在**（历史导入半边**暂留**：壳里没有任何导入入口 ⇒ 删不得）。
    assert {"/m06/import", "/m06/import/preview",
            "/m06/import/confirm", "/m06/import/rollback"} <= paths  # 上传三步 ＋ 纠错通道
    assert any(h == "/m06/import" for h, _t in NAV), "导航里要有这个入口"

    # ① 手录**真的落得进**（旁路载体：无审批、不受源数据约束）
    st = FakeSession({ProcMechManual: []})
    save_mech(st, ym="2025-12", warehouse=WAREHOUSE, values={"mech_0": Decimal("100.00")})
    assert [r["mech_0"] for r in load_mech(st)] == [Decimal("100.00")]

    # ② 上传**真的解析得出** ＋ **默认截止核算月 = 导入数据里最大的核算月**
    plan = proc_importer.parse_sheet(xlsx_bytes([["2025-11", "1000.00"], ["2025-12", "2000.00"]]))
    assert plan.months == ["2025-11", "2025-12"]
    assert plan.default_cutoff == "2025-12"
    batch = import_snapshot(st, warehouse=WAREHOUSE, rows=plan.rows, batch_no="PROC-INIT-001",
                            operator="科室用户", cutoff_ym=plan.default_cutoff)
    assert batch.cutoff_ym == "2025-12"
    assert load_cutoff(st, warehouse=WAREHOUSE) == "2025-12"


# ============================================================ 库存单据 · 补抓历史月份


@acc("ACC-INIT-001", "001-04")
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


@acc("ACC-INIT-001", "001-07")
def test_历史数据不重走审批_匹配不看审批状态():
    """§9.7 末行：**历史数据不重走**（不重走审批）—— 初始值入口**不因缺审批而拒收**。

    可观测出口：流水匹配**只认单据号**，完全不看通知书处于什么审批状态。
    """
    plan = importer.parse_rows([["FKTZS2026090466", "100", "2025-12-05", "现汇", ""]])
    out = importer.split_by_match(plan, {"FKTZS2026090466": 7})
    assert [r.bill_no for r in out.rows] == ["FKTZS2026090466"]
    assert out.rows[0].notice_id == 7 and out.unmatched == []


@acc("ACC-INIT-001", "001-08")
def test_不重走审批不等于不补录_付款事实落库且审批状态不改写():
    """§9.7 末行：⭐ 精确含义 —— **审批流程不重走**，但**已发生的付款事实要补录**（§4.4.6）。"""
    notice = _notice(1, bill_no="FKTZS2026090466", approve_status="已批")
    fake = FakeWriteSession({type(notice): [notice]})

    plan = importer.parse_rows([["FKTZS2026090466", "3000.00", "2025-12-05", "现汇", ""]])
    plan = importer.split_by_match(plan, {"FKTZS2026090466": 1})
    res = importer.commit(fake, plan, batch="20251205-1")

    assert res["written"] == 1
    assert len([x for x in fake.added if type(x).__name__ == "PaymentFlow"]) == 1   # 事实确实落库
    assert notice.approve_status == "已批"                                          # 审批状态一字未改


@acc("ACC-INIT-001", "001-06")
def test_集采台账手录入口在():
    """claim：「集采台账：**手录**入口在（该域所有数据均手录）」。

    ✅ **2026-09-20 已钉** —— ⚠️ 本文件原先写着"对应的域**尚未实现**（M5）⇒ 走未绑定态，
       不造假断言"，那是 **09-17 当时的判断，现已过期**：`M5` 集采域已开工，
       `m11` 上的手录入口齐备。⇒ 那句过期说明**同批删掉**（⛔ 留着就是"文档说一套、实现做一套"，
       而且会让下一个人以为这两点还不能钉）。

    ⚠️ 「该域所有数据均手录」⇒ **三个入口一个都不能少**（合同主表 / 发票 / 付款）：
       少一个，那个域的数据就得绕道别的页去录，"均手录"就不成立。
    ⚠️ 付款另有一条「**从付款域引用**」的旁路（`jcPayRef`）—— 它是"引用**已发生**的付款事实"，
       ⛔ **不是**手录的替代：两条并存（手录借据 / 引用付款域）。
    """
    web = pathlib.Path(app.__file__).resolve().parent / "web"
    all_shell = "\n".join([
        (web / "index.html").read_text(encoding="utf-8"),
        (web / "shell" / "core.js").read_text(encoding="utf-8"),
        (web / "shell" / "actions.js").read_text(encoding="utf-8"),
    ])

    assert 'data-act="jcAdd"' in all_shell, "集采**合同主表**没有手录入口（`jcAdd`，手工新增合同）"
    kinds = set(re.findall(r'data-act="jcSubAdd"[^>]*data-kind="(\w+)"', all_shell))
    assert kinds == {"inv", "tinv", "pay"}, (
        f"集采子表的手录入口不全：只找到 {sorted(kinds)} —— 「该域所有数据均手录」要求"
        "**合同 / 供应商发票 / 贸易公司发票 / 付款**四条都能手录，⛔ 少一条就得绕道别的页去录")
    assert 'data-act="jcPayRef"' in all_shell, (
        "付款的「从付款域引用」入口不见了 —— ⚠️ 它**不是**手录的替代（两条并存），"
        "但少了它，已发生过的付款事实就无法在集采域挂上")
