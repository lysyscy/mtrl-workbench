"""签名图**取值与绑定**的自检（离线 · 不连库 · **不绑定 `ACC-*` 判据点**）。

关键契约（**2026-09-15 真机对照确定**）：
- 模板「办理节点」名 ↔ 流程节点 **`task_des`**；
- 图片地址 ↔ 流程节点 **`signature`**（相对路径，带 `?s=<token>`）。

2026-09-16 补：模板侧取节点名有**两种筛选写法**（见 `template.NODE_FILTER_FIELD` / `NODE_FIELD_ID`），
漏认第 2 种 ⇒ 该格连槽位都不算 ⇒ **静默印出缺签名的件**（实测：其他支出 · 核算部部长）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.errors import MustReportError
from app.mod03_notice.print.signatures import (
    _to_data_uri,
    cache_key,
    check_signature_coverage,
    collect_signature_paths,
    signature_slots,
    unresolved_image_slots,
)
from app.mod03_notice.print.template import PrintTemplate, node_of, parse_design

FIXTURES = Path(__file__).resolve().parent / "fixtures"
OTHER = FIXTURES / "i8_print_design_sample.json"
NOTICE = FIXTURES / "i8_print_design_notice.json"


def _tpl(path: Path):
    return parse_design(json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------- 节点名 → 地址


def test_节点名取task_des且跳过空签名():
    flow = [
        {"task_des": "流程发起", "signature": ""},                  # 无签名 ⇒ 跳过
        {"task_des": "项目经理", "signature": "/a?s=1"},
        {"task_des": "", "signature": "/b"},                        # 无节点名 ⇒ 跳过
        {"task_des": "核算部部长", "signature": "/c"},
    ]
    assert collect_signature_paths(flow) == {"项目经理": "/a?s=1", "核算部部长": "/c"}


def test_同名节点取靠后的那个():
    """流程数组按时间正序 ⇒ 靠后 = 更新的一次处理。"""
    flow = [
        {"task_des": "项目经理", "signature": "/old"},
        {"task_des": "核算部部长", "signature": "/x"},
        {"task_des": "项目经理", "signature": "/new"},
    ]
    assert collect_signature_paths(flow)["项目经理"] == "/new"


def test_空流程与脏数据不炸():
    assert collect_signature_paths([]) == {}
    assert collect_signature_paths(None) == {}
    assert collect_signature_paths(["不是字典", {"task_des": None, "signature": None}]) == {}


# ---------------------------------------------------------------- 缓存键 / MIME


def test_缓存键忽略易变的query():
    # `?s=<token>` 每次都变 ⇒ 带 query 会永不命中缓存
    assert cache_key("/a/b.png?s=abc") == cache_key("/a/b.png?s=xyz")
    assert cache_key("/a/b.png") != cache_key("/a/c.png")


def test_按魔术字节判mime():
    assert _to_data_uri(b"\xff\xd8\xff" + b"0" * 200).startswith("data:image/jpeg;base64,")
    assert _to_data_uri(b"GIF89a" + b"0" * 200).startswith("data:image/gif;base64,")
    assert _to_data_uri(b"BM" + b"0" * 200).startswith("data:image/bmp;base64,")
    assert _to_data_uri(b"\x89PNG\r\n\x1a\n" + b"0" * 200).startswith("data:image/png;base64,")


# ---------------------------------------------------------------- 模板侧节点名


def _tpl_with(cells: list[dict]) -> PrintTemplate:
    return PrintTemplate(print_id="X", print_name="测试", sheet_name="表1", cols=2, rows=4,
                         widths={0: 100, 1: 80}, heights={}, cells=cells, margin={}, page={})


def _img_cell(row: int, col: int, data_filter: list[dict]) -> dict:
    return {"cellType": "field", "row": row, "col": col, "className": "htCenter",
            "cellData": {"otherShowType": "image", "dataFilter": data_filter}, "cellBorders": {}}


def test_模板签名格节点名去重保序():
    # ⚠️ 2026-09-16 起「核算部部长」**必须在内**（其他支出模板 row=15 col=3 那格）——
    #    旧断言按"漏认第 2 种写法"的错误输出写死了 6 个，等于把 bug 钉成了契约。
    assert signature_slots(_tpl(OTHER)) == [
        "项目经理", "事业部分部经理", "工程公司主管审核", "分公司经理",
        "核算部部长", "财务公司经理", "总经理",
    ]
    # 付款通知书模板 8 个图片格里有重名（核算部部长 ×2）⇒ 去重后 7 个
    notice = signature_slots(_tpl(NOTICE))
    assert notice.count("核算部部长") == 1
    assert notice[0] == "项目经理" and "资产管理部总经理" in notice


def test_图片格认两种筛选写法():
    """① `fieldId="办理节点"`（自定义字段）· ② `fieldId="task_des"`（直接筛流程字段）—— 都取 `value`。"""
    assert node_of(_img_cell(0, 0, [{"fieldId": "办理节点", "value": "项目经理"}])) == "项目经理"
    assert node_of(_img_cell(0, 0, [
        {"fieldId": "task_des", "dataSetId": "workflow_history", "value": "核算部部长"},
    ])) == "核算部部长"
    # 空筛选 ⇒ 拿不到节点（i8 本身也印空 ⇒ 合法）
    assert node_of(_img_cell(0, 0, [])) == ""
    # 第 ① 种写法值为空时，继续往后找可用写法（不早退）
    assert node_of(_img_cell(0, 0, [
        {"fieldId": "办理节点", "value": ""},
        {"fieldId": "task_des", "value": "分公司经理"},
    ])) == "分公司经理"


def test_真实模板里没有认不出的签名格():
    """两份真机模板的图片格**两种写法都被认得** ⇒ 未决清单必须为空（否则会误停单）。"""
    assert unresolved_image_slots(_tpl(OTHER)) == []
    assert unresolved_image_slots(_tpl(NOTICE)) == []


def test_有筛选却认不出节点必须报警():
    """⚠️ 静默失效的正面堵口：认不出写法 ⇒ 不许留白，必须停单报错。"""
    bad_filter = [{"fieldId": "某个未知字段", "value": "核算部部长"}]
    tpl = _tpl_with([_img_cell(0, 0, bad_filter), _img_cell(1, 0, [{"fieldId": "办理节点", "value": "项目经理"}])])
    assert unresolved_image_slots(tpl) == [(0, 0, bad_filter)]
    with pytest.raises(MustReportError) as ei:
        # 其余签名**都命中了** —— 所以 001-06（零命中）根本盖不住这种形态，必须单独报
        check_signature_coverage(tpl, [{"task_des": "项目经理", "signature": "/p.png"}], {"项目经理": "data:image/png;base64,AA"})
    assert "取不到审批节点名" in str(ei.value) and "row0col0" in str(ei.value)


def test_无筛选的签名格不算未决且不报错():
    """无筛选 = i8 本身也印空（实测过）⇒ 合法；不许把它当"未决"误报停单。"""
    tpl = _tpl_with([_img_cell(0, 0, []), _img_cell(1, 0, [{"fieldId": "办理节点", "value": "项目经理"}])])
    assert unresolved_image_slots(tpl) == []
    cov = check_signature_coverage(
        tpl, [{"task_des": "项目经理", "signature": "/p.png"}], {"项目经理": "data:image/png;base64,AA"}
    )
    assert cov.filled == ["项目经理"] and cov.unresolved == []


# ---------------------------------------------------------------- 两个模板的差异（防"写死"）


def test_两个模板结构确实不同():
    """⚠️ 这条钉住"**必须模板驱动**"：两个版式的行列数/格数/下边距都不一样，写死必错。"""
    other, notice = _tpl(OTHER), _tpl(NOTICE)
    assert (other.cols, other.rows, len(other.cells)) == (8, 20, 79)
    assert (notice.cols, notice.rows, len(notice.cells)) == (8, 18, 73)
    assert other.print_id != notice.print_id
    assert len(notice.field_cells()) != len(other.field_cells())
