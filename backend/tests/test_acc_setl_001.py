"""`MOD-07` 收发结存月报 —— 离线自检（**不连库**）。

对应判据 `ACC-SETL-001`（9 点，`PRD/验收/验收基线.json`）：
- `001-01` 表体**每仓一行**；**行数合计 = 各仓行数之和**（独立复算）
- `001-02` 默认核算年月 = **北京时间上月**（§9.2）
- `001-03` 切月后表数据跟着换（行数合计 = 独立复算），且**各月数据互不相同**
- `001-04` 「重置」回到默认上月；且**各页各自取数、不产生跨页状态**
- `001-05` 空月给**空态提示行**，跨列数 = 表头列数（**独立数 `<th>`**，不借实现自证）
- `001-06` 抓取入口打开「按月抓取」弹窗，**默认月份 = 本页当前所选核算年月**（可改）
- `001-07` 「行 / 仓 / 文件」三项计数**随数据实时算**（不得写死）
- `001-08` 产出物 = **分仓库工作簿 ＋ 总表**，分仓库工作簿数量**随仓数实时算**
- `001-09` 对平判据 = **按 2 位小数归一后判等（容差 0）**，对平与否**动态判定**
"""

from __future__ import annotations

import pathlib
import tempfile
import zipfile
from datetime import date, timedelta
from decimal import Decimal

from app.mod07_setl import domain as D
from app.mod07_setl.models import SetlDetail
from app.mod07_setl.service import build_page_data, parse_state
from app.report_export import service as _EX
from app.report_export import setl_export as _SE
from tests.acc_plugin import acc
from tests.m07_helpers import (
    EMPTY_MONTH,
    EXPECT,
    FakeSession,
    dataset,
    indep_amount_total,
    indep_row_total,
    indep_warehouses,
)

CASE = "ACC-SETL-001"
MONTHS = ("2026-08", "2026-07", "2026-06")


# ============================================================ 工具（都**不借实现自证**）
#
# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 2**）：原先这里有一整套**页面观测辅助件** ——
#    `_page()`（取旧页 HTML）· `_table`/`_TABLE_RE`/`_trs`/`_rows`/`_data_rows`/`_thead_count`/
#    `_empty_row`/`_sum_row`/`_dialog`/`_num`（从旧页 HTML 里抠表体 / 合计行 / 空态行 / 弹窗 / 数字）。
#    旧页整体删除（授权 `D18`）后它们**零调用**（逐个数过 ✓）⇒ 一并移除；本文件此后**只读数据出口**
#    （`_data()`），形态 claim 全部在 `tests/test_wired_m07.py` 里立 ✓（表体每仓一行 / 合计行由共用出口出 /
#    空态 colspan 由表头派生 / 抓取弹窗 / 产出物清单 / 对平显示与合计校验 …）。⛔ 判据一条没删。


def _data(*, period: str | None = None, params: dict | None = None) -> dict:
    """本表当页**数据**（旧页渲染前的那份 `build_page_data` 出口；⛔ 不碰任何页面形态）。"""
    p = dict(params or {})
    if period is not None:
        p["period"] = period
    return build_page_data(FakeSession(dataset()), parse_state(p))


# ============================================================ 判据点


@acc(CASE, "001-01")
def test_表体每仓一行且行数合计等于各仓行数之和():
    data = _data(period="2026-08")
    rows, summary = data["rows"], data["summary"]
    names = [r["warehouse"] for r in rows]

    assert names == indep_warehouses("2026-08"), "表体不是「每仓一行」或行序不稳"
    assert len(names) == len(set(names)), "同一仓库出现了多行"

    # 各仓行数 = 手写期望表；**行数合计 = 各仓行数之和**（独立复算）
    assert [r["rows"] for r in rows] == [EXPECT["2026-08"][w]["rows"] for w in names]
    assert summary["rows"] == indep_row_total("2026-08")
    assert summary["rows"] == sum(r["rows"] for r in rows)

    # 四个金额列各有合计，且与独立复算一致（列序 = 表头顺序）
    assert [c["key"] for c in D.SETL_COLUMNS[2:6]] == list(D.AMOUNT_KEYS)
    for key in D.AMOUNT_KEYS:
        assert summary[key] == indep_amount_total("2026-08", key), f"{key} 合计不对"
    # ⚠️ 2026-09-19（`§19` 批 2）：原先这些是从**旧页**表体/合计行的 `<td>` 里抠出来的；
    # 旧页删除（授权 `D18`）后**形态**搬到壳 —— `test_wired_m07.py::test_壳里表体每仓一行且合计行
    # 由共用出口出`（`sumRowOf(WH_THEAD, rows, …)` ⇒ 行数与四个金额列的合计都按行派生 ✓）。
    # 这里改走**数据出口**（页面只是印它），口径与独立复算一字未动。


@acc(CASE, "001-02")
def test_默认核算年月为北京时间上月():
    first = date.today().replace(day=1)
    want = (first - timedelta(days=1)).replace(day=1).strftime("%Y-%m")     # 独立推算

    assert D.default_month() == want
    assert parse_state({})["period"] == want
    # ⚠️ 2026-09-19（`§19` 批 2）：原先还查旧页 `name="period"` 输入框里是不是这个月；旧页删除
    # （授权 `D18`）后形态搬到壳 —— `test_wired_m07.py::test_壳里核算年月默认上月且可切` ✓。
    # 上面两条**取数口径**（默认月怎么算、不给参数落哪儿）是实质，留着。


@acc(CASE, "001-03")
def test_切月后表数据跟着换且各月互不相同():
    totals: dict[str, int] = {}
    for ym in MONTHS:
        data = _data(period=ym)
        rows = data["rows"]
        assert [r["warehouse"] for r in rows] == indep_warehouses(ym), f"{ym} 的仓集合不对"
        got = data["summary"]["rows"]
        assert got == indep_row_total(ym), f"{ym} 行数合计 {got} ≠ 独立复算 {indep_row_total(ym)}"
        totals[ym] = got
    # 各月数据互不相同 ⇒ 这条断言有区分力（否则"切月"可以什么都不做也过）
    assert len(set(totals.values())) == len(totals), f"演示数据三个月重复：{totals}"
    # ⚠️ 2026-09-19（`§19` 批 2）：原先这两条借**旧页**的表体行与合计行观测；旧页删除（授权 `D18`）后
    # 形态搬到壳（见上面 001-01 的说明 ＋ `test_wired_m07.py` 的「切月重取数」），这里改走数据出口。


@acc(CASE, "001-04")
def test_重置回到默认上月且不产生跨页状态():
    assert parse_state({})["period"] == D.default_month()
    # ⚠️ 2026-09-19（`TAIL-27` · `§19` 批 2）：原先这里看**旧页**的三件事 —— 「重置」链接
    # （`href="/m07"`）· 「本页不得渲染 MOD-08 的『项目』筛选」· 「不得带 `invWh` 这类跨页状态」；
    # 旧页删除（授权 `D18`）后形态搬到壳 —— `test_wired_m07.py::test_壳里重置回默认月且不串页`
    # （`whReset` ＋ **本页切片**里不含别模块的筛选状态 ✓）。上面那条**取数口径**是实质，留着。


@acc(CASE, "001-05")
def test_空月的空态提示行跨列数等于表头列数():
    empty = _data(period=EMPTY_MONTH)
    assert empty["rows"] == [], "空月不该有数据行"
    # ⚠️ 2026-09-19（`§19` 批 2）：原先在这里从**旧页**抠"空态提示行 / 跨列数 = 表头列数 /
    # 提示里点名了那个月"；旧页删除（授权 `D18`）后形态搬到壳 ——
    # `test_wired_m07.py::test_壳里空态跨列数由表头派生`（`colspan="${thCount(WH_THEAD)}"` ＋
    # 提示里带 `<b>${tmLabel(fWhYm)}</b>` ✓）。「空月不该有合计行」由 `empty["rows"] == []` 蕴含 ✓。


@acc(CASE, "001-06")
def test_抓取弹窗默认月份等于当前所选且可改():
    # ⚠️ 2026-09-19（`§19` 批 2）：原先这一整段查**旧页**的抓取弹窗（月份输入框 = 当前所选、
    # 可改、表单 action、二次确认 token、写没写「强踢」、入口能不能打开弹窗）；旧页删除（授权 `D18`）后
    # 形态搬到壳 —— `test_wired_m07.py::test_壳里抓取弹窗默认取本页年月且讲清强踢`（`fetchWh` ✓）。
    # 下面两条是**回落口径**的实质（抓取只允许单月 §9.2）：
    assert D.fetch_dialog_default("2026-01~2026-06") == D.default_month()
    assert D.fetch_dialog_default("") == D.default_month()


@acc(CASE, "001-07")
def test_行仓文件三项计数随数据实时算():
    seen: list[tuple[int, int, int]] = []
    for ym in MONTHS:
        c = _data(period=ym)["counts"]
        nums = (c["warehouses"], c["rows"], c["files"])
        want = (len(indep_warehouses(ym)), indep_row_total(ym), len(indep_warehouses(ym)) + 1)
        assert nums == want, f"{ym} 的三项计数 {nums} ≠ {want}"
        assert nums[2] == nums[0] + 1, "文件数恒 = 仓数 ＋ 1（总表）"
        seen.append(nums)
    # 三项都跟着数据变 ⇒ 不是写死的数字
    assert len(set(seen)) == len(seen), f"三个月计数完全相同 ⇒ 疑似写死：{seen}"
    # ⚠️ 2026-09-19（`§19` 批 2）：原先这三项是从**旧页**那颗 `<span class="pill">` 里抠出来的；
    # 旧页删除（授权 `D18`）后本项的出口就是 `data["counts"]`（页面只是印它 ✓），
    # 壳侧对应断言见 `test_wired_m07.py::test_壳里文件数恒为仓数加一`（`zipSfjc` 的回执 ✓）。

    # 空月：0 仓 / 0 行 / **1 文件**（总表仍在）—— 计数不因空态变成 0 或空白
    empty = _data(period=EMPTY_MONTH)["counts"]
    assert (empty["warehouses"], empty["rows"], empty["files"]) == (0, 0, 1)


@acc(CASE, "001-08")
def test_产出物为分仓库工作簿加总表且份数随仓数实时算():
    counts: list[int] = []
    for ym in MONTHS:
        data = _data(period=ym)
        manifest = data["manifest"]
        wh = [m for m in manifest if m["kind"] == "warehouse"]
        total = [m for m in manifest if m["kind"] == "total"]

        assert len(wh) == len(indep_warehouses(ym)) == len(data["rows"]), "分仓库份数没跟着仓数走"
        assert [m["name"] for m in wh] == [f"{w}.xlsx" for w in indep_warehouses(ym)]
        assert len(total) == 1 and total[0]["name"].endswith(".xlsx"), "总表必须恰好 1 份"
        assert len(manifest) == len(wh) + 1
        counts.append(len(wh))

        # ⚠️ 2026-09-19（`§19` 批 2）：原先这里看**旧页** zip 弹窗渲染出来的清单（条数 = 份数）；
        # 旧页删除（授权 `D18`）后形态搬到壳 ——
        # `test_wired_m07.py::test_壳里产出物清单按仓数加总表且真导出`（壳的产出物清单逐项 ✓）。

    assert len(set(counts)) > 1, f"三个月份数完全相同 ⇒ 疑似写死：{counts}"
    # 空月：只剩总表 1 份
    assert len(_data(period=EMPTY_MONTH)["manifest"]) == 1

    # ⭐ `TAIL-04` 起：「产出物」不再只是一张清单 —— **清单必须与实际产出的 zip 成员一致**。
    #    ⚠️ 为什么补这一段：本判据点原文写的是「**产出物** = 分仓库工作簿 ＋ 1 个总表」，
    #       而在此之前它只查了 `manifest`（**清单自己说自己**）⇒ **导出根本没实现也照样绿**
    #       （实测：`TAIL-04` 落地前，导出按钮按下去拿不到任何文件，本条却一直是绿的）。
    #    做法：拿**同一份桩明细**真跑一次成品写出，再核对 zip 成员 == 清单。
    rows = dataset((MONTHS[0],))[SetlDetail]
    with tempfile.TemporaryDirectory(prefix="acc-setl-108-") as td:
        zip_path = _SE.build_zip(rows, pathlib.Path(td) / "out", _EX.period_label(MONTHS[0]))
        members = sorted(zipfile.ZipFile(zip_path).namelist())
    manifest = _data(period=MONTHS[0])["manifest"]
    assert members == sorted(m["name"] for m in manifest), (
        f"zip 成员与清单不一致：{members} vs {[m['name'] for m in manifest]}"
    )
    assert len(members) == len(indep_warehouses(MONTHS[0])) + 1


@acc(CASE, "001-09")
def test_对平判据按两位小数归一后判等且动态判定():
    # ① 归一后相等 ⇒ 对平（原始差额 0.004 不足半分）
    assert D.is_balanced({"begin": "0.004", "in": 0, "out": 0, "end": 0}) is True
    # ② 归一后不等 ⇒ 判不平，且差额报出来（0.005 → 0.01）
    assert D.is_balanced({"begin": "0.005", "in": 0, "out": 0, "end": 0}) is False
    assert D.check_text({"begin": "0.005", "in": 0, "out": 0, "end": 0}) == "差 0.01"
    # ③ **容差 0**：差一分也算不平（不是 0.005 那种松容差）
    off = {"begin": "1000.00", "in": "500.50", "out": "200.25", "end": "1300.26"}
    assert D.balance(off) == Decimal("-0.01")
    assert D.is_balanced(off) is False

    # ④⑤⑥ 的**形态**半边（页面按动态判定显示「已对平 / 差 X」、**合计行的校验格**是对
    #   **合计值本身**再判一次）：⚠️ 2026-09-19（`§19` 批 2）原先借**旧页**观测，旧页删除（`D18`）后
    #   形态搬到壳 —— `test_wired_m07.py::test_壳里对平显示与合计行校验`（`tagOf(balOf(w))` 逐行 ＋
    #   合计行的 `tagOf(totBal)` ✓）。下面改用**数据出口**把同一批事实再钉一遍（判据没丢）：
    #   本桩里 丙仓 +0.50 / 戊仓 -0.20 / **合计 +0.30**，三个数互不相同。
    row_bals = [D.balance(r) for r in _data(period="2026-07")["rows"]]
    assert Decimal("0.50") in row_bals and Decimal("-0.20") in row_bals, f"样本行差额变了：{row_bals}"
    tot_bal = D.balance(_data(period="2026-07")["summary"])
    assert tot_bal == Decimal("0.30"), f"合计行的校验不是对**合计值本身**判的：{tot_bal}"
    assert tot_bal not in row_bals, "合计校验格抄了某一行（应当独立判定）"

    # ⑥ 全部对平的月份 ⇒ `balance_ok` 为真（同一个口径，不再借页面）
    assert _data(period="2026-08")["balance_ok"] is True
    assert _data(period="2026-07")["balance_ok"] is False
