"""`API-03` 库存单据明细 · **抓取 → 解析 → 幂等落库** —— 离线自检（**不连库、不连网**）。

对应判据 `ACC-INV-FETCH-001`（9 点，`PRD/验收/验收基线.json`）：
- `001-01` 入参 = **「起止年月」四个独立值**（`a`/`b`/`aa`/`bb`）＋ 项目 key = `xmid`；⛔ 不是「单据日期起止」
- `001-02` 三项标识（`rep_id` / `dataSetId` / `reportName`）**逐表不同**；库存单据的 `reportName` **必须 null**
- `001-03` 抓取**只允许单月**（跨月 / 整年 / 全部一律拒绝，§9.2）
- `001-04` 解析**按表头文字认列**（不写死下标）；**关键列缺失 ⇒ 报错不猜**
- `001-05` 核算年月取导出文件的「**核算年 / 核算月**」列，⛔ 不是「单据日期」
- `001-06` 落库**幂等**：同「核算年月 ＋ 项目」重抓 ⇒ 更新而非重复插入（§9.5）
- `001-07` ⭐ 重抓**不动调整单**：本次不再出现但有调整单的行**保留**（`ENT-04` / §5.2.4）
- `001-08` 抓前**二次确认**且**显式告知会强踢**；接口不可用 ⇒ **显式报错待人处理**且**不静默**
         （⚠️ 2026-09-22 用户裁定：手动 Excel 导入兜底**已删**，⛔ 不复活）；⛔ **失败不得自动重试登录**（D9 —— 导出调用只发生**一次**）
- `001-09` 每次抓取留一条**执行记录**（时间 · 对象 · 结果 · 失败原因）
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import pytest

from app.core.config import I8_REPORTS
from app.core.errors import MustReportError
from app.mod02_i8 import report_export
from app.mod02_i8.models import RunRecord
from app.mod08_inv import fetch_service as FS
from app.mod08_inv import importer
from app.mod08_inv.models import InvAdjustment, InvDetail
from app.mod08_inv.repository import load_rows
from tests.acc_plugin import acc
from tests.m04_helpers import make_project
from tests.m08_helpers import FakeSession

CASE = "ACC-INV-FETCH-001"

HEADER = ("序号", "核算年", "核算月", "业务类型", "项目名称", "单据编号", "供应商", "安全费用",
          "物料名称", "计量单位", "规格型号", "物料性质", "数量", "不含税单价", "含税单价",
          "金额", "价税合计", "出入库方向", "仓库", "班组", "部门", "单据日期", "审核日期",
          "是否作废", "wbs编号", "wbs名称", "cbs编号", "cbs名称")


def _row(seq=1, year=2026, month=8, doc_no="K1", wh="甲仓", direction="入库",
         prop="主材", amount="100.00", doc_date="2026-08-05", void="否") -> list:
    return [seq, year, month, "采购入库", "甲仓项目", doc_no, "某供应商", "0",
            "焊条", "kg", "J422", prop, "10", "10.00", "11.30",
            amount, "113.00", direction, wh, "班组A", "材料科", doc_date, "2026-08-06",
            void, "W1", "W1名称", "C1", "C1名称"]


def _xlsx(rows: list[list], header=HEADER) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "报表1"
    ws.append(list(header))
    for r in rows:
        ws.append(list(r))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _projects() -> list:
    p = make_project(1, "甲仓", "甲公司项目")
    p.phid = "3700000000000123"
    return [p]


def _sess(by_model: dict | None = None) -> FakeSession:
    base = {InvDetail: [], InvAdjustment: [], RunRecord: []}
    base.update(by_model or {})
    base.setdefault(type(make_project(9, "x")), _projects())
    return FakeSession(base)


class _Client:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _run(s, *, content=None, boom=None, month="2026-08", confirmed=True, calls=None):
    def fake_export(client, ym, ids):           # noqa: ANN001
        if calls is not None:
            calls.append((ym, ids))
        if boom is not None:
            raise boom
        return content

    return FS.run_fetch(s, year_month=month, confirmed=confirmed, operator="科室用户",
                        client_factory=_Client, export=fake_export)


# ------------------------------------------------------------ 001-01 / 001-02 入参与标识

@acc(CASE, "001-01")
def test_入参是起止年月四个独立值且不是单据日期():
    body = report_export.build_body(spec_key="inv", year_month="2026-08", proj_ids="1,2")
    params = {p["paramKey"]: p for p in body["queryParams"][0]["sheetQueryParams"]}
    assert set(params) == {"a", "b", "aa", "bb", "xmid"}
    assert (params["a"]["paramValue"], params["b"]["paramValue"]) == ("2026", "8")
    assert (params["aa"]["paramValue"], params["bb"]["paramValue"]) == ("2026", "8")
    assert params["a"]["paramType"] == "1" and params["b"]["label"] == "开始核算月"
    # 项目：paramType=0 / fieldType="0" / 值为 id 列表
    assert params["xmid"]["paramType"] == "0" and params["xmid"]["fieldType"] == "0"
    assert params["xmid"]["paramValue"] == "1,2"
    # ⛔ 不得混入 API-01 的「单据日期区间」口径
    text = str(body)
    assert "BillDt" not in text and "queryfilter" not in text and "start_date" not in text


@acc(CASE, "001-02")
def test_三项标识逐表不同且库存单据的报表名为空():
    spec = I8_REPORTS["inv"]
    assert spec["rep_id"] == "3700000000000104"
    assert spec["dataset_id"] == "3700000000000165"
    assert spec["proj_param"] == "xmid"           # 收发结存用 pc
    assert spec["report_name"] is None            # ⭐ 必须传 null
    body = report_export.build_body(spec_key="inv", year_month="2026-08", proj_ids="1")
    assert body["reportName"] is None and body["reportId"] == spec["rep_id"]
    assert body["exportType"] == "excel"
    # 未登记的报表 ⇒ 报错不猜
    # ⚠️ 这里**不得**拿某张具体表当"未登记"的例子（`setl` 于 2026-09-16 已登记 ⇒ 会误红）。
    #    判据的**意图**是"没登记的键必须报错"，不是"某张表恰好没登记" ⇒ 用一个不可能登记的键。
    with pytest.raises(MustReportError):
        report_export.report_spec("__unregistered__")


# ------------------------------------------------------------ 001-03 只允许单月

@acc(CASE, "001-03")
def test_抓取只允许单月():
    assert report_export.single_month("2026-08") == ("2026", "8", "2026", "8")
    assert FS.build_plan("2026-08")["ym"] == "2026-08"
    for bad in ("2026-01~2026-06", "2026", ""):
        with pytest.raises(MustReportError):
            FS.build_plan(bad)


# ------------------------------------------------------------ 001-04 按表头认列

@acc(CASE, "001-04")
def test_按表头文字认列且缺关键列即报错():
    rows = importer.parse_rows(_xlsx([_row()]))
    assert rows[0]["doc_no"] == "K1" and rows[0]["material_property"] == "主材"

    # 挪列（把「金额」挪到最前）也能认出 ⇒ 证明**不依赖下标**
    base = _row()
    moved = ["金额"] + [h for h in HEADER if h != "金额"]
    by_name = dict(zip(HEADER, base))
    rows2 = importer.parse_rows(_xlsx([[by_name[h] for h in moved]], header=moved))
    assert rows2[0]["amount"] == Decimal("100.00") and rows2[0]["doc_no"] == "K1"

    # 缺「物料性质」⇒ 报错不猜
    header = tuple(h for h in HEADER if h != "物料性质")
    with pytest.raises(MustReportError):
        importer.parse_rows(_xlsx([[_row()[HEADER.index(h)] for h in header]], header=header))


# ------------------------------------------------------------ 001-05 核算年月来源

@acc(CASE, "001-05")
def test_核算年月取自核算年月列而不是单据日期():
    rows = importer.parse_rows(_xlsx([
        _row(year=2026, month=7, doc_date="2026-08-31"),
    ]))
    assert rows[0]["ym"] == "2026-07", "必须取核算年/核算月列"
    assert rows[0]["doc_date"] == "2026-08-31"
    # 数字列非数字 ⇒ 报错（不静默吞掉）
    with pytest.raises(MustReportError):
        importer.parse_rows(_xlsx([_row(amount="—")]))


# ------------------------------------------------------------ 001-06 幂等落库

@acc(CASE, "001-06")
def test_同月同项目重抓幂等不产生重复行():
    s = _sess()
    content = _xlsx([_row(doc_no="K1"), _row(seq=2, doc_no="K2", amount="200.00")])
    first = _run(s, content=content)
    assert first["ok"] and first["stats"]["inserted"] == 2
    assert len(load_rows(s)) == 2

    second = _run(s, content=content)
    assert second["stats"]["inserted"] == 0 and second["stats"]["updated"] == 2
    assert len(load_rows(s)) == 2, "重抓同月不得产生重复行（§9.5 幂等）"
    # 换月 / 减行不留残影
    third = _run(s, content=_xlsx([_row(doc_no="K1")]))
    assert third["stats"]["deleted"] == 1 and len(load_rows(s)) == 1

    # ⭐⭐ **同月多仓库**：刷新范围 = 「核算年月 ＋ 仓库」——
    #     一次抓取里两个仓库都必须留下（2026-09-17 真机抓出：原先只按 `ym` 取 existing ⇒
    #     后一个仓库的刷新会把前一个仓库的行删掉，实测 559 行只剩 18 行）
    s2 = _sess()
    both = _run(s2, content=_xlsx([_row(doc_no="K1"), _row(seq=1, doc_no="K9", wh="乙仓")]))
    assert both["stats"]["inserted"] == 2
    left = {r["warehouse"] for r in load_rows(s2)}
    assert left == {"甲仓", "乙仓"}, f"同月多仓库只留下了 {left} —— 幂等范围必须含仓库"
    # 重抓（两仓库都在）⇒ 全更新、一行不删
    again = _run(s2, content=_xlsx([_row(doc_no="K1"), _row(seq=1, doc_no="K9", wh="乙仓")]))
    assert again["stats"] == {"inserted": 0, "updated": 2, "deleted": 0,
                              "kept_with_adjustment": 0}
    assert {r["warehouse"] for r in load_rows(s2)} == {"甲仓", "乙仓"}


# ------------------------------------------------------------ 001-07 重抓不动调整单

@acc(CASE, "001-07")
def test_重抓不动调整单且消失的有调整行被保留():
    s = _sess()
    _run(s, content=_xlsx([_row(doc_no="K1"), _row(seq=2, doc_no="K2", amount="200.00")]))
    target = next(r for r in s.by_model[InvDetail] if r.doc_no == "K2")
    s.by_model[InvAdjustment].append(
        InvAdjustment(id=901, row_id=target.id, before_amount=Decimal("200.00"),
                      amount=Decimal("150.00"), remark="对账差异", operator="科室用户"))

    # ① 重抓：金额跟随新值，但调整单原封不动
    out = _run(s, content=_xlsx([_row(doc_no="K1"), _row(seq=2, doc_no="K2", amount="260.00")]))
    assert out["stats"]["updated"] == 2
    assert len(s.by_model[InvAdjustment]) == 1
    assert s.by_model[InvAdjustment][0].amount == Decimal("150.00"), "重抓不得改调整单"
    assert target.amount == Decimal("260.00"), "源字段应跟随 i8 新值"

    # ② 该行在 i8 里消失 ⇒ **保留**（否则调整单被 CASCADE 连带删掉）
    out2 = _run(s, content=_xlsx([_row(doc_no="K1")]))
    assert out2["stats"]["deleted"] == 0 and out2["stats"]["kept_with_adjustment"] == 1
    assert len(s.by_model[InvDetail]) == 2 and len(s.by_model[InvAdjustment]) == 1


# ------------------------------------------------------------ 001-08 二次确认 / 降级 / 不重试

@acc(CASE, "001-08")
def test_未二次确认即拒且失败降级且不自动重试登录():
    # ⚠️ 2026-09-18（`§19` 批 2）：原先这三条借**旧页**的抓取弹窗 html 观测（确认 token、「强踢」告知、
    # 表单 action）；旧页删除（`D18`）后形态搬到壳 ——
    # `test_wired_m08.py::test_抓取弹窗默认取本页核算年月且讲清强踢` ✓。
    # 下面「未二次确认即拒」是**服务层**的实质（`FS.CONFIRM_TOKEN` ＋ `confirmed=False` ⇒ 拒），留着。

    s = _sess()
    with pytest.raises(MustReportError):
        _run(s, content=_xlsx([_row()]), confirmed=False)
    assert s.by_model[RunRecord] == [], "用法错误不写执行记录"

    # 接口不可用 ⇒ **显式报错待人处理**（2026-09-22 用户裁定：手动导入兜底已删）；⛔ 导出**只调用一次**（D9）
    calls: list = []
    s2 = _sess()
    out = _run(s2, boom=RuntimeError("i8 接口 500"), calls=calls)
    assert out["ok"] is False and out["degraded"] is True
    assert "i8 抓不到数" in out["message"], out["message"]
    assert "excel_import_available" not in out, "手动导入已删，不得再承诺这条通道"
    assert len(calls) == 1, "失败不得自动重试（更不得重试登录）"

    # ⭐ **撤项守卫**（2026-09-22）：手动导入端点**不得复活**（`T8` 亦守，这里在 OpenAPI 面再钉一道）
    from app.main import create_app

    paths = set(create_app().openapi()["paths"])
    assert not any(p.startswith("/api/m08/import") for p in paths), \
        "手动导入端点已按用户 2026-09-22 裁定删除 —— ⛔ 别加回来"


# ------------------------------------------------------------ 001-09 执行记录

@acc(CASE, "001-09")
def test_每次抓取留一条执行记录():
    s = _sess()
    ok = _run(s, content=_xlsx([_row(), _row(seq=2, doc_no="K2")]))
    rec = next(r for r in s.by_model[RunRecord] if r.id == ok["run_record_id"])
    assert (rec.run_type, rec.status, rec.success_count) == ("fetch", "success", 2)
    assert "2026-08" in rec.target and rec.triggered_by == "科室用户"

    s2 = _sess()
    bad = _run(s2, boom=RuntimeError("boom"))
    rec2 = next(r for r in s2.by_model[RunRecord] if r.id == bad["run_record_id"])
    assert rec2.status == "failed" and "boom" in rec2.error_message
