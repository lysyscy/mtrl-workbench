"""`MOD-06` 过程资料**导出**的验收断言（离线 · 不连库）。

对应判据 `ACC-RPT-EXP-001`（4 点 · `PRD/验收/验收基线.json`；口径主人 =《说明书》§7.1）：
- `001-01` 导出 =「卡头展开区 ＋ **多选**项目」形态；**每项目一份文件**，**≥2 个项目打成 zip**
- `001-02` 展开区**默认选中本页当前项目**（且不改动页面那个**单选**项目）
- `001-03` 展开区渲染在**滚动容器（`.tw`）之外**、**全页恰好一处**
- `001-04` **取数跟随当前所显示的那张表**（切表后提示逐一对上；文件名同源）

⚠️ 本用例只钉**形态与清单**：真实文件写出归切片 6 的 `ACC-X-EXP-001`（与台账 `TAIL-04` 同一条）。
"""

from __future__ import annotations

import re

from app.core.timing import today_cn, ym_of
from app.mod06_proc import domain as D
from app.mod06_proc.service import build_page_data, parse_state
from app.mod06_proc.view import render_export_preview, render_proc_page
from tests.acc_plugin import acc
from tests.m06_helpers import OTHER_WAREHOUSE, WAREHOUSE, FakeSession, dataset

CASE = "ACC-RPT-EXP-001"
YM = "2026-09"                          # 纯函数用（不受"今天"影响）
YM_NOW = ym_of(today_cn())              # 页面级：文件名含**当前年月**（§7.1）


def _data(**params) -> dict:
    return build_page_data(FakeSession(dataset()), parse_state(params))


def _page(**params) -> str:
    return render_proc_page(_data(**params))


def _exp_tab(html: str) -> str:
    """取「导出取数 = 当前所显示的 <b>…</b>」那一格（**按格取值**，不用整页 `in`）。"""
    m = re.search(r'data-exp-tab="1">([^<]*)</b>', html)
    assert m, "页面上没有导出取数提示（`data-exp-tab`）"
    return m.group(1).strip()


def _boxes(html: str) -> list[tuple[str, bool]]:
    return [(v, bool(ck)) for v, ck in re.findall(r'name="exppj" value="([^"]*)"( checked)?>', html)]


def _strip(html: str) -> str:
    """展开区那一段（用于「多选 / 单选」这类**区域内**断言 —— 整页 `in` 会被别处喂饱）。"""
    i = html.index('data-seg="exp-strip"')
    j = html.index('<div class="tw"')
    assert i < j, "展开区落在滚动容器里 ⇒ 浮层面板会被裁（001-03）"
    return html[i:j]


def _cands() -> list[str]:
    cands = _data()["export"]["projects"]
    assert len(cands) >= 2, f"候选不足 2 个（实得 {cands}）⇒ 本件多条断言失去区分力"
    return cands


# ------------------------------------------------------------ 001-01 展开区 + 多选 + 每项目一份 + zip

@acc(CASE, "001-01")
def test_展开区是多选项目面板且每项目一份多项目打zip():
    cands = _cands()
    html = _page()
    strip = _strip(html)
    boxes = _boxes(strip)
    assert len(boxes) == len(cands), f"展开区候选项数 {len(boxes)} ≠ 候选项目数 {len(cands)}"
    assert [v for v, _ in boxes] == cands
    # **多选**的可观测形态：checkbox ＋ 全选 / 清空；且**区域内不得出现 radio**（那是单选面板）
    assert 'type="checkbox"' in strip
    assert 'name="expset" value="all"' in strip and 'name="expset" value="none"' in strip
    assert 'type="radio"' not in strip, "展开区混进了单选 radio ⇒ 不是多选面板"

    # 每项目一份文件：份数 = 所选项目数、文件名互不相同（001-01）
    one = D.export_manifest([cands[0]], tab=D.TAB_ADJUSTED, ym=YM)
    assert one["count"] == 1 and one["zip"] is False and one["zip_name"] == ""
    assert len(one["files"]) == 1 and one["files"][0]["project"] == cands[0]

    two = D.export_manifest(cands[:2], tab=D.TAB_ADJUSTED, ym=YM)
    assert two["count"] == 2 and two["zip"] is True
    assert two["zip_name"] == f"{D.EXPORT_DOMAIN}_{YM}.zip"
    assert [f["project"] for f in two["files"]] == cands[:2]
    assert len({f["name"] for f in two["files"]}) == 2, "两份文件名撞了 ⇒ 不是「每项目一份」"

    # 清单预览：1 个文件 / N 个项目打 zip ＋ 清单行数 = 所选项目数
    p1 = render_export_preview(_data(pj=cands[0], exppj=[cands[0]], expopen="1"))
    assert "1 个文件" in p1 and "17 列模板" in p1
    assert f'class="fc">{D.export_manifest([cands[0]], tab=D.TAB_ADJUSTED, ym=YM_NOW)["files"][0]["name"]}<' in p1

    p2 = render_export_preview(_data(pj=cands[0], exppj=cands[:2], expopen="1"))
    assert p2.count('<tr><td class="fc">') == 2, "清单行数 ≠ 所选项目数"
    m = re.search(r'class="fc">([^<]*\.zip)</span>', p2)
    assert m and m.group(1) == f"{D.EXPORT_DOMAIN}_{YM_NOW}.zip", "多项目没打成 zip / zip 名不对"
    for f in D.export_manifest(cands[:2], tab=D.TAB_ADJUSTED, ym=YM_NOW)["files"]:
        assert f["name"] in p2, f"清单里少了 {f['name']}"
    assert "每项目一份" in p2


@acc(CASE, "001-01")
def test_未选项目时导出按钮禁用而不是静默导当前项目():
    """清空后：**导出按钮禁用**（不静默退回当前项目 —— 那是一次用户没要求的导出）。"""
    cands = _cands()
    html = _page(pj=cands[0], expopen="1", expset="none")
    strip = _strip(html)
    assert [v for v, ck in _boxes(strip) if ck] == [], "点了清空却还有勾选项"
    assert "已选 0 个项目" in strip
    m = re.search(r'formaction="/m06/export"([^>]*)>导出</button>', strip)
    assert m and "disabled" in m.group(1), "0 个项目时导出按钮没有禁用"

    empty = render_export_preview(_data(pj=cands[0], expopen="1", expset="none"))
    assert "请先选择要导出的项目" in empty


# ------------------------------------------------------------ 001-02 默认选中本页当前项目

@acc(CASE, "001-02")
def test_展开区默认选中本页当前项目():
    cands = _cands()
    # 纯函数出口：没动过 ⇒ 默认 = 当前项目（空当前项目 ⇒ 空）
    assert D.export_selection(cands[0], [], touched=False) == [cands[0]]
    assert D.export_selection("", [], touched=False) == []
    # ⚠️ 边界：**动过但清空了**必须保持空 —— 否则「清空」会被静默撤销
    assert D.export_selection(cands[0], [], touched=True) == []
    assert D.export_selection(cands[0], [cands[1], cands[1], " "], touched=True) == [cands[1]]

    # 页面级：刻意取**非默认**的那个项目（默认 = 候选第一），判据才有区分力
    other = WAREHOUSE if cands[0] != WAREHOUSE else OTHER_WAREHOUSE
    assert other in cands and other != cands[0]
    html = _page(pj=other)
    assert [v for v, ck in _boxes(html) if ck] == [other], "默认选中 ≠ 本页当前项目"
    # 且**不改动**页面那个单选项目（两个面板是两件事）
    assert re.search(r'name="pj" value="' + re.escape(other) + r'"[^>]*checked', html)


@acc(CASE, "001-02")
def test_展开区的选择改动不影响页面单选项目():
    cands = _cands()
    html = _page(pj=cands[0], expopen="1", exppj=[cands[1]])
    assert [v for v, ck in _boxes(html) if ck] == [cands[1]]
    # 页面那个单选项目仍是 cands[0]（导出面板的勾选不回流到筛选）
    assert re.search(r'name="pj" value="' + re.escape(cands[0]) + r'"[^>]*checked', html)
    assert re.search(r'name="pj" value="' + re.escape(cands[1]) + r'"[^>]*checked', html) is None


# ------------------------------------------------------------ 001-03 在 .tw 之外 · 全页恰好一处

@acc(CASE, "001-03")
def test_展开区在滚动容器之外且三张表下都恰好一处():
    for tab in (D.TAB_RAW, D.TAB_ADJUSTED, D.TAB_DIFF):
        html = _page(tab=str(tab))
        assert html.count('data-seg="exp-strip"') == 1, f"表签 {tab} 下展开区不是恰好一处"
        assert html.index('data-seg="exp-strip"') < html.index('<div class="tw"'), "展开区落在 `.tw` 之后"
        # 展开区不得落进数据区（滚动容器内）—— 否则浮层面板会被裁
        assert 'name="exppj"' not in html[html.index('<div class="tw"'):]


# ------------------------------------------------------------ 001-04 取数跟随当前所显示的表

@acc(CASE, "001-04")
def test_导出取数跟随当前所显示的那张表():
    cands = _cands()
    got = []
    for tab in (D.TAB_RAW, D.TAB_ADJUSTED, D.TAB_DIFF):
        html = _page(tab=str(tab))
        cur = _exp_tab(html)
        want = next(label for num, label in D.TABS if num == tab)
        assert cur == want == D.tab_name(tab), f"表签 {tab} 的导出提示 = {cur!r}，应为 {want!r}"
        got.append(cur)
    assert len(set(got)) == len(got), "三张表的提示必须互不相同，否则这条判据没有区分力"

    # 清单预览页同源：文件名里就是当前表名（导出取数与提示同一个出口）
    for tab, want in ((D.TAB_RAW, D.TABS[0][1]), (D.TAB_ADJUSTED, D.TABS[1][1]),
                      (D.TAB_DIFF, D.TABS[2][1])):
        prev = render_export_preview(_data(tab=str(tab), exppj=[cands[0]], expopen="1"))
        assert _exp_tab(prev) == want
        name = D.export_manifest([cands[0]], tab=tab, ym=YM)["files"][0]["name"]
        assert want in name and name.endswith(".xlsx")
        assert D.EXPORT_DOMAIN in name and cands[0] in name and YM in name
