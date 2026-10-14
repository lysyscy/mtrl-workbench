"""页面骨架装配器（`app.mod03_notice.page`）的**工程自检**。

⚠️ 本文件**不绑定 `ACC-*` 判据点**（`@acc()` 显式声明）—— 它守的是**交互规格里的两条"没有判据点"的要求**：
  ① 合计行**视口吸附置底**（CSS 契约，实测见 `docs/reference/sticky-total-row.md`）；
  ② **分段线四处一致**（表头 / 数据行 / 合计行 / 总求和行）—— 设计规则 R13 的「总求和」分段。
若要把它变成 `ACC-*` 判据，属**契约层动作**（要改 `PRD/`）⇒ 本文件刻意只做工程自检。
"""

from __future__ import annotations

import re

from app.mod03_notice.page import (
    STICKY_BOTTOM_CSS,
    VSEP_CSS,
    render_list_page,
)
from tests.acc_plugin import acc

COLUMNS = [
    {"key": "ym", "label": "核算月", "sortable": True},
    {"key": "in_a", "label": "入库·甲", "sortable": True},
    {"key": "in_b", "label": "入库·乙", "sortable": True},
    {"key": "out_a", "label": "出库·甲", "sortable": True, "vsep": True},
    {"key": "out_b", "label": "出库·乙", "sortable": True},
    {"key": "op", "label": "操作", "sortable": False},
]
VSEP_IDX = 3


def _render(**kw):
    args = dict(
        page_id="m06",
        title="过程资料",
        tips=["材料数据单向流"],
        filters=[{"key": "ym", "label": "核算月", "control": "acc-period"}],
        columns=COLUMNS,
        rows=[
            {"ym": "2026-08", "in_a": "1.00", "in_b": "2.00", "out_a": "3.00", "out_b": "4.00", "op": ""},
            {"ym": "2026-09", "in_a": "5.00", "in_b": "6.00", "out_a": "7.00", "out_b": "8.00", "op": ""},
        ],
        empty_text="无数据",
        sort_key="m06:proc",
    )
    args.update(kw)
    return render_list_page(**args)


def _tbody_rows(html: str) -> list[list[str]]:
    tbl = re.search(r"<table\b[^>]*>[\s\S]*?</table>", html)
    body = re.search(r"<tbody\b[^>]*>([\s\S]*?)</tbody>", tbl.group(0))
    rows = re.findall(r"<tr\b[^>]*>[\s\S]*?</tr>", body.group(1))
    return [re.findall(r"<td\b[^>]*>", r) for r in rows]


@acc()
def test_分段线四处一致():
    """设计规则 R13：段首列的分段竖线必须在**表头 / 数据行 / 合计行 / 总求和行**四处一致。"""
    html = _render(summary=[{"ym": "合计"}, {"ym": "总求和（本表）"}])
    head = re.findall(r"<th\b[^>]*>", html)
    assert len(head) == len(COLUMNS)
    assert 'class="srt vsep"' in head[VSEP_IDX]          # 表头
    assert "vsep" not in head[VSEP_IDX - 1]
    for tds in _tbody_rows(html):                        # 数据行 ＋ 两条合计行
        assert len(tds) == len(COLUMNS), tds
        assert 'class="vsep"' in tds[VSEP_IDX], tds[VSEP_IDX]
        assert "vsep" not in tds[VSEP_IDX - 1]


@acc()
def test_合计行两条_合计与总求和():
    html = _render(summary=[{"ym": "合计"}, {"ym": "总求和（本表）"}])
    assert html.count('data-pin="1"') == 2               # 两条合计类行都在
    assert html.index("合计") < html.index("总求和（本表）")   # 且顺序 = 合计 → 总求和
    rows = _tbody_rows(html)
    assert len(rows) == 2 + 2                            # 2 数据行 ＋ 2 合计行


@acc()
def test_分段表可关掉吸附但仍钉在表尾():
    """分段表 / 分组表的合计行**不吸附**（`summary_sticky=False`），但**数据序照样钉在最后**。"""
    sticky = _render(summary={"ym": "合计"})
    assert 'class="sum sumrow" data-pin="1"' in sticky
    flat = _render(summary={"ym": "合计"}, summary_sticky=False)
    assert "sumrow" not in flat
    assert 'class="sum" data-pin="1"' in flat            # 仍然钉表尾、不参与排序
    # 空态行与合计行的 data-pin 语义不同：空态是 `data-seg="empty"`
    assert 'data-seg="empty"' not in _render(summary={"ym": "合计"})


@acc()
def test_吸附置底的CSS契约_必须作用在tr上():
    """钉住实测结论：sticky **不能**写在 `td` 上（原型那套写法永不生效）。"""
    assert "tr.sumrow{position:sticky" in STICKY_BOTTOM_CSS.replace(" ", "")
    assert ">td{position:sticky" not in STICKY_BOTTOM_CSS.replace(" ", "")
    assert ".dt th.vsep,.dt td.vsep" in VSEP_CSS
