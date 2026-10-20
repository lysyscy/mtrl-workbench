"""通用导入 API 面的行为判据（`import_kit.api` · `TAIL-75` B1）。

⭐ 素材按**真文件形态**造（不是随手造的表）：一个工作簿里**第一张是噪声表**（真文件里就是
`计划预收款明细` / `pvOg8w` / `3月底` 这种），目标表在第 2 张；表里混着**未映射列**与**坏值**。

⚠️ 本文件**不连数据库**：`session_scope` 被替换成空上下文（通用层的判据只管"编排与四条硬性"，
落库口径归域内 ⇒ 这里用假钩子记录调用）。
"""

from __future__ import annotations

import io
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.import_kit import api as imp_api
from app.import_kit.mapping import Field, IGNORE
from app.import_kit.profile_store import ProfileStore
from app.import_kit.spec import DomainSpec, Hooks

SPEC = DomainSpec(
    domain="m04", title="付款计划", source_label="项目付款计划",
    fields=(
        Field("pj", "项目", type="text", required=True),
        Field("amt", "该流程金额", aliases=("流程金额",), type="amount", required=True),
        Field("pay_time", "付款时间", type="date"),
        Field("method", "付款方式", type="enum"),
    ),
    note="必须有「项目」与「该流程金额」", keep_note="未采：审批状态",
)


def make_book() -> bytes:
    """造一份**真文件形态**的工作簿：第 1 张是噪声表，第 2 张才是目标表。"""
    wb = Workbook()
    noise = wb.active
    noise.title = "计划预收款明细"
    noise.append(["7月份各项目预收款"])
    noise.append(["序号", "项目名称", "合同额（万元）"])
    noise.append([1, "灵宝二期", 2500])

    ws = wb.create_sheet("材机付款计划明细")
    ws.append(["项目", "该流程金额", "付款时间", "付款方式", "审批状态"])
    ws.append(["灵宝二期", "797,726.5", "2026-09-11", "承兑", "已审批"])
    ws.append(["灵宝二期", "壹拾贰万", "2026-09-11", "承兑", "已审批"])   # 金额坏值
    ws.append(["", "28,922", "2026-09-11", "现金", "已审批"])              # 项目必填为空
    ws.append([None, None, None, None, None])                              # 全空行 ⇒ 跳过
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """假钩子 ＋ 隔离的记忆件 ＋ 不连库的 `session_scope`。"""
    calls: dict = {"commit": [], "rollback": []}
    monkeypatch.setattr(imp_api, "REGISTRY", dict(imp_api.REGISTRY))

    def commit(session, records, mapping_, operator):
        calls["commit"].append({"records": records, "mapping": mapping_, "operator": operator})
        return {"inserted": len(records), "batch": "IMP-TEST-1"}

    def rollback(session, batch, operator):
        calls["rollback"].append(batch)
        return {"revoked": 1, "batch": batch}

    @contextmanager
    def fake_scope():
        yield None

    monkeypatch.setattr(imp_api, "session_scope", fake_scope)
    monkeypatch.setattr(imp_api, "current_operator", lambda: "测试人")
    app = FastAPI()
    app.include_router(imp_api.build_router(SPEC, Hooks(commit=commit, rollback=rollback),
                                            store=ProfileStore(tmp_path / "p.json")))
    tc = TestClient(app)
    tc.calls = calls                                     # type: ignore[attr-defined]
    return tc


def _upload(client, sheet: str = ""):
    return client.post("/api/imp/m04/parse",
                       files={"file": ("计划.xlsx", make_book(),
                                       "application/vnd.openxmlformats-officedocument"
                                       ".spreadsheetml.sheet")},
                       data={"sheet": sheet})


def test_schema_端点给字段契约(client):
    out = client.get("/api/imp/m04/schema").json()
    assert out["ok"] and out["title"] == "付款计划"
    assert out["required"] == ["项目", "该流程金额"]
    assert {f["label"] for f in out["fields"]} >= {"项目", "该流程金额", "付款时间", "付款方式"}


def test_解析_自动挑对工作表并认出列(client):
    """⭐ 真文件形态：第一张 sheet 是噪声 ⇒ 必须挑到**认得出表头**的那张。"""
    out = _upload(client).json()
    assert out["ok"], out
    assert out["sheet"] == "材机付款计划明细" and out["header_row"] == 1
    assert out["sheets"] == ["计划预收款明细", "材机付款计划明细"]
    got = {c["src"]: c for c in out["cols"]}
    assert got["项目"]["field"] == "项目" and got["项目"]["level"] == "auto"
    assert got["该流程金额"]["field"] == "该流程金额"
    # ⚠️ 该列样本里混着坏值（`壹拾贰万`）⇒ 画像只能是「文本」（弱证据）⇒ **不降权**、照常给建议；
    #    坏值本身由**行级问题清单**兜住（`test_预览_…` 那条）—— 两件事各有各的出口，别混。
    assert got["该流程金额"]["level"] in ("auto", "confirm")
    assert got["该流程金额"]["samples"][1] == "壹拾贰万"          # 样本照原样给人看
    # 「审批状态」不是本域字段 ⇒ 不猜、留空（⛔ 不硬凑）
    assert got["审批状态"]["field"] is None and got["审批状态"]["level"] == "blank"
    assert out["memory"] is None                       # 第一次 ⇒ 没有记忆


def test_解析_指定不存在的工作表_要显式报错(client):
    out = _upload(client, sheet="没有这张表").json()
    assert out["ok"] is False and "工作表" in out["message"]


def test_预览_不写库_并把坏值与必填为空列成问题(client):
    parsed = _upload(client).json()
    body = {"token": parsed["token"], "mapping": {"项目": "项目", "该流程金额": "该流程金额",
                                                 "付款时间": "付款时间", "付款方式": "付款方式"}}
    out = client.post("/api/imp/m04/preview", json=body).json()
    assert out["ok"] and out["total"] == 3              # 全空行被跳过
    assert client.calls["commit"] == []                 # ⭐ 预览阶段**一个字节都没写库**
    why = " ".join(p["reason"] for p in out["problems"])
    assert "不是数字" in why and "必填为空" in why
    rows = {p["row"] for p in out["problems"]}
    assert rows == {3, 4}
    assert all("raw" not in r for r in out["preview"])   # 预览不回 raw（界面另取）


def test_确认前一个字节都不写库(client):
    """⭐ 解析 ＋ 预览全程只进 `preview_store`；**域钩子一次都没被调**（真落库只在确认那一步）。"""
    parsed = _upload(client).json()
    assert parsed["ok"] and parsed["token"]
    client.post("/api/imp/m04/preview", json={"token": parsed["token"], "mapping": {"项目": "项目"}})
    assert client.calls["commit"] == [] and client.calls["rollback"] == []


def test_未映射列原样保留_不丢也不报错(client):
    parsed = _upload(client).json()
    body = {"token": parsed["token"], "mapping": {"项目": "项目", "该流程金额": "该流程金额"}}
    client.post("/api/imp/m04/preview", json=body)
    client.post("/api/imp/m04/commit", json=body)
    rec = client.calls["commit"][0]["records"][0]
    assert rec["raw"]["审批状态"] == "已审批"            # ⭐ 原样保留
    assert rec["raw"]["付款方式"] == "承兑"
    assert "审批状态" not in rec                        # ⛔ 不许进正式字段


def test_确认落库_调域钩子并回报告(client):
    parsed = _upload(client).json()
    out = client.post("/api/imp/m04/commit",
                      json={"token": parsed["token"],
                            "mapping": {"项目": "项目", "该流程金额": "该流程金额"}}).json()
    assert out["ok"] and out["report"]["inserted"] == 3
    assert client.calls["commit"][0]["operator"] == "测试人"
    assert "已导入 3 行" in out["message"]


def test_记忆_勾了记住_下次解析就预填(client):
    parsed = _upload(client).json()
    client.post("/api/imp/m04/commit",
                json={"token": parsed["token"], "remember": True,
                      "mapping": {"项目": "项目", "该流程金额": "该流程金额"}})
    again = _upload(client).json()
    mem = again["memory"]
    assert mem and mem["sim"] == 1.0 and "来自记忆" in mem["note"] and "可改" in mem["note"]
    assert mem["mapping"]["项目"] == "项目"


def test_回滚端点_只在域给了钩子时才存在(client):
    assert client.post("/api/imp/m04/rollback", json={"batch": "IMP-TEST-1"}).json()["ok"]
    assert client.calls["rollback"] == ["IMP-TEST-1"]
    app = FastAPI()
    app.include_router(imp_api.build_router(SPEC, Hooks(commit=lambda *a: {})))
    assert TestClient(app).post("/api/imp/m04/rollback", json={}).status_code == 404


def test_预览_过期token要显式报错_不静默当空(client):
    out = client.post("/api/imp/m04/preview", json={"token": "deadbeef"}).json()
    assert out["ok"] is False and "重新上传" in out["message"]


def test_不是Excel_要中文原因且HTTP仍是200(client):
    resp = client.post("/api/imp/m04/parse",
                       files={"file": ("假的.xlsx", b"not an excel", "application/octet-stream")})
    assert resp.status_code == 200                      # ⭐ 恒 200 ＋ ok 标志（既有口径）
    out = resp.json()
    assert out["ok"] is False and "读不成 Excel" in out["message"]


def test_忽略哨兵_显式忽略的列进raw而不是字段(client):
    parsed = _upload(client).json()
    body = {"token": parsed["token"],
            "mapping": {"项目": "项目", "该流程金额": IGNORE, "付款方式": "付款方式"}}
    client.post("/api/imp/m04/commit", json=body)
    rec = client.calls["commit"][0]["records"][0]
    assert "该流程金额" not in rec and rec["raw"]["该流程金额"] == "797,726.5"
