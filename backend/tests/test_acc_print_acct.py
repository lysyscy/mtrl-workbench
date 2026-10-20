"""`TAIL-61`：明细取数**空结果要再确认一次**（与列表抓取 / 流程历史同一条处理）。

⭐ 2026-09-21 诊断「收款账号印空」时顺带查出：全量 355 张里实取到 **2 张明细 0 行**
（`FKTZS2026090631` / `FKTZS2026091471`）—— i8 会偶发返回"有效但空"的响应 ⇒
**收款账号/银行/明细表整块静默丢失**，而收款单位靠抬头兜底照旧"正常" ⇒ 极难发现。
（不连真 i8；用桩客户端，`monkeypatch` 掉 `sleep`。）
"""

from __future__ import annotations

import app.mod02_i8.notice_source as ns
from app.mod02_i8.notice_source import NoticeDetailFetcher


class _StubClient:
    """按预设序列回包的桩（只实现 `post_json`，并记下调用次数）。"""

    def __init__(self, payloads: list[object]) -> None:
        self._payloads = list(payloads)
        self.calls = 0

    def post_json(self, path: str, **kwargs: object) -> object:
        self.calls += 1
        return self._payloads.pop(0)


def test_明细回空会再确认一次_重试取到就用(monkeypatch):
    """首次回空 ⇒ 重试一次；重试有数 ⇒ **用重试的结果**（旧行为会静默返回空）。"""
    monkeypatch.setattr(ns.time, "sleep", lambda *_: None)
    stub = _StubClient([{"Record": []}, {"Record": [{"RecAccNo": "300602200902456652"}]}])
    rows = NoticeDetailFetcher(stub).fetch_detail("3700000000008168")
    assert [r.get("RecAccNo") for r in rows] == ["300602200902456652"]
    assert stub.calls == 2                       # 两次请求 ⇒ 确认过一次


def test_明细确认真空后接受空_不死循环(monkeypatch):
    """两次都空 ⇒ **接受空**（真有单据没有明细）并停住 —— ⛔ 不能无限重试。"""
    monkeypatch.setattr(ns.time, "sleep", lambda *_: None)
    stub = _StubClient([{"Record": []}, {"Record": []}])
    assert NoticeDetailFetcher(stub).fetch_detail("ph") == []
    assert stub.calls == 2                       # 确认一次后停


def test_明细正常回包不触发重试(monkeypatch):
    """有数 ⇒ **只调一次**（⛔ 别把"确认一次"做成"每次都取两遍"）。"""
    monkeypatch.setattr(ns.time, "sleep", lambda *_: None)
    stub = _StubClient([{"Record": [{"RecAccNo": "102902"}]}])
    rows = NoticeDetailFetcher(stub).fetch_detail("ph")
    assert [r.get("RecAccNo") for r in rows] == ["102902"]
    assert stub.calls == 1
