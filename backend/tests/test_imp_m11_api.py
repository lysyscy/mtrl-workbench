"""`m11` 集采台账 · **通用导入面**端到端（`TAIL-75` · `B5b`）—— 第三个真域挂上 `/api/imp/*`。

⭐ 钉三件：
1. **两级表头拼名在通用面上也认得出**（`供应商` › `合同总价` ⇒ `供应商合同总价`）—— 这是真台账的形态；
2. ⭐ **匹配口径复用同一个函数**（`import_service.match_and_apply`）：锚点 = **含税合同价**、范围 = 单个项目
   ⇒ 命中 1 条就更新它 ＋ 补汇总发票行；**同源重跑不翻倍**（已有同 kind 发票行 ⇒ 跳过并报出来）；
3. **项目必填**（不给 ⇒ 显式拒绝）；本域**无批次回滚** ⇒ 没有 rollback 端点。

⚠️ 会**真写库** ⇒ 仓库名取随机值（持久测试库）。
"""

from __future__ import annotations

import io
import uuid
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.import_kit import api as imp_api
from app.import_kit.profile_store import ProfileStore
# ⚠️ 先注册表（独立 app ⇒ 不导入就有 FK 解析不到的风险）
from app.mod01_projects import models as _pj_models  # noqa: F401
from app.mod11_jc import imp_spec
from tests.acc_plugin import acc

#: 真台账形态：r2 一级（`供应商`/`贸易公司` 各合并两列）· r3 二级（合同总价 / 发票金额）
R2 = ["序号", "合同日期", "材料名称", "供应商", "", "贸易公司", "", "详细付款方式", "备注"]
R3 = ["", "", "", "合同总价", "发票金额", "合同总价", "发票金额", "", ""]
MERGES = [("A1", "I1"), ("D2", "E2"), ("F2", "G2")]
AMT = "42799.80"


def _book(rows: list[tuple] | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "台账"
    ws.append(["晋江污泥处理项目集采台账"])
    ws.append(list(R2))
    ws.append(list(R3))
    for row in (rows if rows is not None else [(1, "20240723", "钢材", AMT, "40731.17",
                                                "42885.40", "40812.62", "电汇", "60±7银行承兑")]):
        ws.append(list(row))
    for a, b in MERGES:
        ws.merge_cells(f"{a}:{b}")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(imp_api, "current_operator", lambda: "导入自检")
    app = FastAPI()
    app.include_router(imp_api.build_router(imp_spec.SPEC, imp_spec.HOOKS,
                                            store=ProfileStore(tmp_path / "p.json")))
    return TestClient(app)


def _parse(client):
    return client.post("/api/imp/m11_jc/parse",
                       files={"file": ("台账.xlsx", _book(),
                                       "application/vnd.openxmlformats-officedocument"
                                       ".spreadsheetml.sheet")},
                       data={"sheet": ""}).json()


@acc("ACC-IMP-MAP-001", "001-12")
def test_集采台账在通用面端到端_两级拼名认列_锚点匹配_且幂等(client):
    """⭐ 第三个真域：两级拼名认列 → 预览 → 按**合同价锚点**匹配更新 → 再落一次**发票不翻倍**。"""
    from app.core.db import session_scope
    from app.mod01_projects import repository as pj_repo
    from app.mod01_projects.models import TYPE_NORMAL
    from app.mod11_jc.models import JcContract, JcInvoice

    got = _parse(client)
    assert got["ok"] and got["header_rows"] == [2, 3], got
    cols = {c["src"]: c for c in got["cols"]}
    assert cols["供应商合同总价"]["field"] == "供应商合同总价", "两级拼名要认得出（合并格只铺表头行）"
    assert cols["贸易公司发票金额"]["field"] == "贸易公司发票金额"
    assert cols["详细付款方式"]["field"] == "付款方式"
    assert {c["src"] for c in got["cols"] if c["ignored"]} == {"序号"}, "「序号」要显式说明不采"

    wh = "__自检仓_IMP_M11_" + uuid.uuid4().hex[:8] + "__"
    with session_scope() as s:
        p = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full="__自检_B5b_台账__",
                                   warehouse_name=wh, phid="")
        s.add(JcContract(contract_no="__自检_B5b_C1__", project_id=int(p.id),
                         contract_date="2024-07-23", material_name="i8给的材料名",
                         supplier="i8给的供应商", contract_amt=Decimal(AMT)))
    mapping = {"合同日期": "合同日期", "材料名称": "材料名称", "供应商合同总价": "供应商合同总价",
               "供应商发票金额": "供应商发票金额", "贸易公司合同总价": "贸易公司合同总价",
               "贸易公司发票金额": "贸易公司发票金额", "详细付款方式": "付款方式", "备注": "备注"}
    body = {"token": got["token"], "mapping": mapping, "options": {"project_key": wh}}
    pre = client.post("/api/imp/m11_jc/preview", json=body).json()
    assert pre["ok"] and pre["total"] == 1, pre

    out = client.post("/api/imp/m11_jc/commit", json=body).json()
    assert out["ok"] and out["report"]["updated"] == 1, out
    assert out["report"]["unmatched"] == 0 and out["report"]["ambiguous"] == 0, out["report"]
    assert out["report"]["items"][0]["fields"], "要报出这次更新了哪几列（Excel 的地盘）"

    again = client.post("/api/imp/m11_jc/commit", json=body).json()
    assert again["report"]["warned"] >= 1, f"同源重跑必须报「已有发票行 ⇒ 不重复加」：{again['report']}"
    with session_scope() as s:
        inv = s.query(JcInvoice).filter(JcInvoice.contract_id == out["report"]["items"][0]["id"]).count()
    assert inv == 2, f"一合同两张汇总发票行（供应商/贸易公司），重导不翻倍：{inv}"


@acc()
def test_老xls也能读_按魔术字节判类型():
    """⭐ 用户的集采台账是**老 `.xls`** ⇒ 通用面必须两种格式都认（⛔ 且**不靠文件名**）。

    （真 `.xls` 的端到端在实测里验过：两份真台账走通用面各认出 12/11 列、真未认出 0；
      本件钉的是**判型逻辑**——⛔ 别为了"省事"改成看后缀。）
    """
    from app.core.errors import MustReportError
    from app.import_kit.readers import _kind, read_grid

    assert _kind(b"PK\x03\x04rest") == "xlsx"
    assert _kind(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1rest") == "xls"
    assert _kind(b"hello world") == ""
    with pytest.raises(MustReportError) as bad:
        read_grid(b"hello world")
    assert "后缀" in str(bad.value), "非 Excel 的文件要给一句明白话（说的是**按内容判**）"


@acc()
def test_项目必填_且没有回滚端点(client):
    """⚠️ 匹配范围 = 单个项目 ⇒ 不给项目就明确拒绝；本域无批次回滚 ⇒ 不挂 rollback。"""
    got = _parse(client)
    out = client.post("/api/imp/m11_jc/commit",
                      json={"token": got["token"], "mapping": {"合同日期": "合同日期"}}).json()
    assert out["ok"] is False and "项目" in out["message"], out
    assert client.post("/api/imp/m11_jc/rollback", json={"batch": "X"}).status_code in (404, 405)
