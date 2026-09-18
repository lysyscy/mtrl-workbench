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
import re
import tempfile
import zipfile
from datetime import date, timedelta
from decimal import Decimal

from app.mod02_i8.fetch_task import CONFIRM_TOKEN
from app.mod07_setl import domain as D
from app.mod07_setl.models import SetlDetail
from app.mod07_setl.service import build_page_data, parse_state
from app.mod07_setl.view import fetch_dialog_html, render_setl_page
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

_TABLE_RE = re.compile(
    r'<table class="dt" data-sort data-sort-key="m07:warehouses">(.*?)</table>', re.S
)


def _page(*, period: str | None = None, params: dict | None = None) -> str:
    p = dict(params or {})
    if period is not None:
        p["period"] = period
    return render_setl_page(build_page_data(FakeSession(dataset()), parse_state(p)))


def _data(*, period: str | None = None, params: dict | None = None) -> dict:
    p = dict(params or {})
    if period is not None:
        p["period"] = period
    return build_page_data(FakeSession(dataset()), parse_state(p))


def _table(html: str) -> str:
    m = _TABLE_RE.search(html)
    assert m, "没找到结存表（`data-sort-key=\"m07:warehouses\"`）"
    return m.group(1)


def _thead_count(html: str) -> int:
    """**独立数**表头 `<th>` 个数（不用实现里的列数）。"""
    return len(re.findall(r"<th\b", _table(html)))


def _trs(html: str) -> list[tuple[str, list[str]]]:
    """表体每一行 → `(<tr> 的属性串, 各格文字)`——属性串留着判「空态行 / 合计行」。"""
    body = re.search(r"<tbody>(.*?)</tbody>", _table(html), re.S).group(1)
    out: list[tuple[str, list[str]]] = []
    for attrs, inner in re.findall(r"<tr\b([^>]*)>(.*?)</tr>", body, re.S):
        out.append((
            attrs,
            [re.sub(r"<[^>]*>", "", c).strip()
             for c in re.findall(r"<td\b[^>]*>(.*?)</td>", inner, re.S)],
        ))
    return out


def _rows(html: str) -> list[list[str]]:
    return [cells for _attrs, cells in _trs(html)]


def _data_rows(html: str) -> list[list[str]]:
    """**数据行**：不含合计行、不含空态提示行。"""
    return [cells for attrs, cells in _trs(html)
            if "empty" not in attrs and cells and cells[0] != D.TOTAL_LABEL]


def _empty_row(html: str) -> str:
    """空态提示行**整行 HTML**（要读它的 `colspan` 与文字）。"""
    m = re.search(r"<tr[^>]*\bempty\b[^>]*>(.*?)</tr>", _table(html), re.S)
    assert m, "空月没有空态提示行（tbody 直接空白）"
    return m.group(1)


def _sum_row(html: str) -> list[str]:
    for cells in _rows(html):
        if cells and cells[0] == D.TOTAL_LABEL:
            return cells
    raise AssertionError("表尾没有「合计」行")


def _dialog(html: str, dlg_id: str) -> str:
    m = re.search(rf'<dialog[^>]*id="{dlg_id}"[^>]*>.*?</dialog>', html, re.S)
    assert m, f"没有 {dlg_id} 弹窗"
    return m.group(0)


def _num(text: str) -> Decimal:
    return Decimal(re.sub(r"[^\d.\-]", "", text) or "0")


# ============================================================ 判据点


@acc(CASE, "001-01")
def test_表体每仓一行且行数合计等于各仓行数之和():
    html = _page(period="2026-08")
    rows = _data_rows(html)
    names = [r[0] for r in rows]

    assert names == indep_warehouses("2026-08"), "表体不是「每仓一行」或行序不稳"
    assert len(names) == len(set(names)), "同一仓库出现了多行"

    # 各仓行数 = 手写期望表；**行数合计 = 各仓行数之和**（独立复算）
    assert [int(_num(r[1])) for r in rows] == [EXPECT["2026-08"][w]["rows"] for w in names]
    total = _sum_row(html)
    assert int(_num(total[1])) == indep_row_total("2026-08")
    assert int(_num(total[1])) == sum(int(_num(r[1])) for r in rows)

    # 四个金额列各有合计，且与独立复算一致（列序 = 表头顺序）
    assert [c["key"] for c in D.SETL_COLUMNS[2:6]] == list(D.AMOUNT_KEYS)
    for i, key in enumerate(D.AMOUNT_KEYS, start=2):
        assert _num(total[i]) == indep_amount_total("2026-08", key), f"{key} 合计不对"


@acc(CASE, "001-02")
def test_默认核算年月为北京时间上月():
    first = date.today().replace(day=1)
    want = (first - timedelta(days=1)).replace(day=1).strftime("%Y-%m")     # 独立推算

    assert D.default_month() == want
    assert parse_state({})["period"] == want
    # 不带参数打开本页 ⇒ 展示的就是这个月（输入框里就是它）
    html = _page()
    box = re.search(r'<input[^>]*name="period"[^>]*>', html)
    assert box and f'value="{want}"' in box.group(0)


@acc(CASE, "001-03")
def test_切月后表数据跟着换且各月互不相同():
    totals: dict[str, int] = {}
    for ym in MONTHS:
        html = _page(period=ym)
        rows = _data_rows(html)
        assert [r[0] for r in rows] == indep_warehouses(ym), f"{ym} 的仓集合不对"
        got = int(_num(_sum_row(html)[1]))
        assert got == indep_row_total(ym), f"{ym} 行数合计 {got} ≠ 独立复算 {indep_row_total(ym)}"
        totals[ym] = got
    # 各月数据互不相同 ⇒ 这条断言有区分力（否则"切月"可以什么都不做也过）
    assert len(set(totals.values())) == len(totals), f"演示数据三个月重复：{totals}"


@acc(CASE, "001-04")
def test_重置回到默认上月且不产生跨页状态():
    assert parse_state({})["period"] == D.default_month()
    # ⚠️ 2026-09-19（`TAIL-27` · `§19` 批 2）：原先这里看**旧页**的三件事 —— 「重置」链接
    # （`href="/m07"`）· 「本页不得渲染 MOD-08 的『项目』筛选」· 「不得带 `invWh` 这类跨页状态」；
    # 旧页删除（授权 `D18`）后形态搬到壳 —— `test_wired_m07.py::test_壳里重置回默认月且不串页`
    # （`whReset` ＋ **本页切片**里不含别模块的筛选状态 ✓）。上面那条**取数口径**是实质，留着。


@acc(CASE, "001-05")
def test_空月的空态提示行跨列数等于表头列数():
    html = _page(period=EMPTY_MONTH)
    assert _data_rows(html) == [], "空月不该有数据行"
    assert not any(r[0] == D.TOTAL_LABEL for r in _rows(html)), "空月不该有合计行"

    ths = _thead_count(html)                     # 独立数表头
    m = re.search(r'<td colspan="(\d+)"[^>]*>(.*?)</td>', _empty_row(html), re.S)
    assert m, "空态提示行没有跨列单元格"
    assert int(m.group(1)) == ths, f"空态跨列数 {m.group(1)} ≠ 表头列数 {ths}"
    text = re.sub(r"<[^>]*>", "", m.group(2)).strip()
    assert text, "空态行是空白的"
    assert EMPTY_MONTH in text, "空态提示没点名是哪个月"


@acc(CASE, "001-06")
def test_抓取弹窗默认月份等于当前所选且可改():
    html = _page(period="2026-07")
    dlg = _dialog(html, "fetchDlg")

    m = re.search(r'<input[^>]*id="fetchMonth"[^>]*>', dlg)
    assert m, "弹窗里没有月份输入框"
    box = m.group(0)
    assert 'value="2026-07"' in box, "弹窗默认月份 ≠ 页面当前所选核算年月"
    assert "readonly" not in box and "disabled" not in box, "默认月份必须是**可改**的"
    assert 'name="month"' in box
    assert 'method="post"' in dlg and 'action="/m07/fetch"' in dlg
    # 抓前必须二次确认，且**明写会强踢**（D9）
    assert f'value="{CONFIRM_TOKEN}"' in dlg
    assert "强踢" in dlg
    # 页面上的入口真的能打开它
    assert "getElementById('fetchDlg').showModal()" in html

    # 端点同源：换一个当前所选，弹窗默认月随之换
    assert 'value="2026-03"' in fetch_dialog_html(D.fetch_dialog_default("2026-03"))
    # 非单月 / 空 ⇒ 回落本表默认年月（抓取只允许单月，§9.2）
    assert D.fetch_dialog_default("2026-01~2026-06") == D.default_month()
    assert D.fetch_dialog_default("") == D.default_month()


@acc(CASE, "001-07")
def test_行仓文件三项计数随数据实时算():
    seen: list[tuple[int, int, int]] = []
    for ym in MONTHS:
        html = _page(period=ym)
        pill = re.search(r'<span class="pill">(.*?)</span>', html, re.S).group(1)
        nums = tuple(int(x) for x in re.findall(r"\d+", pill))
        want = (len(indep_warehouses(ym)), indep_row_total(ym), len(indep_warehouses(ym)) + 1)
        assert nums == want, f"{ym} 的三项计数 {nums} ≠ {want}"
        assert nums[2] == nums[0] + 1, "文件数恒 = 仓数 ＋ 1（总表）"
        seen.append(nums)
    # 三项都跟着数据变 ⇒ 不是写死的数字
    assert len(set(seen)) == len(seen), f"三个月计数完全相同 ⇒ 疑似写死：{seen}"

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

        # 页面上的 zip 弹窗渲染的就是这份清单（清单条数 = 份数）
        dlg = _dialog(_page(period=ym), "zipDlg")
        assert dlg.count("<td>分仓库工作簿</td>") == len(wh)
        assert f"共 <b>{len(manifest)}</b> 个文件" in dlg

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

    # ④ 页面上按**动态判定**显示：同一页里既有「已对平」也有「差 X」
    html = _page(period="2026-07")
    assert "已对平" in html and "差 0.50" in html

    # ⑤ 合计行的校验 = **对合计值本身**再判一次（不是抄某一行）——
    #    本桩里 丙仓 +0.50 / 戊仓 -0.20 / **合计 +0.30**，三个数互不相同
    total = _sum_row(html)
    assert total[6] == "差 0.30", f"合计行校验格 = {total[6]}（应是对合计值本身判定）"
    assert total[6] not in ("差 0.50", "差 -0.20")

    # ⑥ 全部对平的月份 ⇒ 合计也是「已对平」
    assert _sum_row(_page(period="2026-08"))[6] == D.BALANCE_OK
