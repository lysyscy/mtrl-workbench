"""`ACC-PAY-IA-001`（付款域页面划分与列表页骨架）4 个判据点的验收断言。

依据：《说明书》§4.1.2（范围定义）· §4.2 / §4.3（页面与筛选）
      · `demo/设计规则-提炼自付款通知书页.md`（R1 折叠 · R2 指标区 · R4 筛选栏 · R10 空态 · R13 排序）。
"""

from __future__ import annotations

from app.mod03_notice.page import (
    LIST_PAGE_SEGMENTS,
    PAY_DOMAIN_PAGES,
    SCOPE_EXCLUDED,
    SCOPE_INCLUDED,
    SORT_ASC,
    SORT_DESC,
    SORT_NONE,
    is_sortable,
    nav_violations,
    next_sort_direction,
    render_list_page,
    segment_sequence,
    sort_rows,
    tip_block_count,
)
from tests.acc_plugin import acc

TIPS = [
    "付款计划 = i8 付款通知书的「本月预算版」",
    "「项目」列填的是展示名或仓库名（不是全名）",
    "系统只提示、不拦截；强制通过必须写备注",
]
COLUMNS = [
    {"key": "year_month", "label": "单据年月", "sortable": True},
    {"key": "doc_no", "label": "单据号", "sortable": True},
    {"key": "planned_amount", "label": "本月预付款金额", "sortable": True},
    {"key": "audit_result", "label": "审查结果", "sortable": True},
    {"key": "op", "label": "操作", "sortable": False},
]
FILTERS = [
    {"key": "year_month", "label": "单据年月", "control": "acc-period"},
    {"key": "project_ids", "label": "项目（可多选）", "control": "proj-panel"},
    {"key": "audit_bucket", "label": "审查结果", "control": "select"},
]


def _render(rows):
    return render_list_page(
        page_id="m04",
        title="付款计划",
        tips=TIPS,
        kpis=[{"k": "完全匹配", "v": 3, "s": "笔 · 当前筛选"}],
        filters=FILTERS,
        columns=COLUMNS,
        rows=rows,
        empty_text="当前筛选无付款计划行",
        sort_key="m04:plans",
    )


@acc("ACC-PAY-IA-001", "001-01")
def test_付款域页面划分与导航符合范围定义():
    ids = tuple(p["id"] for p in PAY_DOMAIN_PAGES)
    assert ids == ("m03", "m04", "m05")                     # 付款域恰好三页（§4.1.2）
    covered = set()
    for page in PAY_DOMAIN_PAGES:
        assert page["covers"], f"{page['id']} 必须回答它覆盖「包含」里的哪几项"
        assert set(page["covers"]) <= set(SCOPE_INCLUDED)
        covered |= set(page["covers"])
    assert covered == set(SCOPE_INCLUDED)                   # 「包含」的每一项都有页面承载
    # 「不包含」的任何一项都不得成为页面（项目端操作 / 大领导审批 / 会计记账 / 集采欠款 / 领导驾驶舱）
    assert len(SCOPE_EXCLUDED) == 5
    assert nav_violations() == []


@acc("ACC-PAY-IA-001", "001-02")
def test_列表页固定五段骨架顺序():
    assert LIST_PAGE_SEGMENTS == ("tip", "kpis", "filter", "data", "empty")
    html = _render([{"year_month": "2026-08", "doc_no": "D1",
                     "planned_amount": "100.00", "audit_result": "完全匹配", "op": ""}])
    # 有数据 ⇒ 前四段按固定顺序出现；空态提示行不渲染
    assert segment_sequence(html) == ["tip", "kpis", "filter", "data"]
    assert 'class="fbar"' in html and "<table" in html and 'class="kpis"' in html
    # 无数据 ⇒ 末段「空态提示行」出现，且恒为**最后一段**
    empty = _render([])
    seq = segment_sequence(empty)
    assert seq == ["tip", "kpis", "filter", "data", "empty"]
    assert seq[-1] == LIST_PAGE_SEGMENTS[-1]
    # 任何渲染结果的段序都必须是固定骨架的**前缀**（不得乱序 / 跳段）
    for h in (html, empty):
        assert segment_sequence(h) == list(LIST_PAGE_SEGMENTS[: len(segment_sequence(h))])
    # 空态提示行必须给提示文案，且跨列数 = 表头列数（R10①，不得写死）
    assert "当前筛选无付款计划行" in empty
    assert f'colspan="{len(COLUMNS)}"' in empty


@acc("ACC-PAY-IA-001", "001-03")
def test_一个页面只给一个口径说明折叠块():
    html = _render([])
    assert tip_block_count(html) == 1                 # **只有一处**折叠块
    assert html.count("<details") == 1
    assert html.count('class="tip"') == 1
    assert html.count("<li>") == len(TIPS)            # 多条口径**条目化**并进同一个块
    assert "口径说明 · 3 条" in html                   # 摘要 = 条数实时算
    # 单条口径也不新开一块（仍是一块一条目）
    assert tip_block_count(_render([]).replace("<li>", "<li>", 1)) == 1
    one = render_list_page(page_id="m04", title="付款计划", tips=TIPS[:1], filters=FILTERS,
                           columns=COLUMNS, rows=[], empty_text="无", sort_key="m04:plans")
    assert tip_block_count(one) == 1 and one.count("<li>") == 1


@acc("ACC-PAY-IA-001", "001-04")
def test_表头点击排序可用():
    html = _render([{"year_month": "2026-08", "doc_no": "D1", "planned_amount": "100.00",
                     "audit_result": "完全匹配", "op": ""}])
    assert "data-sort" in html
    assert 'data-sort-key="m04:plans"' in html
    assert is_sortable("单据年月") is True
    assert is_sortable("本月预付款金额") is True
    assert is_sortable("操作") is False           # 「操作」列天然不可排

    rows = [
        {"year_month": "2026-08-01", "doc_no": "b"},
        {"year_month": "2026-07-01", "doc_no": "a"},
        {"year_month": "2026-09-01", "doc_no": "c"},
    ]
    asc = sort_rows(rows, column="year_month", direction=SORT_ASC)
    assert [r["year_month"] for r in asc] == ["2026-07-01", "2026-08-01", "2026-09-01"]
    desc = sort_rows(rows, column="year_month", direction=SORT_DESC)
    assert [r["year_month"] for r in desc] == ["2026-09-01", "2026-08-01", "2026-07-01"]
    back = sort_rows(rows, column="year_month", direction=SORT_NONE)
    assert [r["year_month"] for r in back] == [r["year_month"] for r in rows]   # 回到原序
    # 三态循环闭合：原序 → 升 → 降 → 原序
    assert next_sort_direction(SORT_NONE) == SORT_ASC
    assert next_sort_direction(SORT_ASC) == SORT_DESC
    assert next_sort_direction(SORT_DESC) == SORT_NONE
    # 钉住行（合计 / 空态）恒在最底，不参与排序
    mixed = [
        {"year_month": "2026-09-01", "kind": "data"},
        {"year_month": "合计", "kind": "sum"},
        {"year_month": "2026-07-01", "kind": "data"},
    ]
    out = sort_rows(mixed, column="year_month", direction=SORT_ASC,
                    pinned=lambda r: r["kind"] != "data")
    assert [r["kind"] for r in out] == ["data", "data", "sum"]
    # 数值列按数值排（不是按字符串）：100 应排在 20 之后
    nums = [{"v": "100"}, {"v": "20"}]
    assert [r["v"] for r in sort_rows(nums, column="v", direction=SORT_ASC)] == ["20", "100"]
