"""版式**模板驱动渲染**的工程自检（离线 · 不连库 · **不绑定 `ACC-*` 判据点**）。

数据来源 = **2026-09-15 真机取样**的版式模板（`tests/fixtures/i8_print_design_sample.json`），
所以这些断言钉的是**真实模板形态**，不是手写想象。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.errors import MustReportError
from app.mod03_notice.print.template import (
    DS_DETAIL,
    GEOMETRY,
    PrintTemplate,
    cell_css,
    extract_design_data,
    is_image_cell,
    node_of,
    parse_design,
    render_html,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "i8_print_design_sample.json"


def _sample_data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 解析


def test_真实样本能解析出模板且几何参数齐全():
    tpl = parse_design(_sample_data())
    assert tpl.print_name == "其他支出"
    assert tpl.sheet_name == "报表1"
    assert (tpl.cols, tpl.rows) == (8, 20)
    assert len(tpl.cells) == 79
    assert tpl.widths and tpl.heights               # 列宽 / 行高都取自模板，不写死
    assert tpl.margin and "top" in tpl.margin       # 页边距来自 printSetting
    assert tpl.data_set_infos                        # dataSetInfos 可解析


def test_真实样本里存在明细数据集之外的主表字段格():
    tpl = parse_design(_sample_data())
    fields = tpl.field_cells()
    assert fields, "模板里应至少有一个字段格"
    ids = {str((c.get("cellData") or {}).get("fieldId")) for c in fields}
    assert "项目名称" in ids and "收款单位" in ids    # 与素材包 build_values 的字段名对得上


def test_取不到模板必须显式报错():
    with pytest.raises(MustReportError):
        parse_design({"printSchema": "[]", "printSetting": "[]"})
    with pytest.raises(MustReportError):
        parse_design({"printSchema": json.dumps([{"cells": []}]), "printSetting": "[]"})
    with pytest.raises(MustReportError):
        parse_design("不是对象")


def test_空壳的headerFooter与paging放行而带内容的才拦():
    # 真机样本里这两项**恒为空壳**（content=null / bodies=[]）⇒ 必须能正常解析
    assert parse_design(_sample_data()).print_name == "其他支出"

    data = _sample_data()
    setting = json.loads(data["printSetting"])
    setting[0]["printConfig"]["headerFooter"] = {"header": {"content": "页眉真的有字"}}
    data["printSetting"] = json.dumps(setting, ensure_ascii=False)
    with pytest.raises(MustReportError):
        parse_design(data)


def test_外层Data与裸Data两种形态都能取出():
    data = _sample_data()
    assert extract_design_data({"Status": "success", "Data": data}) is data
    assert extract_design_data(data) is data
    with pytest.raises(MustReportError):
        extract_design_data({"Status": "success"})


# ---------------------------------------------------------------- 样式


def test_字号按scale缩放且对齐与粗体来自className():
    css = cell_css({"className": "htMiddle htCenter htFontSize_26"})
    assert f"font-size:{26 * GEOMETRY['scale']:.2f}px" in css
    assert "text-align:center" in css and "vertical-align:middle" in css
    right = cell_css({"className": "htRight htFontWeight_700"})
    assert "text-align:right" in right and "font-weight:700" in right


def test_框线缺省不画_hide也不画():
    css = cell_css({"className": "", "cellBorders": {}})
    for side in ("top", "bottom", "left", "right"):
        assert f"border-{side}:none" in css
    hidden = cell_css({"cellBorders": {"bottom": {"hide": True}, "top": {"color": "#ff0000"}}})
    assert "border-bottom:none" in hidden
    assert "border-top:1.00px solid #ff0000" in hidden


def test_图片格两种筛选写法都认_无筛选就不渲染():
    """模板侧取节点名有**两种写法**（2026-09-16 补第 2 种，漏认会静默漏印签名）。"""
    with_filter = {"cellType": "field", "cellData": {
        "otherShowType": "image", "dataFilter": [{"fieldId": "办理节点", "value": "核算部部长"}]}}
    assert is_image_cell(with_filter) is True
    assert node_of(with_filter) == "核算部部长"
    # ② 直接筛流程字段 `task_des`（其他支出模板 row15col3 那格就是这个写法）
    task_des_form = {"cellType": "field", "cellData": {
        "otherShowType": "image",
        "dataFilter": [{"fieldId": "task_des", "dataSetId": "workflow_history", "value": "核算部部长"}]}}
    assert node_of(task_des_form) == "核算部部长"
    no_filter = {"cellType": "field", "cellData": {"otherShowType": "image", "dataFilter": []}}
    assert is_image_cell(no_filter) is True
    assert node_of(no_filter) == ""            # 无筛选 ⇒ 拿不到节点 ⇒ 不渲染（与真实打印件一致）


# ---------------------------------------------------------------- 渲染（用迷你模板精确钉行为）


def _mini() -> PrintTemplate:
    cells = [
        {"cellType": "text", "row": 0, "col": 0, "colspan": 2,
         "className": "htCenter htFontSize_26", "cellData": {"value": "标题<T>"}, "cellBorders": {}},
        {"cellType": "field", "row": 1, "col": 0, "colspan": 2, "className": "htLeft",
         "cellData": {"dataSetId": "DS1", "fieldId": "项目名称"},
         "cellBorders": {"bottom": {"color": "#000000"}}},
        {"cellType": "field", "row": 2, "col": 0, "className": "htCenter",
         "cellData": {"dataSetId": "DET", "fieldId": "单据号"}, "cellBorders": {}},
        {"cellType": "field", "row": 2, "col": 1, "className": "htRight",
         "cellData": {"dataSetId": "DET", "fieldId": "支付金额"}, "cellBorders": {}},
        {"cellType": "field", "row": 3, "col": 0, "colspan": 2, "className": "htCenter",
         "cellData": {"dataSetId": "DS1", "fieldId": "签名", "otherShowType": "image",
                      "dataFilter": [{"fieldId": "办理节点", "value": "核算部部长"}]},
         "cellBorders": {}},
    ]
    return PrintTemplate(print_id="X", print_name="测试", sheet_name="表1", cols=2, rows=5,
                         widths={0: 100, 1: 80}, heights={2: 40}, cells=cells,
                         margin={"top": 5, "left": 10, "right": 10, "down": 5})


DETAIL_IDS = frozenset({"DET"})


def test_渲染出表结构且列宽行高取自模板():
    html, slots = render_html(_mini(), values={}, detail_rows=[{}], detail_ids=DETAIL_IDS)
    assert html.startswith("<!DOCTYPE html>")
    assert html.count("<col ") == 2                            # colgroup 列数 = cols
    assert "@page{size:A4 portrait;margin:5mm 10mm 5mm 10mm;}" in html
    assert '<tr style="height:27.36px">' in html               # heights[2]=40 × scale(0.684)
    assert slots and slots[0][2] == "核算部部长" and slots[0][3] is False   # 无签名图 ⇒ 留空


def test_明细行按数据条数重复渲染():
    rows = [{"单据号": "D1", "支付金额": "10.00"}, {"单据号": "D2", "支付金额": "20.00"}]
    html, _ = render_html(_mini(), values={}, detail_rows=rows, detail_ids=DETAIL_IDS)
    assert html.count(">D1</td>") == 1 and html.count(">D2</td>") == 1
    assert html.count(">10.00</td>") == 1 and html.count(">20.00</td>") == 1
    # 明细行被渲染了 2 次（2 个 <tr>带 rowspan/colspan 组合），而普通行只 1 次
    assert html.count('<td colspan="2" style=') == 3            # 标题 + 项目名称 + 签名（非明细行）


def test_字段格取values的dataSetId点fieldId():
    html, _ = render_html(_mini(), values={"DS1.项目名称": "某某项目"}, detail_rows=[{}],
                          detail_ids=DETAIL_IDS)
    assert "某某项目" in html


def test_静态文本会转义不注入HTML():
    html, _ = render_html(_mini(), values={}, detail_rows=[{}], detail_ids=DETAIL_IDS)
    assert "标题&lt;T&gt;" in html and "标题<T>" not in html


def test_签名图取到才出img():
    html, slots = render_html(_mini(), values={}, detail_rows=[{}], detail_ids=DETAIL_IDS,
                              signatures={"核算部部长": "data:image/png;base64,AAA"})
    assert '<img class="sig" src="data:image/png;base64,AAA">' in html
    assert slots[0][3] is True
