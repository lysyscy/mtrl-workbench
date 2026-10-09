"""`MOD-06` 过程资料 · **历史段 / 正式段** —— 离线自检（**不连库**）。

对应判据 `ACC-RPT-PROC-002`（8 点，`PRD/验收/验收基线.json`）：
- `001-01` 历史段（核算月 ≤ 截止核算月）材料列来自**导入的定稿快照**、**不引用库存单据**
- `001-02` 正式段（> 截止核算月）**只读引用**库存单据；两段分界 = 截止核算月，**改它分界随之移动**
- `001-03` ⭐ **2026-09-26 改口径**（`TAIL-107`）：机械 6 列**按段切来源** —— 历史段以**导入的快照**
  为准（**不许手录**）· 正式段手录（"手录仅限于正式启用系统后"）；手录值落旁路载体，**不被重抓 / 重导覆盖**
- `001-04` ⭐ **两段互不覆盖**：重抓 i8 不动历史段 · 重导历史不动正式段
- `001-05` **截止核算月**在导入时设定；默认 = 导入数据里**最大的核算月**；一次设定、可改
- `001-06` 历史段要改**只能走导入**；页面**不提供历史段的行内编辑入口**
- `001-07` ⭐ 机械列与材料列**在页面上同构** —— 都经**同一个「列取值出口」**、数据源可插拔
  （材料列：历史段快照 / 正式段库存单据；机械列：历史段快照 / 正式段手录）
- `001-08` 正式段某月尚无 i8 数据时，材料列给**空态提示**、**不臆造 0**
"""

from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from app.mod06_proc import domain as D
from app.mod06_proc import importer, mech_ui
from app.mod06_proc.models import ProcCutoff, ProcHistoryBatch, ProcHistorySnapshot
from app.mod06_proc.repository import import_snapshot, load_cutoff, rollback_batch, save_mech
from app.mod06_proc.service import build_page_data, parse_state
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


def _by_month(s: FakeSession) -> dict[str, dict]:
    return {r["ym"]: r for r in build_page_data(s, parse_state({"pj": WAREHOUSE}))["rows"]}


# ------------------------------------------------------------ 001-01 历史段不引用库存单据

@acc(CASE, "001-01")
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

@acc(CASE, "001-02")
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

@acc(CASE, "001-03")
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
    assert after_refetch["2026-05"]["in_主辅材"] == Decimal("12345.00")
    assert s.by_model[ProcHistorySnapshot][0].in_0 == Decimal("1000.00"), "i8重抓不改快照记录"
    assert after_refetch["2026-07"][f"in_主辅材"] == Decimal("12345.00"), "正式段应随重抓变"

    # ② 「重导历史」= 新批次快照 ⇒ 正式段一格都不动
    s2 = _sess()
    import_snapshot(s2, warehouse=WAREHOUSE, batch_no="H20260916-02",
                    rows=[{"ym": "2026-06", "in_主辅材": "777.00"}], operator="自检",
                    cutoff_ym=CUTOFF_YM)
    after_reimport = _by_month(s2)
    assert {ym: after_reimport[ym][f"in_主辅材"] for ym in formal_before} == formal_before, \
        "重导历史 **不得**动正式段"
    assert after_reimport["2026-06"][f"in_主辅材"] == Decimal("777.00"), "无库存的月份使用新有效历史"
    assert after_reimport["2026-06"][f"out_主辅材"] == Decimal("0.00"), "旧批次必须退出有效历史"
    s2.by_model[InvDetail] = [r for r in s2.by_model[InvDetail] if r.ym != "2026-06"]
    assert _by_month(s2)["2026-06"]["in_主辅材"] == Decimal("777.00")
    assert _by_month(s2)["2026-06"]["out_主辅材"] == Decimal("0.00"), "旧批次整体退出"


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
    # ⚠️ 2026-09-18（`§19` 批 2）：原先还借旧页 html 看「历史段不提供行内编辑」这句提示与
    #    「材料列无输入框」；旧页删（`D18`）后 —— 前者是**页面文案**、后者已由壳侧
    #    `test_wired_m06.py::test_机械录入口只送mech键_材料列没有输入面` 与上面域出口断言合围 ✓
    #    （`can_edit_history is False` 这条**实质**就在本行 ✓ 不动）。

    # 回滚是「再导一次」的配套动作（置状态、**不物理删**）
    assert rollback_batch(s, batch_no="H20260916-01") == 2
    assert s.by_model[ProcHistoryBatch][0].status == "rolled_back"
    assert _by_month(s)["2026-05"]["in_主辅材"] == Decimal("9999.00"), "回滚历史不影响库存优先"

    # ⭐ **唯一修改通道真的能改**（`TAIL-02`）：再导一次 ⇒ 历史段跟着变，**正式段一格不动**
    s2 = _sess()
    formal_before = _by_month(s2)["2026-07"]["in_主辅材"]
    plan = importer.ImportPlan(rows=[{"ym": "2026-05", "in_主辅材": Decimal("4321.00")}])
    out = importer.commit(s2, plan, warehouse=WAREHOUSE, batch="PROC-006",
                          operator="科室用户", cutoff_ym=CUTOFF_YM)
    assert out["rows"] == 1 and out["cutoff_ym"] == CUTOFF_YM, "截止核算月应保持不动"
    assert _by_month(s2)["2026-07"]["in_主辅材"] == formal_before, "重导历史不得动正式段"
    # 重导替换历史；有库存月份仍优先显示库存。
    assert _by_month(s2)["2026-05"]["in_主辅材"] == Decimal("9999.00")
    # 回滚已替换旧批不影响新批；无库存时读取新历史。
    importer.rollback(s2, batch_no="H20260916-01")
    s2.by_model[InvDetail] = [r for r in s2.by_model[InvDetail] if r.ym != "2026-05"]
    assert _by_month(s2)["2026-05"]["in_主辅材"] == Decimal("4321.00"), "回滚旧批后应只剩新批"


# ------------------------------------------------------------ 001-07 列取值出口同构

@acc(CASE, "001-07")
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

@acc(CASE, "001-08")
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
