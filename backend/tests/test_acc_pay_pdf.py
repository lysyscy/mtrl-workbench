"""`ACC-PAY-PDF-001`（只导出 PDF）7 个判据点的验收断言。

ℹ️ **2026-09-15 断言载体迁移**：`run_batch` 渲染改走**模板驱动**（新增 `detail_fetcher` /
   `signature_store` 两个必需依赖）；本条用例里只有 `001-07` 与渲染内容有关，其余都是编排 / 产物层面
   —— **判据语义未改**，仅补上新增依赖并改用模板输入。
"""

from __future__ import annotations

import shutil

from app.core.config import get_settings
from app.core.errors import MustReportError
from app.mod03_notice.print.template import PrintTemplate
from app.mod03_notice.service import MODE_PDF, MODE_PRINT, _new_batch_dir, run_batch
from tests.acc_plugin import acc
from tests.m03_helpers import (
    DispatchSpy,
    FakeDesignFetcher,
    FakeDetailFetcher,
    FakeSignatureStore,
    RenderSpy,
    field_cell,
    make_notice,
    template,
    text_cell,
)


def _simple_design() -> PrintTemplate:
    """最简版式（无签名格 ⇒ 不触发签名报警），供纯编排类断言使用。"""
    return template([text_cell(0, 0, "I8-NATIVE"), field_cell(1, 0, "项目名称")], cols=1, rows=2)


def _run(notices, mode, *, render=None, dispatch=None, batch_dir=None, fail_on=None, detail=None):
    return run_batch(
        notices,
        mode=mode,
        design_fetcher=FakeDesignFetcher(
            {"material": _simple_design(), "mechanical": _simple_design()}, fail_on=fail_on
        ),
        detail_fetcher=detail or FakeDetailFetcher(),
        signature_store=FakeSignatureStore(),
        render_pdf=render or RenderSpy(),
        dispatch_pdf=dispatch,
        batch_dir=batch_dir,
    )


def _executor_factory(notices):
    def _executor(ids: list[int], mode: str):
        return _run(
            [n for n in notices if n.id in ids],
            mode,
            render=RenderSpy(),
            dispatch=(DispatchSpy() if mode == MODE_PRINT else None),
        )

    return _executor


# ------------------------------------------------------------------ 001-01


@acc("ACC-PAY-PDF-001", "001-01")
def test_与批量打印共用同一次勾选():
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.mod03_notice.router import get_batch_executor

    notices = [make_notice(1, "PN-1", "material"), make_notice(2, "PN-2", "mechanical")]
    app = create_app()
    app.dependency_overrides[get_batch_executor] = lambda: _executor_factory(notices)
    client = TestClient(app)

    selection = [1, 2]  # 同一次勾选
    printed = client.post("/api/m03/batch", json={"ids": selection, "mode": "print"})
    exported = client.post("/api/m03/batch", json={"ids": selection, "mode": "pdf"})
    assert printed.status_code == 200 and exported.status_code == 200
    # 两条入口吃同一份勾选（无需重新选一遍）
    assert printed.json()["total"] == exported.json()["total"] == 2


# ------------------------------------------------------------------ 001-02


@acc("ACC-PAY-PDF-001", "001-02")
def test_只渲染落盘不触发投递(tmp_path):
    dispatch = DispatchSpy()
    notices = [make_notice(1, "PN-1", "material"), make_notice(2, "PN-2", "material")]
    result = _run(
        notices,
        MODE_PDF,
        render=RenderSpy(),
        dispatch=dispatch,  # 即便传入投递器，PDF 模式也绝不调用
        batch_dir=tmp_path,
    )
    assert dispatch.calls == []
    assert len(result.success) == 2


# ------------------------------------------------------------------ 001-03


@acc("ACC-PAY-PDF-001", "001-03")
def test_产物落在约定目录且为绝对路径():
    root = get_settings().pdf_export_path.resolve()
    assert str(_new_batch_dir().resolve()).startswith(str(root))  # 约定产物目录 artifacts/pdf/<批次时间戳>/

    created: list[str] = []
    try:
        result = _run([make_notice(1, "PN-1", "material")], MODE_PDF, render=RenderSpy())
        created.append(result.batch_dir)
        out = result.success[0]
        assert result.batch_dir.startswith(str(root))       # 绝对路径
        assert out.pdf_path.startswith(str(root))           # 绝对路径
        from pathlib import Path

        assert Path(out.pdf_path).is_file()
    finally:
        for d in created:
            shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------ 001-04


@acc("ACC-PAY-PDF-001", "001-04")
def test_产物提供访问入口():
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.mod03_notice.router import get_batch_executor

    notices = [make_notice(1, "PN-DL", "material")]
    created: list[str] = []

    def _executor(ids: list[int], mode: str):
        result = _run([n for n in notices if n.id in ids], mode, render=RenderSpy())
        if result.batch_dir:
            created.append(result.batch_dir)
        return result

    app = create_app()
    app.dependency_overrides[get_batch_executor] = lambda: _executor
    client = TestClient(app)

    try:
        res = client.post("/api/m03/batch", json={"ids": [1], "mode": "pdf"})
        assert res.status_code == 200, res.text
        body = res.json()
        url = body["items"][0]["download_url"]
        assert url  # 界面可拿到下载入口
        dl = client.get(url)
        assert dl.status_code == 200
        assert dl.headers["content-type"].startswith("application/pdf")
        assert dl.content.startswith(b"%PDF")
    finally:
        for d in created:
            shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------ 001-05


@acc("ACC-PAY-PDF-001", "001-05")
def test_取不到版式或渲染失败须显式报错(tmp_path):
    # 渲染失败 ⇒ 该单记"未出 + 原因"，不产空白件、不静默跳过
    render = RenderSpy(fail=MustReportError("PDF 渲染失败：测试注入"))
    notices = [make_notice(1, "PN-1", "material"), make_notice(2, "PN-2", "material")]
    result = _run(notices, MODE_PDF, render=render, batch_dir=tmp_path)
    assert len(result.failed) == 2
    assert all("渲染失败" in o.reason for o in result.failed)
    assert list(tmp_path.iterdir()) == []  # 未产出任何空白件


# ------------------------------------------------------------------ 001-06


@acc("ACC-PAY-PDF-001", "001-06")
def test_批内未产出须列明未出单号():
    fail = {"mechanical": MustReportError("取不到单据类型「mechanical」对应的版式")}
    notices = [make_notice(1, "PN-1", "material"), make_notice(2, "PN-2", "mechanical")]
    result = _run(notices, MODE_PDF, render=RenderSpy(), fail_on=fail)
    assert result.unprinted_bill_nos == ["PN-2"]


# ------------------------------------------------------------------ 001-07


@acc("ACC-PAY-PDF-001", "001-07")
def test_零值金额格留空():
    tpl = template([field_cell(0, 0, "本次结算金额"), field_cell(0, 1, "计划总额")], cols=2, rows=1)
    render = RenderSpy()
    result = run_batch(
        [make_notice(1, "PN-1", "material")],
        mode=MODE_PDF,
        design_fetcher=FakeDesignFetcher({"material": tpl}),
        detail_fetcher=FakeDetailFetcher(info={"ApplyAmt": 88.0, "ApproveAmt": 0}),
        signature_store=FakeSignatureStore(),
        render_pdf=render,
    )
    assert result.success[0].ok
    assert "0.00" not in render.htmls[0]      # 经 PDF 出口的产出同样零值留空
    assert "88.00" in render.htmls[0]
