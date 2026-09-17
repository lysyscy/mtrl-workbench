"""`MOD-08` 库存单据与调整单 —— 离线自检（**不连库**）。

对应判据 `ACC-INV-001`（13 点，`PRD/验收/验收基线.json`）：
- `001-01` 明细总表列结构以 §5.4 / §3.4 为准（列名与列数**回主人**，此处不复述）
- `001-02` 默认核算年月 = 北京时间**上月**；切「全部」后行数变多；「重置」回到默认
- `001-03` 按**项目**（键 = **仓库名**）筛选生效，行数 = 独立复算
- `001-04` 按**出入库方向**筛选生效
- `001-05` **每列可筛**（除末列「操作」），列条件之间「与」
- `001-06` 数值列既给「≥ / ≤」**区间**也给**值清单**，且勾选**真的生效**
- `001-07` 表内「合计」行逐列 = 独立复算 · 随筛选变 · 单价列不求和
- `001-08` 筛选为空时必须有**空态提示行**
- `001-09` 调整单**只改「调整后金额」**，原始值不被覆盖
- `001-10` 调整后金额走统一金额出口：**负值被拦、0 合法**
- `001-11` 抓取入口的弹窗**默认月份 = 本页当前所选核算年月**
- `001-12` 朴素导出与「含数据透视表」并存互不影响；**后者提示与模板实际形态一致**
- `001-13` 不新增删除入口、不建「是否作废」字段
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from app.core.money import sum_money
from app.core.period import default_period
from app.mod08_inv import domain as D
from app.mod08_inv.models import InvDetail
from app.mod08_inv.repository import load_rows, save_adjustment
from app.mod08_inv.service import build_page_data, parse_state
from app.mod08_inv.view import render_inv_page
from tests.acc_plugin import acc
from tests.m08_helpers import FakeSession, dataset

CASE = "ACC-INV-001"


def _sess() -> FakeSession:
    return FakeSession(dataset())


def _page(**params) -> str:
    return render_inv_page(build_page_data(_sess(), parse_state(params)))


def _sum_cells(html: str) -> list[str]:
    """合计行（`<tr class="sum…" data-pin="1">`）里的各格原文。"""
    m = re.search(r'<tr class="sum[^"]*"[^>]*>(.*?)</tr>', html, re.S)
    assert m, "页面里没有合计行"
    return re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)


def _th_labels(html: str) -> list[str]:
    head = re.search(r"<thead>(.*?)</thead>", html, re.S).group(1)
    raw = [re.sub(r"<[^>]*>", "", x) for x in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)]
    return [x.replace("&#8597;", "").strip() for x in raw]      # 去掉排序箭头（骨架自带）


# ------------------------------------------------------------ 001-01 列结构


@acc(CASE, "001-01")
def test_列结构以主人为准且只有一个定义处():
    labels = [c["label"] for c in D.INV_TABLE_COLUMNS]
    html = _page(period="2026-08")

    # ① 渲染出来的表头 = 唯一出口给的那份（列数派生，**不写死数字**）
    assert _th_labels(html) == labels
    assert len(_th_labels(html)) == len(D.INV_TABLE_COLUMNS)

    # ② §3.4「关键字段」逐项都有落点；**刻意不建的**必须显式登记为 None
    for name, key in D.KEY_FIELD_MAP:
        if key is None:
            assert name not in labels, f"「{name}」已裁定不建（NG-06），不得出现在列里"
        else:
            assert key in {c["key"] for c in D.INV_TABLE_COLUMNS}, f"§3.4 关键字段缺落点：{name}"

    # ③ 末列固定是「操作」且天然不可排（R13）
    assert D.INV_TABLE_COLUMNS[-1]["key"] == "ops"
    assert D.PAGE_ONLY_KEYS == ("ops",)


# ------------------------------------------------------------ 001-02 默认核算年月


@acc(CASE, "001-02")
def test_默认核算年月是北京时间上月():
    assert default_period("inventory", now=date(2026, 9, 16)) == "2026-08"   # 材料报表类 = 上月
    assert default_period("inventory", now=date(2026, 1, 3)) == "2025-12"    # 跨年不越界
    assert parse_state({})["period"] == default_period("inventory")


@acc(CASE, "001-02")
def test_切全部行数变多且重置回到默认():
    rows = load_rows(_sess())
    month = D.filter_rows(rows, ym="2026-08")
    everything = D.filter_rows(rows, ym="")
    assert len(everything) > len(month), "「全部」应比单月多"
    # 重置 = 回到默认（页面上「重置」指向不带参数的 /m08）
    assert 'href="/m08"' in _page(period="2026-01~2026-06")


# ------------------------------------------------------------ 001-03 / 004 粗筛


@acc(CASE, "001-03")
def test_按项目筛选键是仓库名():
    rows = load_rows(_sess())
    got = D.filter_rows(rows, ym="2026-08", projects=["甲仓"])
    expect = [r for r in rows if r["ym"] == "2026-08" and r["warehouse"] == "甲仓"]
    assert len(got) == len(expect) == 2, "行数必须 = 独立复算"
    assert all(r["warehouse"] == "甲仓" for r in got)
    # 复位（不传项目）⇒ 回到全量
    assert len(D.filter_rows(rows, ym="2026-08")) == 3


@acc(CASE, "001-04")
def test_按出入库方向筛选():
    rows = load_rows(_sess())
    total = D.filter_rows(rows, ym="2026-08")
    ins = D.filter_rows(rows, ym="2026-08", direction=D.DIRECTION_IN)
    assert 0 < len(ins) < len(total)
    assert all(r["direction"] == "入库" for r in ins)
    assert D.filter_rows(rows, ym="2026-08", direction=D.DIRECTION_ALL) == total


# ------------------------------------------------------------ 001-05 每列可筛


@acc(CASE, "001-05")
def test_除操作列外每列都有筛选入口():
    html = _page(period="2026-08")
    assert set(D.filterable_keys()) == {c["key"] for c in D.INV_TABLE_COLUMNS} - set(D.PAGE_ONLY_KEYS)
    for key in D.filterable_keys():
        has = f'name="f_{key}"' in html or f'name="f_{key}_v"' in html
        assert has, f"「{key}」列没有筛选入口"
    assert 'name="f_ops"' not in html, "末列「操作」不该有筛选入口"


@acc(CASE, "001-05")
def test_列条件之间是与关系():
    rows = load_rows(_sess())
    only_ins = D.filter_rows(rows, ym="2026-08", col_filters={"direction": {"v": ["入库"]}})
    both = D.filter_rows(rows, ym="2026-08", col_filters={
        "direction": {"v": ["入库"]}, "warehouse": {"v": ["甲仓"]}})
    expect = [r for r in rows if r["ym"] == "2026-08"
              and r["direction"] == "入库" and r["warehouse"] == "甲仓"]
    assert len(only_ins) == 2 and len(both) == 1
    assert len(both) == len(expect), "列间「与」的结果必须 = 独立复算"


# ------------------------------------------------------------ 001-06 数值列


@acc(CASE, "001-06")
def test_数值列既给区间也给值清单且勾选真的生效():
    rows = load_rows(_sess())
    # 区间
    gt = D.filter_rows(rows, ym="2026-08", col_filters={"amount": {"min": "50"}})
    assert [r["amount"] for r in gt] == [Decimal("100.00"), Decimal("200.00")]
    le = D.filter_rows(rows, ym="2026-08", col_filters={"amount": {"max": "50"}})
    assert [r["amount"] for r in le] == [Decimal("40.00")]

    # 值清单勾选（原型曾漏判 ⇒ 这里必须真的生效）
    picked = D.filter_rows(rows, ym="2026-08", col_filters={"amount": {"v": ["200.00"]}})
    assert [r["amount"] for r in picked] == [Decimal("200.00")]
    # 区间与勾选是「与」
    both = D.filter_rows(rows, ym="2026-08", col_filters={"amount": {"min": "50", "v": ["100.00"]}})
    assert [r["amount"] for r in both] == [Decimal("100.00")]

    # 页面：数值列同时有 ≥/≤ 与值清单
    html = _page(period="2026-08")
    assert 'name="f_amount_min"' in html and 'name="f_amount_max"' in html
    assert 'name="f_amount_v"' in html
    assert D.distinct_values(rows, "amount", ym="2026-08") == ["100.00", "200.00", "40.00"]


# ------------------------------------------------------------ 001-07 表内合计


@acc(CASE, "001-07")
def test_合计行逐列独立复算且随筛选变():
    rows = load_rows(_sess())
    got = D.filter_rows(rows, ym="2026-08")
    sums = D.sum_cells(got)

    assert sums["amount"] == sum_money([r["amount"] for r in got]) == Decimal("340.00")
    assert sums["qty"] == Decimal("34.00")
    assert sums["tax_total"] == Decimal("379.00")
    # 调整后金额 = 调整单的值（只那一行有）
    assert sums[D.ADJ_KEY] == Decimal("30.00")
    # ⛔ 两个单价列**刻意不求和**
    assert D.NO_SUM_KEYS == ("price_excl", "price_incl")
    assert sums["price_excl"] is None and sums["price_incl"] is None

    # 随筛选变
    narrowed = D.sum_cells(D.filter_rows(rows, ym="2026-08", direction=D.DIRECTION_IN))
    assert narrowed["amount"] == Decimal("300.00") != sums["amount"]


@acc(CASE, "001-07")
def test_合计行在表内且列数对齐():
    html = _page(period="2026-08")
    tbody = re.search(r"<tbody>(.*)</tbody>", html, re.S).group(1)
    assert 'class="sum' in tbody, "合计行必须在 tbody 内"
    cells = _sum_cells(html)
    assert len(cells) == len(D.INV_TABLE_COLUMNS), "合计行的格数必须 = 表头列数（不写死数字）"
    assert cells[0] == "合计"                                            # 首格写「合计」
    idx = {c["key"]: i for i, c in enumerate(D.INV_TABLE_COLUMNS)}
    assert cells[idx["price_excl"]] == "" and cells[idx["price_incl"]] == ""   # 单价列留空
    assert cells[idx["amount"]] == "340.00"


# ------------------------------------------------------------ 001-08 空态


@acc(CASE, "001-08")
def test_筛选为空必须有空态提示行():
    html = _page(period="2026-08", pj=["不存在的仓库"])
    assert "没有库存单据明细" in html
    assert f'colspan="{len(D.INV_TABLE_COLUMNS)}"' in html, "空态行跨列数由表头派生"


# ------------------------------------------------------------ 001-09 / 010 调整单


@acc(CASE, "001-09")
def test_调整单只改调整后金额原始值不被覆盖():
    s = _sess()
    detail = next(d for d in s.by_model[InvDetail] if d.id == 1)
    before = detail.amount

    save_adjustment(s, row_id=1, new_amount="80.00", remark="对账差异", operator="科室用户")
    assert detail.amount == before, "⛔ 原始值（i8 源数据）不得被调整单覆盖"
    row = next(r for r in load_rows(s) if r["id"] == 1)
    assert row["amount"] == before and row["adj_amount"] == Decimal("80.00")
    assert row["adj_remark"] == "对账差异" and row["adj_operator"] == "科室用户"

    # 纯函数侧同款：叠加调整单**返回新行**，源行一字不动
    src = {"id": 9, "amount": Decimal("100.00")}
    merged = D.with_adjustment(src, D.make_adjustment(src, "0", "修正为 0", operator="科室用户"))
    assert src["amount"] == Decimal("100.00") and "adj_amount" not in src
    assert merged["adj_amount"] == "0"


@acc(CASE, "001-10")
def test_调整后金额负值被拦零合法():
    assert D.adjustment_problem("-1", "理由") is not None      # 负值 ⇒ 拦
    assert D.adjustment_problem("0", "修正为 0") is None       # 0 ⇒ 合法
    assert D.adjustment_problem("100", "") is not None         # 备注必填
    assert D.adjustment_problem("abc", "理由") is not None     # 非数字 ⇒ 拦（不静默取 0）
    assert D.adjustment_problem("100.005", "理由") is None     # 走统一金额出口（2 位小数）


# ------------------------------------------------------------ 001-11 抓取弹窗


@acc(CASE, "001-11")
def test_抓取弹窗默认月份等于本页当前所选核算年月():
    html = _page(period="2026-07")
    m = re.search(r'id="fetchMonth"[^>]*value="([^"]*)"', html)
    assert m and m.group(1) == "2026-07"
    assert "强踢" in html, "抓取前必须告知会登录 i8 强踢在线用户（D9）"
    # 当前所选不是单月 ⇒ 回落到本表默认年月（抓取只允许单月，§9.2）
    assert D.fetch_dialog_default("2026-01~2026-06") == default_period("inventory")


# ------------------------------------------------------------ 001-12 两种导出


@acc(CASE, "001-12")
def test_两种导出并存且透视提示与模板形态一致():
    html = _page(period="2026-08")
    assert 'data-act="exp"' in html and 'data-act="expPivot"' in html, "两种导出必须并存"
    kinds = {k["id"]: k for k in D.export_kinds()}
    assert set(kinds) == {D.EXPORT_PLAIN, D.EXPORT_PIVOT}
    # 后者提示必须逐项写明工作簿形态（主人 = demo/模板/模板清单.md §二 第 10–12 行）
    hint = kinds[D.EXPORT_PIVOT]["hint"]
    for sheet in D.PIVOT_SHEETS:
        assert sheet in hint, f"透视导出的提示缺工作表：{sheet}"
    assert "路径②" in hint and "不受影响" in hint, "必须写明它是独立通道、主表那份不受影响"


# ------------------------------------------------------------ 001-13 硬边界


@acc(CASE, "001-13")
def test_不新增删除入口且不建是否作废字段():
    keys = tuple(c["key"] for c in D.INV_TABLE_COLUMNS)
    assert D.boundary_violations(column_keys=keys, action_ids=("adjDlg", "exp", "expPivot")) == []
    assert D.boundary_violations(column_keys=keys, action_ids=("delete",)) != []
    assert D.boundary_violations(column_keys=("amount", "void_flag"), action_ids=()) == []  # 未登记的列不炸
    assert D.boundary_violations(column_keys=("是否作废",), action_ids=()) != []

    html = _page(period="2026-08")
    assert "是否作废" not in html
    for act in D.FORBIDDEN_ACTIONS:
        assert f'data-act="{act}"' not in html, f"本页不得出现删除入口：{act}"
