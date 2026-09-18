"""`MOD-06` 过程资料 —— 离线自检（**不连库**）。

对应判据 `ACC-RPT-PROC-001`（9 点，`PRD/验收/验收基线.json`）：
- `001-01` 原始 / 调整后 / 差异三张齐备，**默认停在「调整后表」**
- `001-02` 表体**一个核算月一行、月份升序**；逐月求和 = 全月合计（逐列独立复算）
- `001-03` 列结构以 §5.2.2 为准；**筛选栏不设只读年月框**（核算月只作表内列）
- `001-04` 项目筛选**单选**（radio、不给全选 / 清空），**选中即收起**
- `001-05` 表①② 在**每个数据列下方**给「合计」行，逐列 = 独立复算
- `001-06` 「总求和」行**按既定分段**给出、**各段跨列数与分段一致**、金额 = 独立复算；
          **调整后与原始的入库合计必须不同**
- `001-07` 差异表同样给「合计」，**可求和列限于 原值 / 调整后 / 差额**，整行跨列数 = 表头列数
- `001-08` 材料费**只作引用 · 只读**：不得出现「理论上 =」、不得提供材料费编辑入口
- `001-09` 差异行**可跳转到库存单据**
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.mod06_proc import domain as D
from app.mod06_proc.service import build_page_data, parse_state
from tests.acc_plugin import acc
from tests.m06_helpers import FakeSession, dataset

CASE = "ACC-RPT-PROC-001"
TWO = Decimal("2")

#: 新壳全文（`§19` 批 2 起，"材料费只读"与"差异行跳转"这两条的**观测对象**从旧页换成了壳）
_SHELL = (Path(__file__).resolve().parents[1] / "app" / "web" / "index.html").read_text(
    encoding="utf-8")


def _sess() -> FakeSession:
    return FakeSession(dataset())


def _data(**params) -> dict:
    return build_page_data(_sess(), parse_state(params))


# ⚠️ 2026-09-18（`§19` 批 2）：原先有 4 个**页面观测辅助件**（`_page` 取旧页 html、`_rows`/`_span_sum`
#    按 `colspan` 取格子、`_filter_bar` 切筛选栏那一段）。旧页整体删除（授权 `D18`）后，它们
#    **一处都不再被用**（逐个数过 ✓）⇒ 随之删除；那些"形态"claim 已搬到 `tests/test_wired_m06.py`
#    （默认表 / 单选即收起 / 无只读年月框 / 合计行格数由表头派生 / 空态破折号 / 导出面板口径）。


# ------------------------------------------------------------ 001-01 三表齐备

@acc(CASE, "001-01")
def test_三表齐备且默认停在调整后表():
    labels = [label for _tab, label in D.TABS]
    assert len(D.TABS) == 3
    assert any("原始" in x for x in labels) and any("调整后" in x for x in labels) and any("差异" in x for x in labels)
    assert D.DEFAULT_TAB == D.TAB_ADJUSTED
    assert D.tab_of("") == D.TAB_ADJUSTED and D.tab_of("9") == D.TAB_ADJUSTED
    assert D.tab_of("0") == D.TAB_RAW and D.tab_of("2") == D.TAB_DIFF

    # ⚠️ 2026-09-18（`§19` 批 2）：原先借旧页 html 看「不带参数 ⇒ 落在表② 调整后」；旧页删（`D18`）后
    #    形态搬到壳（`test_wired_m06.py::test_默认停在调整后表` 钉 `procTab` 初值 = 1 ✓）
    #    —— 下面这条**状态**断言是实质，留着。
    assert D.DEFAULT_TAB == parse_state({})["tab"]


# ------------------------------------------------------------ 001-02 逐月一行

@acc(CASE, "001-02")
def test_一个核算月一行且月份升序逐列独立复算():
    data = _data(pj="甲仓", tab=D.TAB_ADJUSTED)
    rows = data["rows"]
    assert [r["ym"] for r in rows] == ["2026-07", "2026-08"], "月份必须升序、一月一行"

    # 逐列 = 独立复算（期望值由桩样本手工推导）
    assert rows[0][f"in_劳保"] == Decimal("20.00")
    assert rows[0][f"in_临时设施"] == Decimal("50.00")
    assert rows[0][f"out_周转材料"] == Decimal("10.00")
    assert rows[1][f"in_主辅材"] == Decimal("80.00")      # 主材 100 → 调整单改成 80
    assert rows[1][f"out_主辅材"] == Decimal("40.00")     # 辅材 40 归入「主辅材」
    assert rows[1][f"in_工具"] == Decimal("30.00")
    # ⚠️ 未登记的物料性质（金额 999）**必须被跳过**，不得凭空进任何列
    assert Decimal("999.00") not in [rows[0][k] for k in D.DATA_KEYS] + [rows[1][k] for k in D.DATA_KEYS]

    totals = D.column_totals(rows)
    for key in D.DATA_KEYS:
        assert totals[key] == sum((r[key] for r in rows), Decimal("0.00")), f"逐列合计不符：{key}"


# ------------------------------------------------------------ 001-03 列结构

@acc(CASE, "001-03")
def test_列结构以主人为准且筛选栏不设只读年月框():
    labels = [c["label"] for c in D.PROC_COLUMNS]
    assert labels[0] == "核算月" and labels[1:6] == [f"入库{c}" for c in D.CATEGORIES]
    assert labels[6:11] == [f"出库{c}" for c in D.CATEGORIES]
    assert labels[11:] == list(D.MECH_COLUMNS)
    assert len(D.PROC_COLUMNS) == 1 + 2 * len(D.CATEGORIES) + len(D.MECH_COLUMNS)

    # 核算月**只作表内列** ⇒ 筛选栏不得出现只读年月框。
    # ⚠️ 2026-09-18（`§19` 批 2）：原先借旧页 html 看这条；旧页删（`D18`）后形态搬到壳
    #    （`test_wired_m06.py::test_筛选栏不设只读年月框` ✓）。


# ------------------------------------------------------------ 001-04 项目单选

@acc(CASE, "001-04")
def test_项目筛选单选且不给全选清空():
    # ⚠️ 2026-09-18（`§19` 批 2）：原先借旧页筛选栏那一段 html 观测（radio / 无多选 / 选中即提交 /
    #    收起态 details）；旧页删（`D18`）后形态搬到壳（`test_wired_m06.py::test_项目筛选单选且选中即收起`
    #    钉 `single:true` 与 `procPjPick` 里 `procPjOpen=false` ✓）。下面的**数据**断言是实质。
    assert _data(pj="甲仓")["rows"] != [] and _data(pj="乙仓")["rows"] != []


# ------------------------------------------------------------ 001-05 逐列合计

@acc(CASE, "001-05")
def test_表一二每个数据列下方给合计行():
    for tab in (D.TAB_RAW, D.TAB_ADJUSTED):
        data = _data(pj="甲仓", tab=tab)
        assert set(data["totals"]) == set(D.DATA_KEYS), "合计必须覆盖每一个数据列"
        # ⚠️ 2026-09-18（`§19` 批 2）：原先借旧页 html 数 `colspan` 之和验「跨列数 = 表头列数」；
        #    旧页删（`D18`）后壳把这条做成了**结构**（`sumRowOf` 的格数由 `thCols(thead)` 派生 ✓）
        #    ⇒ 形态由 `test_wired_m06.py::test_合计行格数由表头派生` 守，上面 `totals` 是实质。


# ------------------------------------------------------------ 001-06 总求和分段

@acc(CASE, "001-06")
def test_总求和按四段给出且跨列数与分段一致():
    adj = _data(pj="甲仓", tab=D.TAB_ADJUSTED)
    segs = adj["segments"]
    assert [s["span"] for s in segs] == [5, 5, 4, 2], "四段 = 入库5 / 出库5 / 机械前4 / 不含税2"
    assert sum(s["span"] for s in segs) == len(D.DATA_KEYS)
    got = {s["name"]: s["total"] for s in segs}
    assert got["入库"] == Decimal("180.00") and got["出库"] == Decimal("50.00")
    assert got["机械"] == Decimal("10.00") and got["不含税"] == Decimal("11.00")
    assert adj["grand_total"] == Decimal("251.00")

    # ⚠️ 2026-09-18（`§19` 批 2）：原先借旧页 html 看「总求和行的跨列数之和 = 表头列数」与各段名；
    #    旧页删（`D18`）后形态搬到壳（`test_wired_m06.py::test_合计行格数由表头派生` ✓）
    #    —— 上面 `segments`（四段 span 与各自金额）与 `grand_total` 是实质。

    # ⭐ 调整后与原始的**入库合计必须不同**（证明确实跟着当前显示的那批走）
    raw = _data(pj="甲仓", tab=D.TAB_RAW)
    raw_in = {s["name"]: s["total"] for s in raw["segments"]}["入库"]
    assert raw_in == Decimal("200.00") != got["入库"]


# ------------------------------------------------------------ 001-07 差异表合计

@acc(CASE, "001-07")
def test_差异表合计只求三列且跨列数对齐():
    data = _data(pj="甲仓", tab=D.TAB_DIFF)
    diffs = data["diffs"]
    assert len(diffs) == 1, "只有被调整单改过的行才进差异表"
    d = diffs[0]
    assert (d["before"], d["after"], d["delta"]) == (Decimal("100.00"), Decimal("80.00"), Decimal("-20.00"))
    assert D.DIFF_SUM_KEYS == ("before", "after", "delta")
    assert all(v is None for k, v in data["diff_totals"].items() if k not in D.DIFF_SUM_KEYS)

    # ⚠️ 2026-09-18（`§19` 批 2）：原先借旧页 html 看「差异表合计行跨列数 = 表头列数」；
    #    旧页删（`D18`）后形态搬到壳（`test_wired_m06.py::test_合计行格数由表头派生` ✓）——
    #    上面 `diffs` / `DIFF_SUM_KEYS` / `diff_totals` 是实质。


# ------------------------------------------------------------ 001-08 材料费只读

@acc(CASE, "001-08")
def test_材料费只作引用只读且无编辑入口():
    assert all(D.COLUMN_SOURCE[k] == D.SOURCE_INV for k in D.MATERIAL_KEYS)
    assert all(D.COLUMN_SOURCE[k] == D.SOURCE_MANUAL for k in D.MECH_KEYS)
    assert D.MATERIAL_READONLY is True

    # ⚠️ 2026-09-18（`§19` 批 2）：原先拿**旧服务端页**渲染结果喂 `D.boundary_violations` 扫描；
    #    旧页删（`D18`）后**改扫新壳**（`backend/app/web/index.html` 全文）—— 同一把尺子、
    #    **换了个更难糊弄的对象**（壳才是现在唯一会渲染材料费的地方 ✓）。
    assert D.boundary_violations(_SHELL) == [], "壳里出现了材料费「理论上 =」或材料费编辑入口"
    # ⚠️ 别用**整壳子串**去扫「理论上」—— 壳里别处的注释就有这三个字（实测撞红 ✗）。
    #    精确的判据是 `D.boundary_violations`（它找的是"材料费 理论上 ="这种**成对**形态 ✓）。
    assert 'name="in_' not in _SHELL and 'name="out_' not in _SHELL, "材料列不得有输入框"
    # 反向：这把尺子**真的会抓**（否证它）
    assert D.boundary_violations(_SHELL, action_ids=("editMaterial",)) != [], "尺子失灵"
    assert D.boundary_violations("材料费 理论上 = 100") != []


# ------------------------------------------------------------ 001-09 差异行跳转

@acc(CASE, "001-09")
def test_差异行可跳转到库存单据():
    data = _data(pj="甲仓", tab=D.TAB_DIFF)
    href = D.jump_query(data["diffs"][0])
    assert href.startswith("/m08?")
    assert "only_adj=1" in href and "pj=%E7%94%B2%E4%BB%93" in href      # 仓库名 = 项目键
    # ⚠️ 2026-09-18（`§19` 批 2）：原先借旧页 html 看「跳转链接渲染出来了」；旧页删（`D18`）后
    #    形态搬到壳 —— 壳里同一件事是**行内动作**（`data-act="goInvAdj"` ＋ 带单据 id），
    #    不是整页跳 `/m08?only_adj=1`（那是**旧页的 URL 形态**）。`jump_query` 的纯函数断言上面已钉 ✓。
    assert 'data-act="goInvAdj"' in _SHELL and "查看原始行" in _SHELL, \
        "壳里没有「差异行 → 库存单据」的入口"
