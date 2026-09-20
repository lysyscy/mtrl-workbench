"""`ACC-PAY-PDF-001`（只导出 PDF）7 个判据点的验收断言。

ℹ️ **2026-09-15 断言载体迁移**：`run_batch` 渲染改走**模板驱动**（新增 `detail_fetcher` /
   `signature_store` 两个必需依赖）；本条用例里只有 `001-07` 与渲染内容有关，其余都是编排 / 产物层面
   —— **判据语义未改**，仅补上新增依赖并改用模板输入。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import MustReportError
from app.mod03_notice import pdf_cache as cache
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
def test_产物不在本机留文件_直接交浏览器下载():
    """⭐ 口径 **2026-09-20 变更**（用户原文：「如果**导出**的话，**换成浏览器下载**吧」）。

    ⚠️ 旧 claim 是「产物落在**约定的产物目录**内，且界面**显示产物绝对路径**」—— **已被推翻**。
       实测那两个毛病：① 本机**越攒越多**（09-15 起已 **884 个 / 7.7MB**）；
       ② 那条路径**壳里压根没用**（`m03RunBatch` 从没读过 `download_url`）
          ⇒ 用户看到"导出完成"后，只能**自己去翻目录**。
    ⇒ 新口径 = **不落盘**：渲染出的字节只在服务端停一下（`pdf_cache`），
      由 `GET /api/m03/pdf/{token}` **流给浏览器**（单张 = PDF / 多张 = 打包 zip）。
    """
    cache.clear()
    result = _run([make_notice(1, "PN-1", "material")], MODE_PDF, render=RenderSpy())

    # ① **本机没有多出任何东西** —— 没传 `batch_dir` ⇒ `batch_dir` 空（就是"没落盘"的机器判据）
    assert result.batch_dir == "", "导出口径已变：**不再落盘**（见本用例 claim）"

    # ② 收的是**字节**（不是路径）—— 从根上就没有"文件留在本机"这回事
    assert [name for name, _ in result.files] == ["PN-1.pdf"]
    assert result.files[0][1].startswith(b"%PDF"), "收的必须是 PDF 字节"

    # ③ 结果里的 `pdf_path` 只是**文件名**（zip 条目名 / 单张下载名）——
    #    ⛔ 不许再是个**存在的本机路径**（那正是被推翻的那条口径）
    out = result.success[0]
    assert not Path(out.pdf_path).is_absolute(), "⛔ 不许再给本机绝对路径"
    assert not Path(out.pdf_path).exists(), "⛔ 本机不许出现这个文件"
    cache.clear()


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


# ---------------------------------------------------------------- 2026-09-20 新形态
# ------------------------------------------------------------------ 实现层自检（⛔ 不绑判据点）


@acc()
def test_多张打包成zip_单张直出PDF_过期给显式404():
    """`PDF-001-04` 的 **2026-09-20 形态**（导出改浏览器下载）—— 三条新路。

    ⚠️ **多张只能打包**：浏览器**不允许一次响应触发 N 个下载** ⇒ zip 是唯一的办法。
    ⚠️ **取不到（过期 / 服务重启过 / 伪造 token）必须 404 ＋ 中文**，
       ⛔ 绝不静默回一个空 zip —— 那会让人以为"导出成功但里面没东西"（最难查的一类）。
    ⚠️ 中文文件名走 **RFC 5987**（`filename*=UTF-8''…`）—— 裸 `filename=` 遇中文会乱码。
    """
    import io
    import zipfile
    from urllib.parse import quote

    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.mod03_notice import pdf_cache

    client = TestClient(create_app())
    pdf_cache.clear()
    try:
        # ① 多张 ⇒ **一个 zip**，条目名就是各自的 `单号.pdf`
        token = pdf_cache.put([("A.pdf", b"%PDF-1.4 a"), ("B.pdf", b"%PDF-1.4 b")])
        res = client.get(f"/api/m03/pdf/{token}")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/zip"
        assert "attachment" in res.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            assert sorted(zf.namelist()) == ["A.pdf", "B.pdf"]
            assert zf.read("A.pdf").startswith(b"%PDF")

        # ② 单张 ⇒ 直接给那个 PDF（不套一层 zip），文件名由后端带出
        one = pdf_cache.put([("通知书 甲.pdf", b"%PDF-1.4 only")])
        res1 = client.get(f"/api/m03/pdf/{one}")
        assert res1.headers["content-type"] == "application/pdf"
        assert res1.content.startswith(b"%PDF")
        assert quote("通知书 甲.pdf") in res1.headers["content-disposition"]
        assert res1.headers["x-export-filename"] == quote("通知书 甲.pdf")

        # ③ 取不到 ⇒ **404 ＋ 中文真因**（⛔ 不是空文件、⛔ 不是空 zip）
        gone = client.get("/api/m03/pdf/不存在的token")
        assert gone.status_code == 404
        assert "过期" in gone.json()["detail"], "要说清是过期、并告诉人重新点一次"

        # ④ 取用是**幂等**的（下载中断可以重试）—— ⛔ 不搞"取一次就销毁"
        assert client.get(f"/api/m03/pdf/{one}").status_code == 200
    finally:
        pdf_cache.clear()
