"""`MOD-06` **页面 / 组装层 ＋ 两条写路径**的工程自检（离线 · 不连库）。

⚠️ 本文件**不绑定 `ACC-*` 判据点**（`@acc()` 显式声明）：判据在 `test_acc_proc_001/002.py` 里
由纯函数钉住；本文件守的是**这一层新加的东西** ——
**机械手录区块**（§5.2.5 ③）与**历史导入三步**（§5.2.5 ①②）的页面形态、写路径与暂存载具。
"""

from __future__ import annotations

import copy
import re
from decimal import Decimal

import pytest

from app.core import preview_store
from app.core.errors import MustReportError
from app.mod06_proc import domain as D
from app.mod06_proc import importer, mech_ui, repository as repo
from app.mod06_proc.models import ProcHistoryBatch, ProcHistorySnapshot
from app.mod06_proc.service import build_page_data, build_import_data, parse_state
from app.mod08_inv.models import InvDetail
from tests.acc_plugin import acc
from tests.m06_helpers import (
    CUTOFF_YM,
    WAREHOUSE,
    FakeSession,
    dataset_sections,
    make_batch,
    make_snapshot,
    xlsx_bytes,
)

MAT_HEADER = ("核算月", "入库主辅材", "出库工具", "租分公司设备", "备注")


def _sess() -> FakeSession:
    return FakeSession(copy.deepcopy(dataset_sections()))


# ⚠️ 2026-09-18（`§19` 批 2）：`_page()`（取旧页 html）已随过程资料页删除 ⇒ 整件移除
#    （它只被上面那两条页面形态用例用过）。


def _by_month(s: FakeSession) -> dict[str, dict]:
    return {r["ym"]: r for r in build_page_data(s, parse_state({"pj": WAREHOUSE}))["rows"]}


def _xlsx(rows: list[list], header=MAT_HEADER) -> bytes:
    return xlsx_bytes(rows, header)


# ============================================================ 机械手录（§5.2.5 ③）
#
# ⚠️ 2026-09-18（`TAIL-27` · `§19` **批 2**）：过程资料页半边已删（授权 `D18`）——
#    · 「机械手录区块只给机械列输入框」＝**页面形态** ⇒ 搬壳：`test_wired_m06.py` 的
#      「机械录入口只送 mech 键 / 材料列没有输入面」；
#    · 「回执条必须转义」＝**旧页 PRG 的提示文案形态** ⇒ 随页作废（壳的 toast 一律过 `esc()`，
#      另有全站口径在守；这条旧页形态没有独立 claim）；
#    · 「历史导入入口在页面上」⇒ 归**仍在的**导入页那一段（见下方「历史导入」小节 ✓）。
#    保留下来的两条只碰**入参解析/落库**（与页面无关）✓。


@acc()
def test_机械手录入参解析_空按零_负数与非数字报错():
    """⚠️ 原先这条还借旧页 html 看「核算月带回 / 现值预填」；那是页面形态，旧页删后随之删掉，
    留下的**入参解析（空按 0 / 负数与非数字报错）与月份归一**是与页面无关的实质。"""

    zeros = {f"mech_{i}": Decimal("0.00") for i in range(len(D.MECH_COLUMNS))}
    assert mech_ui.parse_mech_values({}) == zeros, "空框按 0（0 是合法录入值）"
    assert mech_ui.parse_mech_values({"mech_0": "12.5"})["mech_0"] == Decimal("12.50")
    with pytest.raises(ValueError):
        mech_ui.parse_mech_values({"mech_0": "-1"})
    with pytest.raises(ValueError):
        mech_ui.parse_mech_values({"mech_0": "abc"})
    # 月份归一（唯一出口 = domain）
    assert D.normalize_ym("2026/8") == D.normalize_ym("202608") == "2026-08"
    assert D.normalize_ym("2026-13") == "" and D.normalize_ym("八月") == ""


@acc()
def test_机械手录落库后表内取到_且重抓重导都不覆盖():
    s = _sess()
    repo.save_mech(s, ym="2026-09", warehouse=WAREHOUSE,
                   values={**{f"mech_{i}": Decimal("0") for i in range(len(D.MECH_COLUMNS))},
                           "mech_0": Decimal("55.00")})
    assert _by_month(s)["2026-09"]["mech_0"] == Decimal("55.00")

    # ① 重抓 i8（库存单据整批改数）⇒ 手录值不动
    for r in s.by_model[InvDetail]:
        r.amount = Decimal("77777.00")
    assert _by_month(s)["2026-09"]["mech_0"] == Decimal("55.00"), "重抓不得动机械手录"
    # ② 重导历史（新批次快照）⇒ 手录值仍不动
    s.by_model[ProcHistoryBatch].append(make_batch("H-02"))
    s.by_model[ProcHistorySnapshot].append(make_snapshot(399, ym="2026-09", ins="1.00",
                                                        batch_no="H-02"))
    assert _by_month(s)["2026-09"]["mech_0"] == Decimal("55.00"), "重导不得动机械手录"
    # ③ 历史段那份手录也照常可录（2026-06 ≤ 截止月）
    assert all(D.column_editable(k, ym="2026-06", cutoff_ym=CUTOFF_YM) for k in D.MECH_KEYS)


# ⚠️ 原先还有一条 `test_机械手录回执条必须转义`（旧页 PRG 的 `msg` 参数反射）—— 随页作废：
#    壳的提示一律过分 `esc()`（全站口径），那条是**旧页形态专用**的回归，没有独立 claim。


# ============================================================ 历史导入（§5.2.5 ①②）


def _plan():
    rows = [
        ["2026-03", "1000.00", "20.00", "888.00", "原始台账"],
        ["2026-04", "2000.00", "", "999.00", ""],
    ]
    return importer.parse_sheet(_xlsx(rows))


@acc()
def test_历史导入按表头认列_机械列不导入_异常行必报():
    plan = _plan()
    assert plan.months == ["2026-03", "2026-04"] and plan.writable == 2
    assert plan.rows[0]["in_主辅材"] == Decimal("1000.00")
    assert plan.rows[0]["out_工具"] == Decimal("20.00")
    # ⛔ 机械列**不入快照**（全段手录）—— 但要**显式列出来**给人看
    assert plan.ignored_mech == ["租分公司设备"]
    assert not any(k.startswith("mech_") for k in plan.rows[0])
    # 认不出的列只提示、不算错
    assert plan.unknown_headers == ["备注"]
    # 列序打乱也认得出（**不依赖位置**）
    shuffled = importer.parse_sheet(_xlsx([["20.00", "2026-03", "888", "1000.00"]],
                                          header=("出库工具", "核算月", "租分公司设备", "入库主辅材")))
    assert shuffled.rows[0]["in_主辅材"] == Decimal("1000.00")

    # 异常行逐条列出：月份认不出 / 金额非数字 / 只有月份
    with pytest.raises(MustReportError) as bad:
        importer.parse_sheet(_xlsx([
            ["八月", "1.00", "", "", ""],
            ["2026-05", "—", "", "", ""],
            ["2026-06", "", "", "", ""],
        ]))
    assert "3 行异常" in str(bad.value) and "行 2" in str(bad.value), "报错要带上行号与原因"

    # 一列材料列都没有 ⇒ 整份拒绝
    with pytest.raises(MustReportError):
        importer.parse_sheet(_xlsx([["2026-03", "1"]], header=("核算月", "备注")))


@acc()
def test_历史导入只写历史段_正式段与机械手录都不动():
    s = _sess()
    before_formal = _by_month(s)["2026-07"]["in_主辅材"]
    before_mech = _by_month(s)["2026-07"]["mech_0"]
    out = importer.commit(s, _plan(), warehouse=WAREHOUSE, batch="PROC-T1",
                          operator="科室用户", cutoff_ym=CUTOFF_YM)
    rows = _by_month(s)
    assert out["rows"] == 2 and out["cutoff_ym"] == CUTOFF_YM
    assert rows["2026-03"]["section"] == D.SECTION_HISTORY
    assert rows["2026-03"]["in_主辅材"] == Decimal("1000.00")
    assert rows["2026-04"]["out_工具"] is None or rows["2026-04"]["out_工具"] == Decimal("0.00")
    # 正式段与机械手录一格没动
    assert rows["2026-07"]["in_主辅材"] == before_formal
    assert rows["2026-07"]["mech_0"] == before_mech
    assert rows["2026-07"]["section"] == D.SECTION_FORMAL, "截止核算月被顺手挪了"


@acc()
def test_历史导入整批回滚后不再计入但不物理删():
    s = _sess()
    importer.commit(s, _plan(), warehouse=WAREHOUSE, batch="PROC-T2",
                    operator="科室用户", cutoff_ym=CUTOFF_YM)
    assert _by_month(s)["2026-03"]["in_主辅材"] == Decimal("1000.00")
    count = importer.rollback(s, batch_no="PROC-T2")
    assert count == 2
    assert "2026-03" not in _by_month(s), "回滚后该月连行都不该再有（历史段不回落 i8）"
    kept = [x for x in s.by_model[ProcHistorySnapshot] if x.batch_no == "PROC-T2"]
    assert len(kept) == 2, "回滚**不物理删**（留痕）"


@acc()
def test_核对报告列出不回落i8的月份():
    s = _sess()
    # 2026-05 在 i8 里有数据（9999）、快照里也有 ⇒ 不算空；把 2026-05 从快照里去掉再看
    s.by_model[ProcHistorySnapshot] = [r for r in s.by_model[ProcHistorySnapshot]
                                       if r.ym != "2026-05"]
    report = importer.check_report(s, warehouse=WAREHOUSE, batch_no="H20260916-01",
                                   cutoff_ym=CUTOFF_YM)
    assert report["count"] == 1 and report["rows"] == ["2026-05"]
    assert report["months"] == ["2026-06"], "报告里的「本批月份」= 生效批次覆盖到的月份"


# ============================================================ 暂存载具（两个导入页共用）


@acc()
def test_预览暂存不落库且两个导入页共用同一载具():
    token = preview_store.save({"rows": [{"ym": "2026-03"}]})
    assert preview_store.load(token)["rows"] == [{"ym": "2026-03"}]
    # ⚠️ 「取不到」这条分支要用**形态合法但不存在**的 token 才测得到 ——
    #    用中文串 / 带斜杠的串会**先被 token 形态校验拦掉**，测的其实是别的东西（反向灵敏度揪出来的）
    with pytest.raises(MustReportError):
        preview_store.load("deadbeefdeadbeef")
    with pytest.raises(MustReportError):
        preview_store.load("../etc/passwd")            # 路径穿越 ⇒ 直接拒
    # `MOD-05` 的付款导入走**同一个**载具（此前是它自己的一份 `_dump/_load`）
    from app.mod05_flow import importer as m05
    from app.mod05_flow.import_router import _known, _payload, _plan_of

    plan = m05.parse_rows([["FKTZS2026090466", "3000.00", "2026-08-05", "现汇", ""]])
    again = _plan_of(_payload(plan))
    assert again.rows[0].amount == Decimal("3000.00")
    assert again.rows[0].bill_no == "FKTZS2026090466"
    assert _known(FakeSession({})) == {}


# ============================================================ 导入页（三步）


@acc()
def test_历史导入页三步齐备且带项目与截止月():
    from app.mod06_proc.import_view import render_import_page

    s = _sess()
    html = render_import_page(build_import_data(s, warehouse=WAREHOUSE))
    assert 'action="/m06/import/preview"' in html
    assert f'name="pj" value="{WAREHOUSE}"' in html
    assert "核算月" in html and "入库主辅材" in html
    assert "机械 6 列不导入" in html
    assert CUTOFF_YM in html, "当前截止核算月要显示出来"
    assert "不提供行内编辑" in html
