"""`ACC-PAY-PRINT-001`（付款通知书批量打印）10 个判据点的验收断言。

判据全文见 `PRD/验收/验收基线.json`（只读快照）。
⚠️ 全部离线：不连库 / 不启浏览器 / 不碰打印机（依赖注入桩）。

ℹ️ **2026-09-15 断言载体迁移**（模板驱动链路）：`001-04/05/06/10` 原来打在旧的
   「HTML 占位符替换 + `<span class="sign-slot">`」实现上 —— 那套假设已被**真机证伪**
   （i8 返回的是版式模板 JSON，里面没有 HTML）。现改为打在**真实模板形态**上：
   签名格 = `cellData.otherShowType=image` ＋ `dataFilter` 的「办理节点」。
   **判据语义一字未改**（见每条的注释与判据原文）。
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import get_settings
from app.core.errors import MustReportError, NotConfiguredError
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.print import ipp
from app.mod03_notice.print.design import DesignFetcher
from app.mod03_notice.print.signatures import check_signature_coverage
from app.mod03_notice.print.template import PrintTemplate
from app.mod03_notice.service import MODE_PDF, MODE_PRINT, run_batch
from tests.acc_plugin import acc
from tests.m03_helpers import (
    DispatchSpy,
    FakeDesignFetcher,
    FakeDetailFetcher,
    FakeSignatureStore,
    RenderSpy,
    field_cell,
    make_notice,
    sign_cell,
    template,
    text_cell,
)

# ---------------------------------------------------------------- 版式与编排助手


def _simple_design(marker: str = "I8-DESIGN") -> PrintTemplate:
    """一张"来自 i8"的最简版式：一个静态标记格 ＋ 一个项目名称格（无签名格）。"""
    return template([text_cell(0, 0, marker), field_cell(1, 0, "项目名称")], cols=1, rows=2)


def _design_payload() -> dict:
    """`getPrintDesign` 的**真实响应形态**（2026-09-15 真机复核）：模板在 `Data` 里、且是 JSON 串。"""
    sheet = {
        "sheetName": "表1",
        "cells": [text_cell(0, 0, "I8-NATIVE")],
        "globalSettings": {"cols": 1, "rows": 1, "widths": {"0": 100}, "heights": {}},
    }
    setting = [{"printConfig": {"page": {}, "margin": {"top": 5, "left": 5, "right": 5, "down": 5}}}]
    return {
        "Status": "success",
        "Data": {
            "printId": "some-id",
            "printName": "测试版式",
            "printSchema": json.dumps([sheet], ensure_ascii=False),
            "printSetting": json.dumps(setting, ensure_ascii=False),
        },
    }


def _run(
    notices,
    mode,
    designs,
    *,
    detail=None,
    store=None,
    render=None,
    dispatch=None,
    batch_dir=None,
    fail_on=None,
):
    """跑一批（默认注入了空详情 / 空签名桩，省去每个用例重复拼装）。"""
    return run_batch(
        notices,
        mode=mode,
        design_fetcher=FakeDesignFetcher(designs, fail_on=fail_on),
        detail_fetcher=detail or FakeDetailFetcher(),
        signature_store=store or FakeSignatureStore(),
        render_pdf=render or RenderSpy(),
        dispatch_pdf=dispatch,
        batch_dir=batch_dir,
    )


# ------------------------------------------------------------------ 001-01


@acc("ACC-PAY-PRINT-001", "001-01")
def test_产出版式取自i8不自存不自绘(tmp_path):
    """判据：产出版式取自 i8 原生版式；系统内不自存、不自绘版式。"""
    render = RenderSpy()
    data = FakeDetailFetcher(info={"PhidPc_EXName": "某工程项目"})

    _run(
        [make_notice(1, "PN-001", "material")],
        MODE_PDF,
        {"material": _simple_design("I8-DESIGN-MARKER")},
        detail=data,
        render=render,
        batch_dir=tmp_path,
    )

    # 产出内容 = i8 版式（含其静态文本/几何）＋ 注入数据（不是本地自绘的模板）
    assert "I8-DESIGN-MARKER" in render.htmls[0]
    assert "某工程项目" in render.htmls[0]
    # 系统内不自存版式：单据表没有任何存放版式/模板的列
    cols = set(PaymentNotice.__table__.columns.keys())
    assert not (cols & {"html", "design", "template", "body", "layout"})


# ------------------------------------------------------------------ 001-02


class _StubSettings:
    # ⚠️ 2026-09-16 起：i8 端点由「服务地址 ＋ 常量路径」推导（§7.8）
    # ⇒ 桩只需给 `i8_base_url`（旧的 `i8_print_design_url` 已不再被读）
    i8_base_url = "http://stub"

    def print_id_for_bill_type(self, bill_type: str) -> str:
        return "MECH-PID" if bill_type == "mechanical" else "MAT-PID"


class _RecordingClient:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.calls: list[tuple] = []

    def get_json(self, path, params=None, **kw):
        self.calls.append((path, dict(params or {})))
        return self._payload


@acc("ACC-PAY-PRINT-001", "001-02")
def test_单据按类型走对应版式(monkeypatch):
    """判据：单据按类型走对应版式（现有两类分流）。"""
    monkeypatch.setattr("app.mod03_notice.print.design.get_settings", lambda: _StubSettings())

    client = _RecordingClient(_design_payload())
    fetcher = DesignFetcher(client)  # type: ignore[arg-type]

    mech = fetcher.fetch("mechanical")
    mat = fetcher.fetch("material")

    assert client.calls[0][1]["printId"] == "MECH-PID"
    assert client.calls[1][1]["printId"] == "MAT-PID"
    assert mech.print_id != mat.print_id
    assert mech.tpl.print_name == "测试版式"        # 取回的是**模板**（不是 HTML）

    # 未配置 printId ⇒ 显式报错（不得静默用同一个版式）
    # ⚠️ **必须显式把配置清空后再断言** —— 这条不能依赖 `.env` 的真实取值，
    #    否则本机一旦填入真实 printId（2026-09-15 起已填）这条就变成"假绿/假红"。
    monkeypatch.setenv("I8_PRINT_ID_MECHANICAL", "")
    monkeypatch.setenv("I8_PRINT_ID_MATERIAL", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(NotConfiguredError):
            get_settings().print_id_for_bill_type("mechanical")
    finally:
        get_settings.cache_clear()


# ------------------------------------------------------------------ 001-03


@acc("ACC-PAY-PRINT-001", "001-03")
def test_取不到版式须显式报错不产空白件(tmp_path):
    """判据：取不到对应版式时须显式报错，不得静默产出空白件。"""
    # ① 取版式层：空模板 ⇒ MustReportError
    class _EmptyClient:
        def get_json(self, path, params=None, **kw):
            return {"Status": "success", "Data": {}}

    import app.mod03_notice.print.design as design_mod

    orig = design_mod.get_settings
    design_mod.get_settings = lambda: _StubSettings()
    try:
        with pytest.raises(MustReportError):
            DesignFetcher(_EmptyClient()).fetch("material")  # type: ignore[arg-type]
    finally:
        design_mod.get_settings = orig

    # ② 编排层：某类型取不到版式 ⇒ 该单记"未出 + 原因"，且不产出文件
    fail = {"mechanical": MustReportError("取不到单据类型「mechanical」对应的版式")}
    render = RenderSpy()
    notices = [
        make_notice(1, "PN-A", "material"),
        make_notice(2, "PN-B", "mechanical"),
    ]
    result = _run(
        notices,
        MODE_PDF,
        {"material": _simple_design()},
        fail_on=fail,
        render=render,
        batch_dir=tmp_path,
    )
    failed = result.failed
    assert [o.bill_no for o in failed] == ["PN-B"]
    assert "版式" in failed[0].reason
    # 未产出者没有落文件（未静默产空白件）
    assert not (tmp_path / "PN-B.pdf").exists()


# ------------------------------------------------------------------ 001-04 / 001-05 / 001-06


def _sign_design() -> PrintTemplate:
    """一张带两个签名槽位的版式（槽位名 = 模板里 `dataFilter` 的「办理节点」）。"""
    return template(
        [text_cell(0, 0, "签字区"), sign_cell(1, 0, "项目经理"), sign_cell(1, 1, "财务审核")],
        cols=2,
        rows=3,
    )


SIG_URI = "data:image/png;base64,PM"


@acc("ACC-PAY-PRINT-001", "001-04")
def test_签名按审批节点名绑定槽位(tmp_path):
    """判据：签名按审批节点名绑定到版式槽位。"""
    render = RenderSpy()
    result = _run(
        [make_notice(1, "PN-1")],
        MODE_PDF,
        {"material": _sign_design()},
        detail=FakeDetailFetcher(flow=[{"task_des": "项目经理", "signature": "/sig/pm.png"}]),
        store=FakeSignatureStore({"/sig/pm.png": SIG_URI}),
        render=render,
        batch_dir=tmp_path,
    )
    assert result.success, [o.reason for o in result.failed]
    # 签名落在"项目经理"这个槽位里（按节点名绑定）——渲染成该格的图片
    assert f'<img class="sig" src="{SIG_URI}">' in render.htmls[0]


@acc("ACC-PAY-PRINT-001", "001-05")
def test_流程未走到节点则槽位留空且不报错(tmp_path):
    """判据：版式有槽位、流程未走到该节点，则槽位留空 —— 正确行为，不得报错、不得补占位图。"""
    render = RenderSpy()
    # "财务审核"槽位存在，但流程**未走到**（不在流程数据里）⇒ 留空、不报错
    result = _run(
        [make_notice(1, "PN-1")],
        MODE_PDF,
        {"material": _sign_design()},
        detail=FakeDetailFetcher(
            flow=[
                {"task_des": "流程发起", "signature": ""},
                {"task_des": "项目经理", "signature": "/sig/pm.png"},
            ]
        ),
        store=FakeSignatureStore({"/sig/pm.png": SIG_URI}),
        render=render,
        batch_dir=tmp_path,
    )
    assert result.success, [o.reason for o in result.failed]   # 未走到 ⇒ 不得报错
    # 两个槽位**都确实在版式里**（"财务审核"不是被静默丢掉）
    from app.mod03_notice.print.signatures import signature_slots

    assert signature_slots(_sign_design()) == ["项目经理", "财务审核"]
    html = render.htmls[0]
    assert html.count("<img") == html.count('<img class="sig"') == 1   # 只有"项目经理"命中
    assert SIG_URI in html


@acc("ACC-PAY-PRINT-001", "001-06")
def test_流程有数据却零命中须显式报警(tmp_path):
    """判据：槽位存在且流程有数据、却一个签名都未命中，必须显式报警（禁止静默产出无签名件）。"""
    tpl = _sign_design()
    flow = [{"task_des": "项目经理", "signature": "/sig/pm.png"}]

    # ① 单元层：覆盖度判定必须抛错
    with pytest.raises(MustReportError) as ei:
        check_signature_coverage(tpl, flow, {"/sig/pm.png": ""})
    assert "签名" in str(ei.value)

    # ② 编排层：该单记"未出 + 原因"，且**一个文件都不落**（禁止静默产出无签名件）
    render = RenderSpy()
    result = _run(
        [make_notice(1, "PN-1")],
        MODE_PDF,
        {"material": tpl},
        detail=FakeDetailFetcher(flow=flow),
        store=FakeSignatureStore({}),          # 取图一律失败 ⇒ 命中 0
        render=render,
        batch_dir=tmp_path,
    )
    assert [o.bill_no for o in result.failed] == ["PN-1"]
    assert "签名" in result.failed[0].reason
    assert render.htmls == []                  # 还没进渲染就被拦下
    assert not (tmp_path / "PN-1.pdf").exists()


# ------------------------------------------------------------------ 001-07


@acc("ACC-PAY-PRINT-001", "001-07")
def test_批内未产出须列明未出单号():
    """判据：批量中任一单据未产出，结束时须显式列明未出单号；禁止静默漏单。"""
    fail = {"material": MustReportError("取不到单据类型「material」对应的版式")}
    notices = [
        make_notice(1, "PN-OK1", "mechanical"),
        make_notice(2, "PN-BAD", "material"),
        make_notice(3, "PN-OK2", "mechanical"),
    ]
    result = _run(
        notices,
        MODE_PRINT,
        {"mechanical": _simple_design()},
        fail_on=fail,
        render=RenderSpy(),
        dispatch=DispatchSpy(),
    )
    assert result.unprinted_bill_nos == ["PN-BAD"]
    assert len(result.success) == 2


# ------------------------------------------------------------------ 001-08


@acc("ACC-PAY-PRINT-001", "001-08")
def test_出纸失败须显式报出原因(monkeypatch):
    """判据：出纸环节失败须显式报出原因；禁止把整批静默丢弃。"""
    # ① 编排层：第 2 张出纸失败 ⇒ 记为未出、带原因
    dispatch = DispatchSpy(fail_on_call=2)
    notices = [make_notice(1, "PN-1", "material"), make_notice(2, "PN-2", "material")]
    result = _run(
        notices,
        MODE_PRINT,
        {"material": _simple_design()},
        render=RenderSpy(),
        dispatch=dispatch,
    )
    assert [o.bill_no for o in result.failed] == ["PN-2"]
    assert "出纸" in result.failed[0].reason

    # ② 投递层：连不上打印机 ⇒ MustReportError 且带出地址（不静默丢弃整批）
    def _boom(*a, **kw):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(ipp.httpx, "post", _boom)
    with pytest.raises(MustReportError) as ei:
        ipp.send_pdf(b"%PDF", printer_uri="ipp://192.168.5.248")
    assert "192.168.5.248" in str(ei.value)


# ------------------------------------------------------------------ 001-09


@acc("ACC-PAY-PRINT-001", "001-09")
def test_系统内勾选_单选多选端到端():
    """判据：待打印单据来自系统内勾选（不依赖外部文件或手输清单）；单选与多选均能端到端跑通。"""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.mod03_notice.router import get_batch_executor, get_notice_lister

    notices = [
        make_notice(1, "PN-1", "material"),
        make_notice(2, "PN-2", "mechanical"),
        make_notice(3, "PN-3", "material"),
    ]

    def _executor(ids: list[int], mode: str):
        selected = [n for n in notices if n.id in ids]
        return _run(
            selected,
            mode,
            {"material": _simple_design(), "mechanical": _simple_design()},
            render=RenderSpy(),
            dispatch=(DispatchSpy() if mode == MODE_PRINT else None),
        )

    app = create_app()
    app.dependency_overrides[get_batch_executor] = lambda: _executor
    app.dependency_overrides[get_notice_lister] = lambda: (
        lambda bill_type=None, limit=200: notices
    )
    client = TestClient(app)

    # 勾选来源 = 系统内 id 列表（非文件 / 手输清单）
    single = client.post("/api/m03/batch", json={"ids": [1], "mode": "print"})
    assert single.status_code == 200, single.text
    assert single.json()["total"] == 1 and single.json()["success"] == 1

    multi = client.post("/api/m03/batch", json={"ids": [1, 2, 3], "mode": "print"})
    assert multi.status_code == 200, multi.text
    assert multi.json()["total"] == 3 and multi.json()["success"] == 3


# ------------------------------------------------------------------ 001-10


@acc("ACC-PAY-PRINT-001", "001-10")
def test_零值金额格留空(tmp_path):
    """判据：零值金额格留空（不出现 0.00 占位）。"""
    tpl = template([field_cell(0, 0, "本次结算金额"), field_cell(0, 1, "计划总额")], cols=2, rows=1)
    render = RenderSpy()
    result = _run(
        [make_notice(1, "PN-1")],
        MODE_PDF,
        {"material": tpl},
        detail=FakeDetailFetcher(info={"ApplyAmt": 1234.5, "ApproveAmt": 0}),
        render=render,
        batch_dir=tmp_path,
    )
    assert result.success, [o.reason for o in result.failed]
    html = render.htmls[0]
    assert "0.00" not in html          # 零值留空，不出现 0.00 占位
    assert "1,234.50" in html          # 非零正常出（且为千分位 + 2 位小数）


# ------------------------------------------------------------------ 001-11


def _unrecognised_sign_design() -> PrintTemplate:
    """版式含一个**认不出取人条件**的签名格 —— 与一个正常格**并存**。

    ⚠️ 这正是 2026-09-16 真机踩到的形态：其余签名**都贴上了**，所以"零命中报警"（001-06）**看不见它**。
    """
    bad = {"cellType": "field", "row": 1, "col": 0, "colspan": 1, "className": "htCenter",
           "cellData": {"dataSetId": "3700000000000010", "fieldId": "签名",
                        "otherShowType": "image",
                        "dataFilter": [{"fieldId": "某个未知字段", "value": "核算部部长"}]},
           "cellBorders": {}}
    return template([sign_cell(0, 0, "项目经理"), bad], cols=2, rows=2)


@acc("ACC-PAY-PRINT-001", "001-11")
def test_认不出签名格取人条件须显式报警(tmp_path):
    """判据：版式里有签名格带了「取人条件」、却解析不出该贴谁的签名时，必须显式报警并停单；不得静默留白。"""
    tpl = _unrecognised_sign_design()
    flow = [{"task_des": "项目经理", "signature": "/sig/pm.png"}]

    # ① 单元层：必须抛错（⚠️ 此时"项目经理"是**命中**的 ⇒ 001-06 的零命中判定覆盖不到）
    with pytest.raises(MustReportError) as ei:
        check_signature_coverage(tpl, flow, {"项目经理": SIG_URI})
    msg = str(ei.value)
    assert "取不到审批节点名" in msg and "row1col0" in msg

    # ② 编排层：该单记"未出 + 原因"，且**一个文件都不落**
    render = RenderSpy()
    result = _run(
        [make_notice(1, "PN-1")],
        MODE_PDF,
        {"material": tpl},
        detail=FakeDetailFetcher(flow=flow),
        store=FakeSignatureStore({"/sig/pm.png": SIG_URI}),
        render=render,
        batch_dir=tmp_path,
    )
    assert [o.bill_no for o in result.failed] == ["PN-1"]
    assert "签名" in result.failed[0].reason
    assert render.htmls == []
    assert not (tmp_path / "PN-1.pdf").exists()

    # ③ 反向灵敏度：把那一格换成**正确写法** ⇒ 同一批必须能出（证明拦的是"认不出"，不是"有签名格"）
    ok = template([sign_cell(0, 0, "项目经理"), sign_cell(1, 0, "核算部部长")], cols=2, rows=2)
    render2 = RenderSpy()
    result2 = _run(
        [make_notice(2, "PN-2")],
        MODE_PDF,
        {"material": ok},
        detail=FakeDetailFetcher(flow=flow),
        store=FakeSignatureStore({"/sig/pm.png": SIG_URI}),
        render=render2,
        batch_dir=tmp_path,
    )
    assert result2.success, [o.reason for o in result2.failed]
    assert len(render2.htmls) == 1


# ---------------------------------------------------------------- 出纸报文（真机实测固化 · 不绑定判据点）


@acc()
def test_IPP报文的值标签必须与属性类型一致():
    """⚠️ 2026-09-16 真机固化：`document-format` 的值标签必须是 **`0x49`（mimeMediaType）**。

    误用 `0x44`（那是 `keyword`）⇒ 这台 **RICOH IM 3000 PS3** 直接回 `0x0400 client-error-bad-request`
    （响应仅 115 字节、`status-message` **不指明是哪个属性错了** —— 真机排障耗时就在这）。
    """
    body = ipp._build_print_job("ipp://192.168.5.248:631/ipp/print", b"%PDF-1.4-x")
    # ① document-format：标签 0x49 = mimeMediaType
    assert b"\x49\x00\x0fdocument-format\x00\x0fapplication/pdf" in body
    assert b"\x44\x00\x0fdocument-format" not in body          # ← 曾经的坏写法（0x44 = keyword）
    # ② 其余属性标签逐一对齐（uri / charset / naturalLanguage / nameWithoutLanguage）
    assert b"\x45\x00\x0bprinter-uri" in body
    assert b"\x47\x00\x12attributes-charset" in body
    assert b"\x48\x00\x1battributes-natural-language" in body
    assert b"\x42\x00\x14requesting-user-name" in body
    # ③ 文档紧随 end-of-attributes（0x03）
    assert body.endswith(b"%PDF-1.4-x")


@acc()
def test_出纸失败要带出打印机自报的原因(monkeypatch):
    """001-08 的加强：错误文本必须含打印机自报的 `status-message` —— 只给十六进制码现场无从下手。"""
    def _bad_post(url, **kw):  # noqa: ARG001
        payload = (bytes([0x01, 0x01]) + bytes([0x04, 0x00]) + bytes([0, 0, 0, 1]) + bytes([0x01])
                   + b"\x41\x0estatus-message\x18client-error-bad-request" + bytes([0x03]))
        return httpx.Response(200, content=payload)

    monkeypatch.setattr(ipp.httpx, "post", _bad_post)
    with pytest.raises(MustReportError) as ei:
        ipp.send_pdf(b"%PDF-1.4", printer_uri="ipp://192.168.5.248:631/ipp/print")
    msg = str(ei.value)
    assert "0x0400" in msg and "client-error-bad-request" in msg and "报文被拒" in msg
