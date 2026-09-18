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
from app.mod07_setl.view import render_extract_page
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

_TBL_RE = re.compile(r'<table class="dt" data-sort-key="m07:kinds">(.*?)</table>', re.S)


def _data(*, status: str | None = None, period: str | None = None) -> dict:
    params: dict = {}
    if status is not None:
        params["status"] = status
    if period is not None:
        params["ext_period"] = period
    return build_extract_data(FakeSession(extract_dataset()), parse_extract_state(params))


def _page(*, status: str | None = None, period: str | None = None) -> str:
    return render_extract_page(_data(status=status, period=period))


def _table(html: str) -> str:
    m = _TBL_RE.search(html)
    assert m, "没找到提取表（`data-sort-key=\"m07:kinds\"`）"
    return m.group(0)


def _trs(html: str) -> list[tuple[str, list[str]]]:
    body = re.search(r"<tbody>(.*?)</tbody>", _table(html), re.S).group(1)
    out: list[tuple[str, list[str]]] = []
    for attrs, inner in re.findall(r"<tr\b([^>]*)>(.*?)</tr>", body, re.S):
        out.append((attrs, [re.sub(r"<[^>]*>", "", c).strip()
                            for c in re.findall(r"<td\b[^>]*>(.*?)</td>", inner, re.S)]))
    return out


def _rows_of_kind(html: str, kind: str) -> list[dict]:
    """某一类的**数据行**（按出现顺序）。"""
    out: list[dict] = []
    for attrs, cells in _trs(html):
        if "empty" in attrs or "sum" in attrs or not cells or cells[0] != kind:
            continue
        out.append({"warehouse": cells[1], "total": Decimal(cells[2].replace(",", "")),
                    "amount": Decimal(cells[3].replace(",", ""))})
    return out


def _sum_row(html: str, kind: str) -> dict:
    for attrs, cells in _trs(html):
        if "sum" in attrs and cells and cells[0] == f"{kind}合计":
            return {"total": Decimal(cells[1].replace(",", "")),
                    "amount": Decimal(cells[2].replace(",", ""))}
    raise AssertionError(f"没找到「{kind}合计」行")


def _empty_rows(html: str) -> list[str]:
    return [cells[0] for attrs, cells in _trs(html) if "empty" in attrs and cells]


def _num(text: str) -> Decimal:
    return Decimal(re.sub(r"[^\d.\-]", "", text) or "0")


# ============================================================ 判据点

@acc(CASE, "001-01")
def test_两类齐备且各类合计等于逐项之和():
    html = _page(period="2026-08")

    for kind in X.KINDS:
        rows = _rows_of_kind(html, kind)
        assert rows, f"{kind} 没有数据行"
        # 逐项「总金额」= 独立复算（手写期望表）
        for r in rows:
            assert r["total"] == indep_extract_total(kind, r["warehouse"]), r
        # 合计行 = **逐项之和**（独立复算，不抄任何一行）
        total = _sum_row(html, kind)
        assert total["total"] == sum((r["total"] for r in rows), Decimal("0.00"))
        assert total["total"] == indep_extract_kind_total(kind)
        assert total["amount"] == sum((r["amount"] for r in rows), Decimal("0.00"))

    # ⛔ 近名物料**不命中**：白名单是精确匹配（「氧气瓶」/「氩气表」两条 555 / 333 都不进气体）
    gas_aug = [r for r in _rows_of_kind(html, "气体") if r["warehouse"] == "甲仓"][0]
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
    aug = _page(period="2026-08")
    jun = _page(period="2026-06")

    def cell(html: str, kind: str, wh: str) -> dict:
        return next(r for r in _rows_of_kind(html, kind) if r["warehouse"] == wh)

    # ① 切月 ⇒「金额」跟着换（且 = 独立复算），「总金额」**一动不动**
    for kind, wh, m in (("焊材", "甲仓", "2026-08"), ("气体", "甲仓", "2026-08")):
        a, b = cell(aug, kind, wh), cell(jun, kind, wh)
        assert a["total"] == b["total"] == indep_extract_total(kind, wh), "总金额应恒为全月累计"
        assert a["amount"] == indep_extract_sum(kind, wh, ["2026-08"])
        assert b["amount"] == indep_extract_sum(kind, wh, ["2026-06"])
        assert a["amount"] != b["amount"], "切月后「金额」没变 ⇒ 断言失去区分力"

    # ② 跨月 / 年 / 全部 三种范围也各按独立复算
    span = _page(period="2026-06~2026-08")
    assert cell(span, "焊材", "甲仓")["amount"] == indep_extract_sum(
        "焊材", "甲仓", ["2026-06", "2026-07", "2026-08"])
    assert cell(_page(period="2026"), "焊材", "甲仓")["amount"] == indep_extract_total("焊材", "甲仓")
    assert cell(_page(period=""), "焊材", "甲仓")["amount"] == indep_extract_total("焊材", "甲仓")
    # 只覆盖 06 的月份：金额 = 全月，但 08 有数据的仓在 06 下金额为 0
    assert cell(jun, "焊材", "乙仓")["amount"] == Decimal("0.00")
    assert cell(jun, "焊材", "乙仓")["total"] == Decimal("500.00")


@acc(CASE, "001-03")
def test_分组合计紧贴本类数据行且整表不可排():
    html = _page(period="2026-08")
    trs = _trs(html)
    kinds = [("[sum]" if "sum" in a else ("[empty]" if "empty" in a else (c[0] if c else "?")))
             for a, c in trs]

    # 行序 = 焊材数据行… → **焊材合计** → 气体数据行… → **气体合计**
    assert kinds == ["焊材", "焊材", "[sum]", "气体", "气体", "[sum]"], kinds
    assert trs[2][1][0] == "焊材合计" and trs[5][1][0] == "气体合计"
    # 合计行**紧贴**本类数据行 ⇒ 它后面紧跟的是另一类的数据行（不是表尾）
    assert trs[3][1][0] == "气体"

    # 刻意不可排：整表**没有** `data-sort` 属性、每个 `<th>` 都是 `nosort`、四列全部 sortable=False
    assert "data-sort " not in _table(html).replace("data-sort-key", "")
    ths = re.findall(r"<th\b[^>]*>", _table(html))
    assert len(ths) == len(X.EXTRACT_COLUMNS) and all("nosort" in t for t in ths)
    assert all(c["sortable"] is False for c in X.EXTRACT_COLUMNS)


@acc(CASE, "001-04")
def test_项目状态默认在建且归档下给空态提示行():
    # ① 默认「在建」：页面选中项 = 在建，且**不含归档仓**
    html = _page()
    sel = re.search(r'<select name="status">(.*?)</select>', html, re.S).group(1)
    assert 'value="在建" selected' in sel
    assert ARCHIVED_WAREHOUSE not in html

    # ② 在建下的行序 = **项目档案顺序**（ord：乙仓 1 → 甲仓 2）
    assert [r["warehouse"] for r in _rows_of_kind(html, "焊材")] == ["乙仓", "甲仓"]

    # ③ 切「归档」⇒ 两类都无数据行，且**各自**给空态提示行，跨列数 = 表头列数（独立数 <th>）
    arch = _page(status="归档", period="2026-08")
    for kind in X.KINDS:
        assert _rows_of_kind(arch, kind) == [], f"归档下 {kind} 不该有行"
    empties = _empty_rows(arch)
    assert len(empties) == len(X.KINDS)
    ths = len(re.findall(r"<th\b[^>]*>", _table(arch)))
    body = re.search(r"<tbody>(.*?)</tbody>", _table(arch), re.S).group(1)
    spans = [int(re.search(r'colspan="(\d+)"', inner).group(1))
             for attrs, inner in re.findall(r"<tr\b([^>]*)>(.*?)</tr>", body, re.S)
             if "empty" in attrs]
    assert spans == [ths, ths], f"空态跨列数 {spans} ≠ 表头列数 {ths}"

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
    assert default["period"] == D.default_month()           # 月份默认 = 上月（§9.2）
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
    html = _page(period="2026-08")
    m = re.search(r'<table class="dt" data-sort-key="modal:expExt-焊材">(.*?)</table>', html, re.S)
    assert m, "导出弹窗里没有焊材矩阵"
    tbl = m.group(1)
    heads = [re.sub(r"<[^>]*>", "", x).strip() for x in re.findall(r"<th\b[^>]*>(.*?)</th>", tbl, re.S)]

    # ① 列 = 项目 → **最早有数据的月** → …（逐月连续）→ 求和
    assert heads == ["项目", *EXTRACT_MONTHS, "求和"], heads
    assert heads[1] == min(EXTRACT_MONTHS)

    # ⚠️ 只取 tbody（`<thead>` 的表头行也是 `<tr>`，混进来会多算一行）
    body = re.search(r"<tbody>(.*?)</tbody>", tbl, re.S).group(1)
    data_rows = [[re.sub(r"<[^>]*>", "", x).strip()
                  for x in re.findall(r"<td\b[^>]*>(.*?)</td>", inner, re.S)]
                 for attrs, inner in re.findall(r"<tr\b([^>]*)>(.*?)</tr>", body, re.S)
                 if "empty" not in attrs]
    list_now = [r["warehouse"] for r in _rows_of_kind(html, "焊材")]
    assert len(data_rows) == len(list_now) + 1, "矩阵行数应 = 所筛选项目数 ＋ 合计行"
    assert [r[0] for r in data_rows[:-1]] == list_now
    assert data_rows[-1][0] == "焊材合计"

    # ② 末列「求和」= 该项目**全月累计**（与页面「总金额」列同源）
    for r in data_rows[:-1]:
        wh = r[0]
        assert _num(r[-1]) == indep_extract_total("焊材", wh)
        assert _num(r[-1]) == sum((_num(x) for x in r[1:-1]), Decimal("0.00"))
    # ③ 合计行的每一列 = 该列逐项之和
    for i, month in enumerate(EXTRACT_MONTHS, start=1):
        assert _num(data_rows[-1][i]) == sum(
            (indep_extract_sum("焊材", wh, [month]) for wh in list_now), Decimal("0.00"))
    assert _num(data_rows[-1][-1]) == indep_extract_kind_total("焊材")

    # ④ 气体矩阵同款（月份列**与焊材一致** ⇒ 两个分组列对齐）
    m2 = re.search(r'<table class="dt" data-sort-key="modal:expExt-气体">(.*?)</table>', html, re.S)
    heads2 = [re.sub(r"<[^>]*>", "", x).strip()
              for x in re.findall(r"<th\b[^>]*>(.*?)</th>", m2.group(1), re.S)]
    assert heads2 == heads

    # ⑤ 归档筛选下矩阵也给**空态行**（不渲染假数据）
    arch = _page(status="归档", period="2026-08")
    assert "当前筛选条件下没有焊材数据" in arch
