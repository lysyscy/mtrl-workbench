"""付款通知书**列表页**（`/m03/notices`）的工程自检（离线 · 不连库）。

⚠️ `@acc()` **显式不绑定判据点**（同 `test_notice_list.py`：MOD-03 能力 1 在基线里无判据点）。
守的是：**五段骨架装配正确** · **剔除行默认隐藏** · **「分类=剔除」视图不受审批/付款状态约束且带分档** · **API 不吐 HTML**。

⚠️ 2026-09-19（`TAIL-27` · `§19` 批 4 **小轮①**）：本文件里的**页形态**断言已在
`tests/test_wired_m03_list.py` 立了**壳侧**对应件（旧页删除授权 `D18`，形态改指新壳）。
⇒ 删页那一轮本文件里对应的页形态观测随之作废；⛔ 实质（口径 / 取数 / 纯函数）不删，
只是要从 `notice_page.py`（**会被删**）归位到存活件（`list_view.py` 等）—— 见批 4 施工图。
"""

from __future__ import annotations

from decimal import Decimal

from app.mod01_projects.models import Project
from app.mod03_notice.list_view import CATEGORY_EXCLUDE, NoticeFilters
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_page import build_page_data, columns, render_notice_page
from tests.acc_plugin import acc
from tests.m04_helpers import FakeSession


def _notice(nid: int, **kw) -> PaymentNotice:
    vals = dict(
        id=nid, ph_id=f"P{nid}", bill_no=f"B{nid}", bill_type="material",
        doc_date="2026-09-05", category="material", biz_type="付其他供应商款",
        payee="某供应商", input_by="王潜森", amount_approved=Decimal("10000.00"),
        stat_settle=Decimal("10000.00"),
        stat_paid=Decimal("10000.00"), approve_status="已批",
        excluded=False, exclude_source="", i8_revoked=False, ownership_id=11,
        project_name="甲项目", fields={"BillName": "材料款结算单"},
    )
    vals.update(kw)
    return PaymentNotice(**vals)


def _data(notices, flows=None, *, sort_col: str = "", sort_dir: int = 0, **filters):
    """组装一页（`sort_col`/`sort_dir` **不进筛选器** —— 它们是排序参数）。"""
    session = FakeSession({PaymentNotice: list(notices), Project: []})
    f = NoticeFilters(period="2026-09", **filters)
    flows_map = flows or {}
    return build_page_data(
        session, filters=f, sort_col=sort_col, sort_dir=sort_dir,
        flows_of=lambda nid: flows_map.get(nid, []),
    )


# ---------------------------------------------------------------- 骨架与列


@acc()
def test_页面五段骨架齐备且18列():
    html = render_notice_page(_data([_notice(1)]))
    # 五段：口径说明 → 指标区（本页空）→ 筛选栏 → 数据区 → 空态
    for seg in ("tip", "kpis", "filter", "data"):
        assert f'data-seg="{seg}"' in html, seg
    assert html.count("data-seg=") >= 4
    assert 'class="view"' in html and 'data-view="m03-notices"' in html
    # 列数 = 18（勾选 + 16 数据列 + 操作）
    assert len(columns()) == 18
    # 金额是千分位 2 位（列表上零值显示 0.00，与打印件的"零值留空"故意不同）
    assert "10,000.00" in html
    # 勾选框只在页面上（API 里没有）
    assert '<input type="checkbox"' in html


@acc()
def test_年月输入框用统一控件取值语法():
    html = render_notice_page(_data([_notice(1)]))
    assert 'name="period"' in html and 'value="2026-09"' in html      # YYYY-MM 形态
    assert "闭区间" in html                                            # 单据日期区间是只读显示


# ---------------------------------------------------------------- 剔除行默认隐藏


@acc()
def test_默认视图隐藏剔除与撤单行且计数分档():
    notices = [
        _notice(1),
        _notice(2, excluded=True, exclude_source="rule"),
        _notice(3, excluded=True, exclude_source="manual"),
        _notice(4, i8_revoked=True),
    ]
    data = _data(notices)
    assert [r["notice_id"] for r in data["rows"]] == [1]              # 只显示有效行
    c = data["counters"]
    assert (c.effective, c.excluded, c.revoked) == (1, 2, 1)
    assert c.excluded_by == {"人工": 1, "规则": 1}
    html = render_notice_page(data)
    assert "有效 1 条" in html and "i8 已撤单 1 条" in html            # 右侧 pill


# ---------------------------------------------------------------- 「分类 = 剔除」专用视图


@acc()
def test_剔除视图不受审批付款约束且带分档标签():
    notices = [
        _notice(1, excluded=True, exclude_source="manual", approve_status="未批"),
        _notice(2, excluded=True, exclude_source="rule", approve_status="已批"),
        _notice(3, i8_revoked=True),
        _notice(4),                                                   # 有效行不进来
    ]
    data = _data(
        notices, category=CATEGORY_EXCLUDE,
        approve_status="已批", pay_status="paid",                     # 这两个**应被忽略**
    )
    assert [r["notice_id"] for r in data["rows"]] == [1, 2, 3]
    html = render_notice_page(data)
    # **按来源分档**（口径：不混作一谈）
    for tag in ("人工批量剔除", "规则命中", "i8 已撤单"):
        assert tag in html, tag


# ---------------------------------------------------------------- 排序与空态


@acc()
def test_金额列按数值排序而不是按字符串():
    notices = [_notice(1, amount_approved=Decimal("900.00")), _notice(2, amount_approved=Decimal("10000.00"))]
    from app.mod03_notice.page import SORT_ASC

    data = _data(notices, sort_col="amount_approved_text", sort_dir=SORT_ASC)
    # 按字符串排会是 "10,000.00" < "900.00"；**按数值**才是 900 在前
    assert [r["notice_id"] for r in data["rows"]] == [1, 2]


@acc()
def test_空数据显示空态提示行():
    data = _data([])
    html = render_notice_page(data)
    assert "当前筛选没有付款通知书" in html
    assert "剔除" in html                                             # 提示里给出"去哪儿找剔除了的行"


# ---------------------------------------------------------------- API 不吐 HTML


@acc()
def test_默认年月是当月而不是上月():
    """§9.2：付款域类表默认 = **当月**。

    ⚠️ 这条是**回归断言** —— 此前 `build_page_data` 把"统一时间控件的调用点标识"（`nt`）
       当成 `default_period()` 的口径键传进去，于是落到"材料报表类 = 上月"分支 ⇒ 打开页面看到上月。
    """
    from app.core.period import default_period

    from app.mod03_notice.notice_page import PERIOD_DEFAULT_KEY

    assert default_period(PERIOD_DEFAULT_KEY) == default_period("notice")
    session = FakeSession({PaymentNotice: [], Project: []})
    data = build_page_data(session, flows_of=lambda nid: [])
    assert data["filters"].period == default_period("notice") != default_period("process")


@acc()
def test_API_的_items_不含HTML():
    """`/api/m03/notice-list` 返回**纯数据** —— 勾选框是页面渲染时才注入的。"""
    data = _data([_notice(1)])
    item = {k: v for k, v in data["rows"][0].items() if k != "_row"}
    assert "pick" not in item
    assert not any("<input" in str(v) for v in item.values())
    assert item["category_label"] == "辅材"                            # 分类是中文标签


# ---------------------------------------------------------------- 表内合计行（001-09）

CASE_LIST = "ACC-PAY-LIST-001"


@acc(CASE_LIST, "001-09")
def test_表内合计行只算非剔除行且全剔除时不给():
    """`ACC-PAY-LIST-001/001-09`（2026-09-17 **新增**）：表内**合计行** —— 用户口径「**求和一律落在表内**」。

    ⚠️ 这是 `m03` 列表页补的**结构判据**：该用例原有 8 点**全是数据口径**、无一条讲页面结构
       ⇒ 实测（`tools/ui_parity.py` 拿原型源码比对）发现这一页**连合计行都没有**，而
       `m04`/`m05`/`m08` 都传了 `summary=` —— 属"同一口径只做了一半"。
    """
    import re

    from app.mod03_notice.notice_page import summary_row

    # ① 一行正常 + 一行剔除（剔除行金额很大）⇒ **剔除行不得计入**
    d = _data([
        _notice(1, amount_approved=Decimal("10000.00")),
        _notice(2, amount_approved=Decimal("999999.00"), excluded=True, exclude_source="manual"),
    ])
    html = render_notice_page(d)
    assert '<tr class="sum sumrow" data-pin="1">' in html, "合计行须在 tbody 内、钉在表尾（不参与排序）"
    row = summary_row(d)
    assert row[columns()[0]["key"]] == "合计", "首格写「合计」（与 m08 同款）"
    assert row["amount_approved_text"] == "10,000.00", \
        f"剔除行不得计入合计，实得 {row['amount_approved_text']}"
    # ② 5 个金额列逐列有合计（与原型 `sumRowOf` 的下标 10…14 一一对应）
    for key in ("amount_approved_text", "pay_amount_text", "amount_paid_text",
                "stat_settle_text", "stat_paid_text"):
        assert row[key], key
    # ③ 随筛选变动（只留一行 ⇒ 合计就是该行）
    d1 = _data([_notice(1, amount_approved=Decimal("10000.00"))])
    assert summary_row(d1)["amount_approved_text"] == "10,000.00"
    # ④ 切「分类 = 剔除」⇒ 该视图**全为剔除行** ⇒ **不给合计行**（不给一排 0，免得看着像坏了）
    d2 = _data([_notice(3, excluded=True, exclude_source="manual")], category=CATEGORY_EXCLUDE)
    assert summary_row(d2) == {}, "全剔除视图不得给合计行"
    assert not re.search(r'<tr class="sum sumrow"', render_notice_page(d2))


# ---------------------------------------------------------------- 项目选择器走共用件（001-07 加强）


@acc(CASE_LIST, "001-07")
def test_项目选择器走共用件且不得套两层label():
    """`001-07` **加强**（2026-09-17）：项目选择器 = **全站共用件**（原型 `projPanel` 的等价物）。

    依据：设计规则 **§8.2 复用点**（「项目选择器」只有一个出口）＋ 用户 2026-09-17 裁定
    「**结构 / 布局 / 交互必须照原型**」—— 实测（`tools/ui_parity.py`）实现里 `pjwrap` **恒为 0**：
    `m03` 用 `<select multiple>`、`m06`/`m07`/`m09` 各写一份 `.pjsel` ⇒ 7 页七个样。
    """
    from app.mod03_notice.proj_panel import proj_panel_html

    # ① 页面结构：走共用件（原型类名）、且**不得套两层 `.fi`**（`_render_filter_bar` 的 `raw` 口子）
    html = render_notice_page(_data([_notice(1)]))
    assert 'class="fi pjwrap"' in html, "项目选择器须用共用件（原型类名 .fi.pjwrap）"
    assert html.count("<label>项目（可多选）</label>") == 1, "label 只出现一次（套两层就重复了）"
    assert 'data-seg="filter"' in html
    # ② 纯函数层：多选 / 单选 / 选中态 / 空候选（**钉逻辑本身**，不依赖页面数据）
    opts = [{"key": "甲仓", "label": "甲项目"}, {"key": "乙仓", "label": "乙项目"}]
    h = proj_panel_html(opts, selected=["甲仓"], form="f-m03")
    assert h.count('type="checkbox"') == 2 and h.count('form="f-m03"') == 2
    assert 'value="甲仓" checked' in h and 'value="乙仓" checked' not in h
    assert "已选 1 个" in h
    h1 = proj_panel_html(opts, multiple=False)
    assert 'type="radio"' in h1 and "全部项目" in h1, "空选中态显示「全部项目」（原型同款）"
    assert "为空" in proj_panel_html([]), "候选为空要给提示，不假装有数据"
