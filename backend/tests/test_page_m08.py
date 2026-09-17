"""`MOD-08` **手动 Excel 导入**（§3.6 的降级通道）的工程自检（离线 · 不连库）。

⚠️ 本文件**不绑定 `ACC-*` 判据点**（`@acc()` 显式声明）：抓取与落库的判据在
`test_acc_inv_fetch.py` 里由纯函数钉住；本文件守的是**降级通道这一层** ——
「上传 i8 导出的那个 xlsx」是否真的走**同一条解析 ＋ 幂等落库管线**、入口是否真的在。
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from app.mod08_inv import importer
from app.mod08_inv.import_router import _apply, _groups_of, _payload, _rows_of
from app.mod08_inv.import_view import render_import_page
from app.mod08_inv.models import InvAdjustment, InvDetail
from app.mod08_inv.repository import load_rows
from app.mod08_inv.service import build_page_data, parse_state
from app.mod08_inv.view import _flash_html, fetch_dialog_html, render_inv_page
from tests.acc_plugin import acc
from tests.m08_helpers import FakeSession, dataset

HEADER = ("序号", "核算年", "核算月", "业务类型", "项目名称", "单据编号", "供应商", "安全费用",
          "物料名称", "计量单位", "规格型号", "物料性质", "数量", "不含税单价", "含税单价",
          "金额", "价税合计", "出入库方向", "仓库", "班组", "部门", "单据日期", "审核日期",
          "是否作废", "wbs编号", "wbs名称", "cbs编号", "cbs名称")


def _row(seq=1, doc_no="K1", wh="甲仓", direction="入库", amount="100.00", void="否") -> list:
    return [seq, 2026, 8, "采购入库", "甲仓项目", doc_no, "某供应商", "0",
            "焊条", "kg", "J422", "主材", "10", "10.00", "11.30",
            amount, "113.00", direction, wh, "班组A", "材料科", "2026-08-05", "2026-08-06",
            void, "W1", "W1名称", "C1", "C1名称"]


def _xlsx(rows: list[list]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "报表1"
    ws.append(list(HEADER))
    for r in rows:
        ws.append(list(r))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _new_session() -> FakeSession:
    """一张空表（手动导入是从零灌数 —— 与抓取落到同一张表、同一套键）。"""
    return FakeSession({InvDetail: [], InvAdjustment: []})


# ============================================================ 与抓取同一条管线


@acc()
def test_手动导入与抓取共用同一解析与幂等落库():
    content = _xlsx([_row(doc_no="K1"), _row(seq=2, doc_no="K2", amount="200.00")])
    rows = importer.parse_rows(content)                    # ← 与抓取**同一个**解析器
    assert len(rows) == 2 and rows[0]["warehouse_name"] == "甲仓"

    # 预览 → 暂存 → 取回：金额列**转回 Decimal**（暂存只放纯数据，不放文件）
    back = _rows_of(_payload(rows))
    assert back[0]["amount"] == Decimal("100.00") and isinstance(back[0]["amount"], Decimal)
    assert _groups_of(back) == [{"ym": "2026-08", "warehouse": "甲仓", "rows": 2,
                                 "amount": "300.00"}]

    s = _new_session()
    first = _apply(s, back)                                # ← 与抓取**同一个**落库出口
    assert first["totals"]["inserted"] == 2 and len(load_rows(s)) == 2
    second = _apply(s, back)
    assert second["totals"] == {"inserted": 0, "updated": 2, "deleted": 0,
                               "kept_with_adjustment": 0}
    assert len(load_rows(s)) == 2, "同月同仓库重导 = 刷新，不产生重复行（§9.5）"


@acc()
def test_手动导入照样不动有调整单的行():
    s = _new_session()
    rows = importer.parse_rows(_xlsx([_row(doc_no="K1"), _row(seq=2, doc_no="K2")]))
    _apply(s, _rows_of(_payload(rows)))
    target = next(d for d in s.by_model[InvDetail] if d.doc_no == "K2")
    s.by_model[InvAdjustment].append(
        InvAdjustment(id=901, row_id=target.id, before_amount=Decimal("100.00"),
                      amount=Decimal("80.00"), remark="对账差异", operator="科室用户"))

    part = _apply(s, _rows_of(_payload(importer.parse_rows(_xlsx([_row(doc_no="K1")])))))
    assert part["totals"]["deleted"] == 0 and part["totals"]["kept_with_adjustment"] == 1
    assert len(s.by_model[InvDetail]) == 2, "有调整单的行必须保留（否则调整单被连带删）"
    assert s.by_model[InvAdjustment][0].amount == Decimal("80.00"), "调整单一字未改"


# ============================================================ 入口与降级提示


@acc()
def test_入口在页面与降级回执里都真的给出来了():
    assert 'action="/m08/import/preview"' in render_import_page()
    assert "报表1" in render_import_page()                  # 说明里写了读哪张工作表
    # ① 明细页工具栏有入口
    html = render_inv_page(build_page_data(FakeSession(dataset()), parse_state({})))
    assert 'href="/m08/import"' in html and "手动导入 Excel" in html
    # ② 抓取失败 ⇒ 降级回执**必须给出这条通道**（§3.6：降级要显式说明）
    flash = _flash_html({"kind": "degraded", "message": "i8 接口 500"})
    assert "已降级为手动 Excel 导入" in flash and 'href="/m08/import"' in flash
    # ③ 抓取弹窗仍然只走抓取（不把两条路混在一个按钮里）
    assert 'method="post" action="/m08/fetch"' in fetch_dialog_html("2026-08")
