"""过程资料历史读取、i8整月优先、手录有效值及只读材料的回归。"""

from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from app.mod06_proc import domain as D
from app.mod06_proc import mech_ui
from app.mod06_proc.models import ProcCutoff, ProcHistoryBatch, ProcHistorySnapshot
from app.mod06_proc.repository import save_mech
from app.mod06_proc.service import build_page_data, parse_state
from app.mod08_inv.models import InvDetail
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


def _by_month(s: FakeSession) -> dict[str, dict]:
    return {r["ym"]: r for r in build_page_data(s, parse_state({"pj": WAREHOUSE}))["rows"]}


# ------------------------------------------------------------ 001-01 历史段不引用库存单据

def test_同月库存优先_无库存历史材料取快照():
    rows = _by_month(_sess())
    assert rows["2026-05"]["section"] == D.SECTION_HISTORY
    assert rows["2026-05"][f"in_主辅材"] == Decimal("9999.00")
    assert rows["2026-06"][f"out_主辅材"] == Decimal("200.00")

    # ⭐ 改库存单据（历史段内的那个月）之后，历史段金额**不变**（快照说了算）
    s = _sess()
    for r in s.by_model[InvDetail]:
        if r.ym == "2026-05":
            r.amount = Decimal("88888.00")
    assert _by_month(s)["2026-05"][f"in_主辅材"] == Decimal("88888.00"), "同月材料优先库存"
    s.by_model[InvDetail] = [r for r in s.by_model[InvDetail] if r.ym != "2026-05"]
    assert _by_month(s)["2026-05"]["in_主辅材"] == Decimal("1000.00"), "无库存历史取快照"


# ------------------------------------------------------------ 001-02 正式段引用 ＋ 分界移动

def test_正式段只读引用库存单据且分界可移动():
    rows = _by_month(_sess())
    assert rows["2026-07"]["section"] == D.SECTION_FORMAL
    assert rows["2026-07"][f"in_主辅材"] == Decimal("100.00")
    assert rows["2026-08"][f"in_主辅材"] == Decimal("200.00")
    assert rows["2026-09"][f"out_工具"] == Decimal("50.00")
    assert all(D.column_source(k, ym="2026-07", cutoff_ym=CUTOFF_YM, has_inventory=True) == D.SOURCE_INV
               for k in D.MATERIAL_KEYS), "正式段材料列 = 只读引用库存单据"

    # ⭐ 把截止核算月往后挪 ⇒ 该月转历史段（快照里没有 ⇒ 空态，**不回落库存单据**）
    s = _sess()
    s.by_model[ProcCutoff][0].cutoff_ym = "2026-08"
    moved = _by_month(s)
    assert moved["2026-07"]["section"] == D.SECTION_HISTORY
    assert moved["2026-07"]["material_empty"] is False
    assert moved["2026-07"][f"in_主辅材"] == Decimal("100.00")
    assert moved["2026-09"]["section"] == D.SECTION_FORMAL


# ------------------------------------------------------------ 001-03 机械列按段切来源（2026-09-26 改口径）

def test_机械六列_历史段以导入值为准_正式段手录():
    """机械导入和手录共用有效表，任何月份可编辑；材料仍只读。"""
    s = _sess()
    rows = _by_month(s)
    assert rows["2026-06"]["mech_0"] == Decimal("7.00")
    for ym in ("2026-06", "2026-07"):
        assert all(D.column_source(k, ym=ym, cutoff_ym=CUTOFF_YM) == D.SOURCE_MANUAL for k in D.MECH_KEYS)
        assert all(D.column_editable(k, ym=ym, cutoff_ym=CUTOFF_YM) for k in D.MECH_KEYS)
        assert not any(D.column_editable(k, ym=ym, cutoff_ym=CUTOFF_YM) for k in D.MATERIAL_KEYS)
    save_mech(s, ym="2026-06", warehouse=WAREHOUSE, values={"mech_0": Decimal("12.34")})
    assert _by_month(s)["2026-06"]["mech_0"] == Decimal("12.34")
    assert mech_ui.parse_mech_values({"mech_1": "0"})["mech_1"] == Decimal("0.00")
    with pytest.raises(ValueError):
        mech_ui.parse_mech_values({"mech_1": "-0.01"})


# ------------------------------------------------------------ 001-04 两段互不覆盖

def test_i8重抓保留历史原件且有效批次筛选不改库存():
    s = _sess()
    for row in s.by_model[InvDetail]:
        row.amount = Decimal('12345.00')
    assert _by_month(s)['2026-05']['in_主辅材'] == Decimal('12345.00')
    assert s.by_model[ProcHistorySnapshot][0].in_0 == Decimal('1000.00')
    assert _by_month(s)['2026-07']['in_主辅材'] == Decimal('12345.00')
    original = s.by_model[ProcHistoryBatch][0]
    original.status = 'replaced'
    s.add(make_batch('new'))
    s.add(make_snapshot(90, ym='2026-06', ins='777.00', batch_no='new'))
    rows = _by_month(s)
    assert rows['2026-06']['in_主辅材'] == Decimal('777.00')
    assert rows['2026-06']['out_主辅材'] == Decimal('0.00')
    assert rows['2026-07']['in_主辅材'] == Decimal('12345.00')
    assert len(s.by_model[ProcHistorySnapshot]) == 3


# ------------------------------------------------------------ 001-05 截止核算月


# ------------------------------------------------------------ 001-06 历史段无行内编辑

def test_历史段不提供行内编辑且已退出批次保留原件():
    s = _sess()
    assert build_page_data(s, parse_state({}))['can_edit_history'] is False
    s.by_model[ProcHistoryBatch][0].status = 'rolled_back'
    assert _by_month(s)['2026-05']['in_主辅材'] == Decimal('9999.00')
    assert '2026-06' in _by_month(s)  # 有机械有效值的历史月份仍可读。
    assert len(s.by_model[ProcHistorySnapshot]) == 2


# ------------------------------------------------------------ 001-07 列取值出口同构

def test_机械列与材料列同构且数据源可插拔():
    # ⭐ 两类列走**同一个**出口：只靠 column_source(key, ym, cutoff) 决定数据源
    hist = {D.column_source(k, ym="2026-06", cutoff_ym=CUTOFF_YM) for k in D.MATERIAL_KEYS}
    formal = {D.column_source(k, ym="2026-07", cutoff_ym=CUTOFF_YM, has_inventory=True) for k in D.MATERIAL_KEYS}
    mech_h = {D.column_source(k, ym="2026-06", cutoff_ym=CUTOFF_YM) for k in D.MECH_KEYS}
    mech_f = {D.column_source(k, ym="2026-07", cutoff_ym=CUTOFF_YM) for k in D.MECH_KEYS}
    assert hist == {D.SOURCE_SNAPSHOT} and formal == {D.SOURCE_INV}
    # ⭐ 2026-09-26（`TAIL-107`）：机械 6 列**走的还是这同一个出口**，只是结果也**按段切**
    #    （历史段 = 快照 / 正式段 = 手录）—— "同构、数据源可插拔"这条 claim 没变，变的是插头插在哪。
    assert mech_h == mech_f == {D.SOURCE_MANUAL}
    assert D.column_source(D.MATERIAL_KEYS[0], ym="2026-06", cutoff_ym="", has_inventory=True) == D.SOURCE_INV
    # 两类列**同一张表、同一套渲染出口** ⇒ 换机械费数据源时不动界面。
    # ⚠️ 2026-09-18（`§19` 批 2）：原先借旧页 html 的 `class="tw"` 计数观测；旧页删（`D18`）后
    #    这条的**实质**由上面 `column_source` 四条 ✓ ＋ 壳侧「合计行格数由表头派生」
    #    （`test_wired_m06.py`）合围 —— 「同一张表」在新壳里是**结构**（一张表 ＋ 一个表头派生通道）。


# ------------------------------------------------------------ 001-08 正式段空态

def test_正式段无i8数据时给空态不臆造零():
    rows = _by_month(_sess())
    row = rows["2026-10"]
    assert row["section"] == D.SECTION_FORMAL and row["material_empty"] is True
    assert all(row[k] is None for k in D.MATERIAL_KEYS), "材料列必须留空，不得臆造 0"
    assert row["mech_0"] == Decimal("9.00"), "同一行的机械列照常显示手录值"

    # ⚠️ 2026-09-18（`§19` 批 2）：原先还借旧页 html 看「—而不是 0.00」；旧页删（`D18`）后
    #    那条形态 claim 搬到壳：`test_wired_m06.py::test_正式段空态在壳里渲染成破折号而不是零`
    #    （钉壳的金额格式器 `M()` 的 `null ⇒ —` 分支 ✓）。上面 `is None` 三条是**实质** ✓ 不动。
    # 整列全空 ⇒ 合计留空（不臆造 0）
    assert D.column_totals([{"in_主辅材": None}])["in_主辅材"] is None
