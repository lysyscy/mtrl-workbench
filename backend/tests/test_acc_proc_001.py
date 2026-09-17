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

import re
from decimal import Decimal

from app.mod06_proc import domain as D
from app.mod06_proc.service import build_page_data, parse_state
from app.mod06_proc.view import render_proc_page
from tests.acc_plugin import acc
from tests.m06_helpers import FakeSession, dataset

CASE = "ACC-RPT-PROC-001"
TWO = Decimal("2")


def _sess() -> FakeSession:
    return FakeSession(dataset())


def _data(**params) -> dict:
    return build_page_data(_sess(), parse_state(params))


def _page(**params) -> str:
    return render_proc_page(_data(**params))


def _rows(html: str, kind: str) -> str:
    """取某类行（`sumrow` 合计 / `tot` 总求和）的整段 `<tr>…</tr>`。"""
    m = re.search(rf'<tr class="{kind}[^"]*"[^>]*>(.*?)</tr>', html, re.S)
    assert m, f"页面里没有 {kind} 行"
    return m.group(1)


def _span_sum(row_html: str) -> int:
    """一行里各格 `colspan` 之和（缺省 1）。"""
    total = 0
    for cell in re.findall(r"<td[^>]*>", row_html):
        m = re.search(r'colspan="(\d+)"', cell)
        total += int(m.group(1)) if m else 1
    return total


def _filter_bar(html: str) -> str:
    """**筛选栏那一段**（`data-seg="filter"` → 数据区之前）。

    ⚠️ 本页有**两套「项目」UI**：筛选栏 = 单选（radio），导出展开区 = 多选（checkbox）。
       整页 `in` / `not in` 断言**分不开这两套** —— 2026-09-17 加导出展开区（`ACC-RPT-EXP-001`）
       时实测把「不给多选」那条整页断言撞红。凡断言"筛选栏里怎样"就绑到这一段。
    """
    i = html.index('data-seg="filter"')
    j = min(html.index('data-seg="exp-strip"'), html.index('<div class="tw"'))
    assert i < j, "筛选栏不在数据区之前"
    return html[i:j]


# ------------------------------------------------------------ 001-01 三表齐备

@acc(CASE, "001-01")
def test_三表齐备且默认停在调整后表():
    labels = [label for _tab, label in D.TABS]
    assert len(D.TABS) == 3
    assert any("原始" in x for x in labels) and any("调整后" in x for x in labels) and any("差异" in x for x in labels)
    assert D.DEFAULT_TAB == D.TAB_ADJUSTED
    assert D.tab_of("") == D.TAB_ADJUSTED and D.tab_of("9") == D.TAB_ADJUSTED
    assert D.tab_of("0") == D.TAB_RAW and D.tab_of("2") == D.TAB_DIFF

    html = _page()                       # 不带参数 ⇒ 落在默认表
    assert f"tab={D.TAB_ADJUSTED}" in html
    assert "总求和（本表）" in html      # 默认表渲染的是 17 列矩阵（表①② 同构）
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

    # 核算月**只作表内列** ⇒ 筛选栏不得出现只读年月框
    html = _page()
    assert 'name="period"' not in html and "readonly" not in html


# ------------------------------------------------------------ 001-04 项目单选

@acc(CASE, "001-04")
def test_项目筛选单选且不给全选清空():
    html = _page()
    # ⚠️ 绑到**筛选栏那一段**（见 `_filter_bar`）—— 整页断言会被导出展开区（多选面板）喂饱
    bar = _filter_bar(html)
    assert 'type="radio" name="pj"' in bar
    assert 'type="checkbox"' not in bar, "筛选栏的项目选择必须是单选，不给多选"
    assert "全选" not in bar and "清空" not in bar
    # 选中即收起：radio 变更即提交；面板是**收起态**的 `<details>`（不为选中项预先展开）
    assert 'onchange="this.form.submit()"' in bar
    assert "<details>" in bar and "<details open>" not in bar
    # 切换项目后行数随之切换
    assert _data(pj="甲仓")["rows"] != [] and _data(pj="乙仓")["rows"] != []


# ------------------------------------------------------------ 001-05 逐列合计

@acc(CASE, "001-05")
def test_表一二每个数据列下方给合计行():
    for tab in (D.TAB_RAW, D.TAB_ADJUSTED):
        data = _data(pj="甲仓", tab=tab)
        assert set(data["totals"]) == set(D.DATA_KEYS), "合计必须覆盖每一个数据列"
        html = render_proc_page(data)
        row = _rows(html, "sumrow")
        assert _span_sum(row) == len(D.PROC_COLUMNS), "合计行的格数必须 = 表头列数（派生，不写死）"
        assert re.search(r"<td[^>]*>合计</td>", row)


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

    html = render_proc_page(adj)
    tot_row = _rows(html, "tot")
    assert _span_sum(tot_row) == len(D.PROC_COLUMNS), "总求和行的跨列数之和 = 表头列数"
    for name in got:
        assert f"{name}合计" in tot_row

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

    html = render_proc_page(data)
    row = _rows(html, "sumrow")
    assert _span_sum(row) == len(D.DIFF_COLUMNS), "差异表合计行跨列数 = 表头列数"


# ------------------------------------------------------------ 001-08 材料费只读

@acc(CASE, "001-08")
def test_材料费只作引用只读且无编辑入口():
    assert all(D.COLUMN_SOURCE[k] == D.SOURCE_INV for k in D.MATERIAL_KEYS)
    assert all(D.COLUMN_SOURCE[k] == D.SOURCE_MANUAL for k in D.MECH_KEYS)
    assert D.MATERIAL_READONLY is True

    for tab in (D.TAB_RAW, D.TAB_ADJUSTED, D.TAB_DIFF):
        html = render_proc_page(_data(pj="甲仓", tab=tab))
        assert D.boundary_violations(html) == []
        assert "理论上" not in html
        assert 'name="in_' not in html and 'name="out_' not in html, "材料列不得有输入框"
        assert D.boundary_violations(html, action_ids=("editMaterial",)) != []
        assert D.boundary_violations("材料费 理论上 = 100") != []


# ------------------------------------------------------------ 001-09 差异行跳转

@acc(CASE, "001-09")
def test_差异行可跳转到库存单据():
    data = _data(pj="甲仓", tab=D.TAB_DIFF)
    href = D.jump_query(data["diffs"][0])
    assert href.startswith("/m08?")
    assert "only_adj=1" in href and "pj=%E7%94%B2%E4%BB%93" in href      # 仓库名 = 项目键
    html = render_proc_page(data)
    assert href.replace("&", "&amp;") in html or href in html
    assert "查看原始行" in html
