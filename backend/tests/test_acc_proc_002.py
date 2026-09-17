"""`MOD-06` 过程资料 · **历史段 / 正式段** —— 离线自检（**不连库**）。

对应判据 `ACC-RPT-PROC-002`（8 点，`PRD/验收/验收基线.json`）：
- `001-01` 历史段（核算月 ≤ 截止核算月）材料列来自**导入的定稿快照**、**不引用库存单据**
- `001-02` 正式段（> 截止核算月）**只读引用**库存单据；两段分界 = 截止核算月，**改它分界随之移动**
- `001-03` 机械 6 列**全段可手录**（含历史段）；手录值落旁路载体，**不被重抓 / 重导覆盖**
- `001-04` ⭐ **两段互不覆盖**：重抓 i8 不动历史段 · 重导历史不动正式段
- `001-05` **截止核算月**在导入时设定；默认 = 导入数据里**最大的核算月**；一次设定、可改
- `001-06` 历史段要改**只能走导入**；页面**不提供历史段的行内编辑入口**
- `001-07` ⭐ 机械列与材料列**在页面上同构** —— 都经**同一个「列取值出口」**、数据源可插拔
- `001-08` 正式段某月尚无 i8 数据时，材料列给**空态提示**、**不臆造 0**
"""

from __future__ import annotations

import copy
import re
from decimal import Decimal

import pytest

from app.mod06_proc import domain as D
from app.mod06_proc import importer, mech_ui
from app.mod06_proc.models import ProcCutoff, ProcHistoryBatch, ProcHistorySnapshot
from app.mod06_proc.repository import import_snapshot, load_cutoff, rollback_batch, save_mech
from app.mod06_proc.service import build_page_data, parse_state
from app.mod06_proc.view import render_proc_page
from app.mod08_inv.models import InvDetail
from tests.acc_plugin import acc
from tests.m06_helpers import (
    CUTOFF_YM,
    WAREHOUSE,
    FakeSession,
    dataset_sections,
    make_batch,
    make_snapshot,
)

CASE = "ACC-RPT-PROC-002"


def _sess() -> FakeSession:
    return FakeSession(copy.deepcopy(dataset_sections()))


def _page(s: FakeSession) -> str:
    return render_proc_page(build_page_data(s, parse_state({"pj": WAREHOUSE})))


def _by_month(s: FakeSession) -> dict[str, dict]:
    return {r["ym"]: r for r in build_page_data(s, parse_state({"pj": WAREHOUSE}))["rows"]}


# ------------------------------------------------------------ 001-01 历史段不引用库存单据

@acc(CASE, "001-01")
def test_历史段材料来自快照不引用库存单据():
    rows = _by_month(_sess())
    assert rows["2026-05"]["section"] == D.SECTION_HISTORY
    assert rows["2026-05"][f"in_主辅材"] == Decimal("1000.00")
    assert rows["2026-06"][f"out_主辅材"] == Decimal("200.00")

    # ⭐ 改库存单据（历史段内的那个月）之后，历史段金额**不变**（快照说了算）
    s = _sess()
    for r in s.by_model[InvDetail]:
        if r.ym == "2026-05":
            r.amount = Decimal("88888.00")
    assert _by_month(s)["2026-05"][f"in_主辅材"] == Decimal("1000.00"), "历史段不得引用库存单据"


# ------------------------------------------------------------ 001-02 正式段引用 ＋ 分界移动

@acc(CASE, "001-02")
def test_正式段只读引用库存单据且分界可移动():
    rows = _by_month(_sess())
    assert rows["2026-07"]["section"] == D.SECTION_FORMAL
    assert rows["2026-07"][f"in_主辅材"] == Decimal("100.00")
    assert rows["2026-08"][f"in_主辅材"] == Decimal("200.00")
    assert rows["2026-09"][f"out_工具"] == Decimal("50.00")
    assert all(D.column_source(k, ym="2026-07", cutoff_ym=CUTOFF_YM) == D.SOURCE_INV
               for k in D.MATERIAL_KEYS), "正式段材料列 = 只读引用库存单据"

    # ⭐ 把截止核算月往后挪 ⇒ 该月转历史段（快照里没有 ⇒ 空态，**不回落库存单据**）
    s = _sess()
    s.by_model[ProcCutoff][0].cutoff_ym = "2026-08"
    moved = _by_month(s)
    assert moved["2026-07"]["section"] == D.SECTION_HISTORY
    assert moved["2026-07"]["material_empty"] is True
    assert moved["2026-07"][f"in_主辅材"] is None
    assert moved["2026-09"]["section"] == D.SECTION_FORMAL


# ------------------------------------------------------------ 001-03 机械全段手录

@acc(CASE, "001-03")
def test_机械六列全段可手录含历史段():
    rows = _by_month(_sess())
    assert rows["2026-06"]["section"] == D.SECTION_HISTORY
    assert rows["2026-06"]["mech_0"] == Decimal("7.00"), "历史段机械列照样取手录值"
    assert rows["2026-10"]["mech_0"] == Decimal("9.00")
    assert all(D.column_source(k, ym="2026-06", cutoff_ym=CUTOFF_YM) == D.SOURCE_MANUAL
               for k in D.MECH_KEYS)
    assert all(D.column_editable(k, ym="2026-06", cutoff_ym=CUTOFF_YM) for k in D.MECH_KEYS)
    assert not any(D.column_editable(k, ym="2026-06", cutoff_ym=CUTOFF_YM) for k in D.MATERIAL_KEYS)

    # ⭐ **录入口真的在页面上**（此前只有「域出口说可编辑」，页面根本没有录入口 —— `TAIL-03`）
    html = _page(_sess())
    assert all(f'name="mech_{i}"' in html for i in range(len(D.MECH_COLUMNS))), "机械列没有输入框"
    assert 'action="/m06/mech"' in html
    # ⛔ 材料列**仍然一个输入框都不能有**（机械列可录 ≠ 材料列可录）
    assert 'name="in_' not in html and 'name="out_' not in html

    # ⭐ **两段都真的录得进**（历史段 + 正式段），0 是合法值、负数被拦
    s = _sess()
    save_mech(s, ym="2026-05", warehouse=WAREHOUSE, values={"mech_1": Decimal("3.50")})
    save_mech(s, ym="2026-07", warehouse=WAREHOUSE, values={"mech_1": Decimal("4.50")})
    got = _by_month(s)
    assert got["2026-05"]["mech_1"] == Decimal("3.50"), "历史段手录没生效"
    assert got["2026-07"]["mech_1"] == Decimal("4.50"), "正式段手录没生效"
    assert mech_ui.parse_mech_values({"mech_1": "0"})["mech_1"] == Decimal("0.00"), "0 合法"
    with pytest.raises(ValueError):
        mech_ui.parse_mech_values({"mech_1": "-0.01"}), "负数必须被拦"


# ------------------------------------------------------------ 001-04 两段互不覆盖

@acc(CASE, "001-04")
def test_两段互不覆盖():
    base = _by_month(_sess())
    hist_before = {ym: base[ym][f"in_主辅材"] for ym in ("2026-05", "2026-06")}
    formal_before = {ym: base[ym][f"in_主辅材"] for ym in ("2026-07", "2026-08")}

    # ① 「重抓 i8」= 批量改库存单据金额 ⇒ 历史段一格都不动
    s = _sess()
    for r in s.by_model[InvDetail]:
        r.amount = Decimal("12345.00")
    after_refetch = _by_month(s)
    assert {ym: after_refetch[ym][f"in_主辅材"] for ym in hist_before} == hist_before, \
        "重抓 i8 **不得**动历史段"
    assert after_refetch["2026-07"][f"in_主辅材"] == Decimal("12345.00"), "正式段应随重抓变"

    # ② 「重导历史」= 新批次快照 ⇒ 正式段一格都不动
    s2 = _sess()
    s2.by_model[ProcHistoryBatch].append(make_batch("H20260916-02"))
    s2.by_model[ProcHistorySnapshot].append(
        make_snapshot(303, ym="2026-06", ins="777.00", batch_no="H20260916-02"))
    after_reimport = _by_month(s2)
    assert {ym: after_reimport[ym][f"in_主辅材"] for ym in formal_before} == formal_before, \
        "重导历史 **不得**动正式段"
    assert after_reimport["2026-06"][f"out_主辅材"] == Decimal("200.00"), "同月快照按批次相加"
    assert after_reimport["2026-06"][f"in_主辅材"] == Decimal("777.00")


# ------------------------------------------------------------ 001-05 截止核算月

@acc(CASE, "001-05")
def test_截止核算月默认取导入数据的最大核算月():
    s = FakeSession({})
    batch = import_snapshot(s, warehouse=WAREHOUSE, batch_no="B1",
                            rows=[{"ym": "2026-03", "in_主辅材": "10.00"},
                                  {"ym": "2026-06", "in_主辅材": "20.00"}],
                            operator="科室用户")
    assert batch.cutoff_ym == "2026-06", "默认 = 导入数据里最大的核算月"
    assert load_cutoff(s, warehouse=WAREHOUSE) == "2026-06"

    # 一次设定、可改
    import_snapshot(s, warehouse=WAREHOUSE, batch_no="B2",
                    rows=[{"ym": "2026-04", "in_主辅材": "30.00"}],
                    operator="科室用户", cutoff_ym="2026-04")
    assert load_cutoff(s, warehouse=WAREHOUSE) == "2026-04"

    # 空导入 ⇒ 拒绝（不把历史段清空）
    try:
        import_snapshot(s, warehouse=WAREHOUSE, batch_no="B3", rows=[], operator="科室用户")
        raise AssertionError("空导入必须被拒")
    except ValueError:
        pass


# ------------------------------------------------------------ 001-06 历史段无行内编辑

@acc(CASE, "001-06")
def test_历史段不提供行内编辑入口():
    s = _sess()
    assert build_page_data(s, parse_state({}))["can_edit_history"] is False
    html = _page(s)
    assert "历史段不提供行内编辑" in html
    assert 'name="in_' not in html and 'name="out_' not in html, "材料列不得有输入框（含历史段）"

    # 回滚是「再导一次」的配套动作（置状态、**不物理删**）
    assert rollback_batch(s, batch_no="H20260916-01") == 2
    assert s.by_model[ProcHistoryBatch][0].status == "rolled_back"
    assert _by_month(s)["2026-05"]["material_empty"] is True, "整批回滚后历史段为空（不回落库存单据）"

    # ⭐ **唯一修改通道真的能改**（`TAIL-02`）：再导一次 ⇒ 历史段跟着变，**正式段一格不动**
    s2 = _sess()
    formal_before = _by_month(s2)["2026-07"]["in_主辅材"]
    plan = importer.ImportPlan(rows=[{"ym": "2026-05", "in_主辅材": Decimal("4321.00")}])
    out = importer.commit(s2, plan, warehouse=WAREHOUSE, batch="PROC-006",
                          operator="科室用户", cutoff_ym=CUTOFF_YM)
    assert out["rows"] == 1 and out["cutoff_ym"] == CUTOFF_YM, "截止核算月应保持不动"
    assert _by_month(s2)["2026-07"]["in_主辅材"] == formal_before, "重导历史不得动正式段"
    # ① 旧批**仍生效** ⇒ 同月按批次相加（既有口径，见 001-04）
    assert _by_month(s2)["2026-05"]["in_主辅材"] == Decimal("5321.00")
    # ② 正路 = 「同批回滚后重导」：回滚旧批 ⇒ 该月只剩新批的数
    importer.rollback(s2, batch_no="H20260916-01")
    assert _by_month(s2)["2026-05"]["in_主辅材"] == Decimal("4321.00"), "回滚旧批后应只剩新批"


# ------------------------------------------------------------ 001-07 列取值出口同构

@acc(CASE, "001-07")
def test_机械列与材料列同构且数据源可插拔():
    # ⭐ 两类列走**同一个**出口：只靠 column_source(key, ym, cutoff) 决定数据源
    hist = {D.column_source(k, ym="2026-06", cutoff_ym=CUTOFF_YM) for k in D.MATERIAL_KEYS}
    formal = {D.column_source(k, ym="2026-07", cutoff_ym=CUTOFF_YM) for k in D.MATERIAL_KEYS}
    mech_h = {D.column_source(k, ym="2026-06", cutoff_ym=CUTOFF_YM) for k in D.MECH_KEYS}
    mech_f = {D.column_source(k, ym="2026-07", cutoff_ym=CUTOFF_YM) for k in D.MECH_KEYS}
    assert hist == {D.SOURCE_SNAPSHOT} and formal == {D.SOURCE_INV}
    assert mech_h == mech_f == {D.SOURCE_MANUAL}
    assert D.column_source(D.MATERIAL_KEYS[0], ym="2026-06", cutoff_ym="") == D.SOURCE_INV
    # 两类列**同一张表、同一套渲染出口** ⇒ 换机械费数据源时不动页面
    html = _page(_sess())
    assert html.count('class="tw"') == 1


# ------------------------------------------------------------ 001-08 正式段空态

@acc(CASE, "001-08")
def test_正式段无i8数据时给空态不臆造零():
    rows = _by_month(_sess())
    row = rows["2026-10"]
    assert row["section"] == D.SECTION_FORMAL and row["material_empty"] is True
    assert all(row[k] is None for k in D.MATERIAL_KEYS), "材料列必须留空，不得臆造 0"
    assert row["mech_0"] == Decimal("9.00"), "同一行的机械列照常显示手录值"

    html = _page(_sess())
    assert "不臆造 0" in html
    line = re.search(r"<tr>(?:(?!</tr>).)*2026-10(?:(?!</tr>).)*</tr>", html, re.S)
    assert line, "2026-10 那一行必须在表里"
    assert "—" in line.group(0), "空态格渲染为「—」而不是 0.00"
    # 整列全空 ⇒ 合计留空（不臆造 0）
    assert D.column_totals([{"in_主辅材": None}])["in_主辅材"] is None
