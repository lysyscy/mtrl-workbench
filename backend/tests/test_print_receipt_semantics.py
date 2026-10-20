"""打印回执的**三态语义**（`TAIL-46`-①）—— 「说不清」⛔ **不算失败**。

**为什么有这条**（用户 2026-09-18 实测教训，原话要点）：「**假失败比假成功更危险**」——
早先一版因为读不到打印队列就把"没查到作业"判成**失败**，结果纸**照常出来了**、界面却显示失败
⇒ 人会以为没打、**重复再打，白浪费纸**。⇒ 规矩改成：

| 情形 | 语义 | 回执 |
|---|---|---|
| `successful-ok`（作业被接收，但本进程**不轮询**作业状态 ⇒ 说不清"打完没有"） | **已投递（未核实）** | `ok=True, unverified=True`，**不算失败** |
| 明确错误（连不上 / 非 IPP 响应 / IPP 报 4xx-5xx） | **失败** | `ok=False` |

⚠️ 本文件**不连打印机、不连 i8**：`httpx.post` 用桩打掉。
⚠️ **判据点**：打印这一族的新加点属**扩范围**（且打印这条链路的判据主人待核）⇒ 本文件一律 `@acc()` **显式不绑定**。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.errors import MustReportError
from app.mod03_notice import service as S
from app.mod03_notice.print import ipp

from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛


class _Resp:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code


def _ok_ipp_response(status: int = 0) -> bytes:
    """隔离打印机响应，成功码取自IPP规范。"""
    return b"\x02\x00" + status.to_bytes(2, "big") + b"\x03"


# ------------------------------------------------------------------ 投递实现（ipp）


@pytest.mark.parametrize("status", [0x0000, 0x0001, 0x0002])
def test_成功接收的作业算已投递未核实而不是已完成也不失败(monkeypatch, status):
    """⭐ IPP 的 `successful-ok` = **作业被接收**；本实现不轮询作业状态 ⇒ **说不清"打完没有"**
    ⇒ 返回一句说明（⛔ 不许说成"已完成"＝假成功，⛔ 更不许说成"失败"＝假失败）。"""
    monkeypatch.setattr(ipp.httpx, "post", lambda *a, **k: _Resp(_ok_ipp_response(status)))
    note = ipp.send_pdf(b"%PDF-1.4 x", "ipp://10.0.0.1")
    assert isinstance(note, str) and note, "成功的作业也要回一句『已投递但未核实』的说明"
    assert "已投递" in note and "未核实" in note
    assert "失败" not in note.replace("假失败", ""), "⛔ 不许把『说不清』写成失败"
    assert "别重打" in note, "要明确叫人**别重复打印**"
    if status:
        assert "属性" in note, "属性调整应提示核对出纸效果"


def test_明确错误才算失败(monkeypatch):
    """明确错误 ⇒ **仍然抛**（001-08「显式报错、不静默丢弃」这条口径不动）。"""
    def _boom(*a, **k):
        raise ipp.httpx.ConnectError("连不上")

    monkeypatch.setattr(ipp.httpx, "post", _boom)
    with pytest.raises(MustReportError) as e:
        ipp.send_pdf(b"%PDF-1.4 x", "ipp://10.0.0.1")
    assert "出纸失败" in str(e.value)

    monkeypatch.setattr(ipp.httpx, "post", lambda *a, **k: _Resp(b"\x00"))     # 非 IPP 响应
    with pytest.raises(MustReportError):
        ipp.send_pdf(b"%PDF-1.4 x", "ipp://10.0.0.1")

    monkeypatch.setattr(ipp.httpx, "post",
                        lambda *a, **k: _Resp(b"\x02\x00\x04\x00" + b"\x03"))  # 0x0400 报文被拒
    with pytest.raises(MustReportError) as e2:
        ipp.send_pdf(b"%PDF-1.4 x", "ipp://10.0.0.1")
    assert "0x0400" in str(e2.value), "打印机自报的状态码要带出来（现场才查得下去）"


# ------------------------------------------------------------------ 编排（service）


def _run(monkeypatch, dispatch):
    """跑一次 `run_batch`（渲染/版式全打桩 ⇒ **不连库、不连 i8、不连打印机**）。"""
    monkeypatch.setattr(S, "render_notice_html", lambda *a, **k: "<html/>")
    notice = SimpleNamespace(id=7, bill_no="FKTZS-1", bill_type="t")
    return S.run_batch(
        [notice],
        mode=S.MODE_PRINT,
        # ⚠️ 两个取数件要的是**带 `.fetch` 的对象**（生产上分别是 `DesignFetcher` / `NoticeDetailFetcher`）
        design_fetcher=SimpleNamespace(fetch=lambda bt: SimpleNamespace(tpl=None)),
        detail_fetcher=SimpleNamespace(fetch=lambda *a, **k: None),
        signature_store=None,
        render_pdf=lambda html: b"%PDF-1.4 x",      # ⚠️ `render_pdf` 是**入参**（不是模块属性）⇒ 直接给桩
        dispatch_pdf=dispatch,
    )


def test_投递说明进回执且不算失败(monkeypatch):
    """⭐ 投递实现返回一句 ⇒ `ok=True, unverified=True, reason=那句`（**新第三态**）。"""
    r = _run(monkeypatch, lambda pdf: "已投递（未核实）")
    o = r.outcomes[0]
    assert o.ok is True, "『说不清』⛔ 不是失败"
    assert o.unverified is True and o.reason == "已投递（未核实）"
    assert len(r.success) == 1, "它算**成功**（`success` 集合里）"


def test_已核实与真失败两态不受影响(monkeypatch):
    """空串 = 已核实（`unverified=False`）；抛异常 = 失败（`ok=False`，⛔ 且不是 unverified）。"""
    o = _run(monkeypatch, lambda pdf: "").outcomes[0]
    assert o.ok is True and o.unverified is False and o.reason == ""

    def _boom(pdf):
        raise MustReportError("出纸失败：打印机返回 IPP 状态码 0x0400")

    o2 = _run(monkeypatch, _boom).outcomes[0]
    assert o2.ok is False and o2.unverified is False, "失败就是失败，⛔ 别混进『未核实』"
    assert "出纸失败" in o2.reason


# ------------------------------------------------------------------ 壳侧回执


def test_壳把已投递未核实单独说出来且不并进失败():
    """⛔ 壳里不许把"已投递未核实"并进"失败"（那正是"假失败"的来源）。"""
    body = SHELL[SHELL.index("async function m03RunBatch("):]
    body = body[:body.index("async function m03PrinterOpen(")]
    assert "x.ok && x.unverified" in body, "要单独认出『已投递未核实』"
    assert "已投递但未核实" in body and "别重复打印" in body, "要单独说出来，并叫用户去看打印机"
    assert "别重复" in body, "⛔ 不并进失败"
