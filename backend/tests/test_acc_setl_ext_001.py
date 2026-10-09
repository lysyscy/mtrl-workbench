"""`MOD-07` 焊材 / 气体提取 —— 离线自检（**不连库**）。

对应判据 `ACC-SETL-EXT-001`（6 点，`PRD/验收/验收基线.json`）：
- `001-01` 提取表分**焊材 / 气体**两类，各类**合计 = 逐项之和**（独立复算）
- `001-02` 「**金额**」= 所选**月份范围**（独立复算）；「**总金额**」= **全部月累计**、⛔ 不随所选月份变
- `001-03` 「分组合计」**紧贴**本类数据行；该表**刻意不可排**
- `001-04` 「项目状态」默认**在建**；切到归档后无行且给**空态提示行**（跨列数 = 表头列数）
- `001-05` 「重置」回到默认（**月份 ＋ 在建**）
- `001-06` 导出矩阵：行 = 所筛选项目 · 列 = 项目 → **最早有数据的月** → …（逐月连续）→ 求和
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.mod07_setl import domain as D
from app.mod07_setl import extract as X
from app.mod07_setl.service import build_extract_data, parse_extract_state
from tests.acc_plugin import acc
from tests.m07_helpers import (
    ARCHIVED_WAREHOUSE,
    EXTRACT_MONTHS,
    EXTRACT_EXPECT,
    FakeSession,
    extract_dataset,
    indep_extract_kind_total,
    indep_extract_sum,
    indep_extract_total,
)

CASE = "ACC-SETL-EXT-001"

# ⚠️ 2026-09-19（`§19` 批 2）：原先这里还有一整组**页面观测辅助件**（`_page`/`_TBL_RE`/`_table`/`_trs`/
# `_rows_of_kind`/`_sum_row`/`_empty_rows`/`_num`）—— 从**旧页** HTML 里抠数据行 / 合计行 / 空态行 / 数字。
# 旧页删除（授权 `D18`）后它们**零调用**（逐个数过 ✓）⇒ 一并移除。⛔ 判据一条没删，只是换了观测面。


def _data(*, status: str | None = None, period: str | None = None) -> dict:
    params: dict = {}
    if status is not None:
        params["status"] = status
    if period is not None:
        params["ext_period"] = period
    return build_extract_data(FakeSession(extract_dataset()), parse_extract_state(params))


# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 2**）：原先这里还有个 `_page()`（取旧页 HTML）；
# 旧页删除（授权 `D18`）后它**零调用**（逐个数过 ✓）⇒ 移除。本文件此后**只读数据出口**（`_data()`），
# 形态 claim 全部在 `tests/test_wired_m07.py`（两类按序且合计行紧贴 / 按状态过滤＋空态跨列派生 /
# 重置回默认 / 导出真下载 …）。⛔ 判据一条没删。


def _kind_block(data: dict, kind: str) -> dict:
    """该类的数据块（`blocks` 里按 `kind` 取 —— **行序就是装配行序** ✓）。"""
    return next(b for b in data["blocks"] if b["kind"] == kind)


def _kind_rows(data: dict, kind: str) -> list[dict]:
    return _kind_block(data, kind)["rows"]




# ============================================================ 判据点

@acc(CASE, "001-01")
def test_两类齐备且各类合计等于逐项之和():
    data = _data(period="2026-08")

    for kind in X.KINDS:
        rows = _kind_rows(data, kind)
        assert rows, f"{kind} 没有数据行"
        # 逐项「总金额」= 独立复算（手写期望表）
        for r in rows:
            assert r["total"] == indep_extract_total(kind, r["warehouse"]), r
        # 合计行 = **逐项之和**（独立复算，不抄任何一行）
        total = _kind_block(data, kind)["total_row"]
        assert total["total"] == sum((r["total"] for r in rows), Decimal("0.00"))
        assert total["total"] == indep_extract_kind_total(kind)
        assert total["amount"] == sum((r["amount"] for r in rows), Decimal("0.00"))

    # ⛔ 近名物料**不命中**：白名单是精确匹配（「氧气瓶」/「氩气表」两条 555 / 333 都不进气体）
    gas_aug = [r for r in _kind_rows(data, "气体") if r["warehouse"] == "甲仓"][0]
    assert gas_aug["amount"] == indep_extract_sum("气体", "甲仓", ["2026-08"]) == Decimal("400.00")

    # 规则机制（两类各一条，防止"看着像就收"）：
    rules = X.default_rules()
    assert X.match_kind("氧气管", "气体", rules) is False          # 白名单外 ⇒ 不收
    assert X.match_kind("氧气", "气体", rules) is True
    assert X.match_kind("焊条J422", "焊材", rules) is True
    assert X.match_kind("电缆", "焊材", rules) is False            # 关键词外 ⇒ 不收
    assert X.match_kind("焊条箱", "焊材", X.extract_rules(not_weld=("箱",))) is False   # **排除子串**生效
    assert X.match_kind("焊条J422", "焊材", X.extract_rules(not_weld=("箱",))) is True


@acc(CASE, "001-02")
def test_金额按所选月份范围而总金额恒为全月累计():
    aug = _data(period="2026-08")
    jun = _data(period="2026-06")

    def cell(d: dict, kind: str, wh: str) -> dict:
        return next(r for r in _kind_rows(d, kind) if r["warehouse"] == wh)

    # ① 切月 ⇒「金额」跟着换（且 = 独立复算），「总金额」**一动不动**
    for kind, wh, m in (("焊材", "甲仓", "2026-08"), ("气体", "甲仓", "2026-08")):
        a, b = cell(aug, kind, wh), cell(jun, kind, wh)
        assert a["total"] == b["total"] == indep_extract_total(kind, wh), "总金额应恒为全月累计"
        assert a["amount"] == indep_extract_sum(kind, wh, ["2026-08"])
        assert b["amount"] == indep_extract_sum(kind, wh, ["2026-06"])
        assert a["amount"] != b["amount"], "切月后「金额」没变 ⇒ 断言失去区分力"

    # ② 跨月 / 年 / 全部 三种范围也各按独立复算
    span = _data(period="2026-06~2026-08")
    assert cell(span, "焊材", "甲仓")["amount"] == indep_extract_sum(
        "焊材", "甲仓", ["2026-06", "2026-07", "2026-08"])
    assert cell(_data(period="2026"), "焊材", "甲仓")["amount"] == indep_extract_total("焊材", "甲仓")
    assert cell(_data(period=""), "焊材", "甲仓")["amount"] == indep_extract_total("焊材", "甲仓")
    # 只覆盖 06 的月份：金额 = 全月，但 08 有数据的仓在 06 下金额为 0
    assert cell(jun, "焊材", "乙仓")["amount"] == Decimal("0.00")
    assert cell(jun, "焊材", "乙仓")["total"] == Decimal("500.00")


@acc(CASE, "001-03")
def test_分组合计紧贴本类数据行且整表不可排():
    data = _data(period="2026-08")
    # 每个块**自带**数据行与合计行，块序 = 两类顺序 ⇒ 合计行**紧贴**本类数据行（不是表尾一张总合计）
    assert [b["kind"] for b in data["blocks"]] == list(X.KINDS), "块顺序 ≠ 两类顺序"
    for b in data["blocks"]:
        assert b["rows"], f"{b['kind']} 没有数据行"
        assert b["total_row"], f"{b['kind']} 没有合计行"
    # 刻意不可排：四列全部 sortable=False
    assert all(c["sortable"] is False for c in X.EXTRACT_COLUMNS)
    # ⚠️ 2026-09-19（`§19` 批 2）：原先这里从**旧页**的 `<tr>` 属性串判行序 / 合计行位置 / `nosort` 标记
    # （"合计行紧贴本类数据行"本是**页面形态**）；旧页删除（授权 `D18`）后形态搬到壳 ——
    # `test_wired_m07.py::test_壳里提取表两类按序且合计行紧贴`（`${extBlock('焊材')}${extBlock('气体')}`
    # ＋ `sumRowOf(EXT_THEAD, …, {lead:kind+'合计'})` 在**块内** ＋ 该表不帯 `data-sort` ✓）。


@acc(CASE, "001-04")
def test_项目状态默认在建且归档下给空态提示行():
    # ① 默认「在建」（取数口径）；⚠️ "页面选中项"那半已搬壳（壳的 `extVisible` 按状态过滤 ✓）
    assert parse_extract_state({})["status"] == "在建"
    assert X.visible_warehouses({ARCHIVED_WAREHOUSE: {"2026-08": Decimal("1.00")}},
                                statuses={}, status="在建") == [], "归档仓进了「在建」的可见集"

    # ② 在建下的行序 = **项目档案顺序**（ord：乙仓 1 → 甲仓 2）
    data = _data()
    assert [r["warehouse"] for r in _kind_rows(data, "焊材")] == ["乙仓", "甲仓"]

    # ③ 切「归档」⇒ 两类都无数据行
    arch = _data(status="归档", period="2026-08")
    for kind in X.KINDS:
        assert _kind_rows(arch, kind) == [], f"归档下 {kind} 不该有行"
    # ⚠️ 2026-09-19（`§19` 批 2）：原先这里从**旧页**数空态提示行的 `colspan`（= 表头列数）；
    # 旧页删除（授权 `D18`）后形态搬到壳 ——
    # `test_wired_m07.py::test_壳里按项目状态过滤且空态跨列派生`（`extBlock` 的空态行
    # `EMPTYROW(thCount(EXT_THEAD), …)` ＋ 点名哪一类 ✓）。

    # ④ 陌生仓库（档案里没有）**只在「全部」下出现** —— 状态取自档案，不臆造"在建"
    alien = {"丁仓": {"2026-08": Decimal("1.00")}}
    assert X.visible_warehouses(alien, statuses={}, status="在建") == []
    assert X.visible_warehouses(alien, statuses={}, status=X.STATUS_ALL) == ["丁仓"]


@acc(CASE, "001-05")
def test_重置回到默认月份与在建():
    # ⚠️ 2026-09-19（`§19` 批 2）：原先这里看**旧页**的「重置」链接（`href="/m07/extract"`）；
    # 旧页删除（授权 `D18`）后形态搬到壳 —— `test_wired_m07.py::test_壳里提取页重置回在建与上月` ✓。

    default = parse_extract_state({})
    assert default["status"] == "在建" == X.STATUS_DEFAULT
    assert default["period"] == D.default_month()[:4]       # 年份默认 = 上月所属年（TAIL-266）
    # 带参数的筛选**原样生效**（不被默认值盖掉）
    st = parse_extract_state({"status": "全部", "ext_period": "2026-06"})
    assert st == {"status": "全部", "period": "2026-06", "explicit": True}
    # 认不出的状态取值 ⇒ 回落默认，不臆造
    assert parse_extract_state({"status": "瞎写"})["status"] == X.STATUS_DEFAULT
    # ⚠️ 2026-09-19（`§19` 批 2）：原先这条查旧页「筛选栏必须包在表单里，否则『查询』按钮是死的」；
    # 新壳**没有表单 / 查询按钮**这一层 —— 筛选控件直接绑状态、一改就重取数（见 `test_wired_m07.py`
    # 的「切月份切项目都重取数」）⇒ 那个形态问题在壳里**不存在**，随页移除。


@acc(CASE, "001-06")
def test_导出矩阵按项目与月份连续展开():
    data = _data(period="2026-08")
    ex = next(e for e in data["export"] if e["kind"] == "焊材")

    # ① 列 = 项目 → **最早有数据的月** → …（逐月连续）→ 求和
    assert ex["months"] == list(EXTRACT_MONTHS) == data["months"], ex["months"]
    assert ex["months"][0] == min(EXTRACT_MONTHS)

    list_now = [r["warehouse"] for r in _kind_rows(data, "焊材")]
    assert len(ex["rows"]) == len(list_now), "矩阵行数应 = 所筛选项目数"
    assert [r["warehouse"] for r in ex["rows"]] == list_now

    # ② 末列「求和」= 该项目**全月累计**（与「总金额」列同源）
    for r in ex["rows"]:
        assert r["total"] == indep_extract_total("焊材", r["warehouse"])
        assert r["total"] == sum(r["cells"], Decimal("0.00"))

    # ③ 合计行的每一列 = 该列逐项之和
    for i, month in enumerate(EXTRACT_MONTHS):
        assert ex["sum_row"][i] == sum(
            (indep_extract_sum("焊材", r["warehouse"], [month]) for r in ex["rows"]), Decimal("0.00"))
    assert ex["sum_row"][-1] == indep_extract_kind_total("焊材")

    # ④ 气体矩阵同款（月份列**与焊材一致** ⇒ 两个分组列对齐）
    ex2 = next(e for e in data["export"] if e["kind"] == "气体")
    assert ex2["months"] == ex["months"]

    # ⑤ 归档筛选下不再有数据（⛔ 不渲染假数据）；**空态行**那半是形态 ⇒ 搬到壳 ——
    #   `test_wired_m07.py::test_壳里按项目状态过滤且空态跨列派生` ✓
    arch = _data(status="归档", period="2026-08")
    assert all(not _kind_rows(arch, k) for k in X.KINDS)
