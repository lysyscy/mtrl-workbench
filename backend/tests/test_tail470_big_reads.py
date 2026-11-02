"""`TAIL-470` 月度会大表读取提速的具名检查（离线：只跑真实装配代码，连内存桩）。

钉三件事，都是这次改动的**意图**本身（⛔ 不钉"恰好也对的结果"）：
- `big_service._mech_amounts` 只要机械 6 列**原值** ⇒ 必须走 `load_mech(..., with_sources=False)`，
  且取值与完整出口逐仓逐月一致（来源/签名是对本表无用的整包副本，不参与任何列）。
- `build_big_data` 把**它读到的那份**手填历史一并发出来 ⇒ 页面出参不再需要第二遍全表读。
- `api_big` 的 `manual` 与行内带入**同源**（同一份 `{年月: {仓库: {key: 值}}}`），
  且整表响应字段一项未减（旧完整契约保留）。
"""

from __future__ import annotations

from unittest.mock import patch

from starlette.requests import Request

from app.mod07_setl import api
from app.mod07_setl import big_domain as B
from app.mod07_setl import big_repository as R
from app.mod07_setl import big_service as S
from tests.m07_big_helpers import dataset
from tests.m08_helpers import FakeSession

YM = "2026-08"


def _session() -> FakeSession:
    return FakeSession(dataset())


def _expected_mech(rows: list[dict]) -> dict:
    """独立复算：`{仓库: {月份: [mech_0..5]}}`。"""
    out: dict[str, dict[str, list]] = {}
    for row in rows:
        wh, ym = str(row.get("warehouse") or ""), str(row.get("ym") or "")
        if wh and ym:
            out.setdefault(wh, {})[ym] = [row.get(f"mech_{i}") for i in range(6)]
    return out


def test_机械取数只要原值且与完整出口同值():
    s = _session()
    calls: list[dict] = []
    original = S.P6S.load_mech

    def counted(*args, **kw):
        calls.append(dict(kw))
        return original(*args, **kw)

    with patch.object(S.P6S, "load_mech", counted):
        got = S._mech_amounts(s)
    assert calls == [{"with_sources": False}], f"大表仍要了整包来源/签名：{calls}"
    assert got == _expected_mech(original(s)), "原值口径与完整出口不一致"


def test_构建结果带手填历史且与库内同值():
    s = _session()
    data = S.build_big_data(s, {"month": YM})
    assert "manual" in data, "装配结果没带手填历史 ⇒ 调用方只能再读一遍全表"
    assert data["manual"] == R.load_manual(s)


def test_页面出参手填历史只读一次且字段不减少(monkeypatch):
    s = _session()
    reads: list[int] = []
    original = R.load_manual

    def counted(session):
        reads.append(1)
        return original(session)

    # 两处绑定分别打点：`big_service` 走 `R.load_manual`，`api` 自己 `from ... import load_manual`
    monkeypatch.setattr(S.R, "load_manual", counted)
    monkeypatch.setattr(api, "load_manual", counted)
    monkeypatch.setattr(api, "session_scope", _scope(s))
    body = api.api_big(Request({"type": "http", "query_string": f"period={YM}".encode()}))

    assert len(reads) == 1, f"一次读取里全表手填被取了 {len(reads)} 遍"
    assert body["manual"] == {
        str(ym): {str(wh): {k: api._s(v) for k, v in (keys or {}).items()}
                  for wh, keys in (by_wh or {}).items()}
        for ym, by_wh in original(s).items()
    }
    assert set(body) == {"month", "selected", "selection", "candidates", "manual", "manual_keys",
                         "manual_fmts", "rows", "totals", "mat_available", "empty_text"}
    # 行内带入仍按本月/历史月份给值 + 来源月（§5.7.1 的 `is not None` 判据不变）
    for row in body["rows"]:
        for key in B.BIG_MANUAL_KEYS:
            cell = row["manual"][key]
            assert isinstance(cell, dict) and "value" in cell and "from" in cell
    assert [row["warehouse"] for row in body["rows"]] == list(body["selected"])
    # 金额出字符串（`numeric(18,2)` 精度保护）：自动列仍是同一份提取合计
    sums = {row["warehouse"]: row["auto"]["hw_cum"] for row in body["rows"]}
    assert sums["甲仓"] == "600.00", "自动列取值被改动（应为同一份提取合计）"


def _scope(session):
    from contextlib import contextmanager

    @contextmanager
    def borrowed():
        yield session

    return borrowed
