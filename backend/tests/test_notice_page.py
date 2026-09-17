"""付款通知书**列表页**（`/m03/notices`）的工程自检（离线 · 不连库）。

⚠️ `@acc()` **显式不绑定判据点**（同 `test_notice_list.py`：MOD-03 能力 1 在基线里无判据点）。
守的是：**五段骨架装配正确** · **剔除行默认隐藏** · **「分类=剔除」视图不受审批/付款状态约束且带分档** · **API 不吐 HTML**。
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
