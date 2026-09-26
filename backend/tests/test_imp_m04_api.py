"""`m04` 付款计划 · **通用导入面**端到端（`TAIL-75` · `B5b`）—— 第二个真域挂上 `/api/imp/*`。

⭐ 钉三件：
1. **端到端**：`schema → parse（认列）→ preview → commit`（本域**无批次回滚** ⇒ 不挂 `rollback` 端点）；
2. ⭐ **域内两条口径在通用面上不许走样**：① 「**9月11号**」这类中文月日要按**所选年月**补成完整日期；
   ② **幂等**（同源重跑 = 更新不重复，§9.5）；
3. **年月必填**：不选年月 ⇒ **显式拒绝**（⛔ 不许落到"没有月份"的桶里）。

⚠️ 会**真写库** ⇒ 仓库名/年月都取随机值（持久测试库），避免撞既有两个月的唯一约束。
"""

from __future__ import annotations

import io
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.import_kit import api as imp_api
from app.import_kit.profile_store import ProfileStore
# ⚠️ 先注册 `project` 等表（独立 app ⇒ 不导入就有 FK 解析不到的风险，m06 那件踩过）
from app.mod01_projects import models as _pj_models  # noqa: F401
from app.mod04_plan import imp_spec
from tests.acc_plugin import acc

HEADER = ["项目", "该流程金额", "本月预付款金额", "付款时间", "付款方式", "备注", "审批状态",
          "材料：其他支出付资产处/贸易公司（编号）"]


def _book(rows: list[tuple] | None = None) -> bytes:
    """实拍形态：大标题 1 行 ＋ 表头 1 行 ＋ 数据（含**中文月日**与**长表头**那两列）。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "材机付款计划明细"
    ws.append(["2026年9月付款计划（材机费）"])
    ws.append(list(HEADER))
    for row in (rows if rows is not None else _rows()):
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _rows(wh: str, ym_cn: str = "9月11号"):
    return [
        (wh, "797,726.5", "400,000", ym_cn, "承兑", "循环水管道", "已审批", "FKTZS2025120365"),
        (wh, "28,922", "28,922", "9月15号", "现金", "PE管件", "已审批", "CL2026090012"),
    ]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(imp_api, "current_operator", lambda: "导入自检")
    app = FastAPI()
    app.include_router(imp_api.build_router(imp_spec.SPEC, imp_spec.HOOKS,
                                            store=ProfileStore(tmp_path / "p.json")))
    return TestClient(app)


def _parse(client, wh: str):
    return client.post("/api/imp/m04_plan/parse",
                       files={"file": ("计划.xlsx", _book(_rows(wh)),
                                       "application/vnd.openxmlformats-officedocument"
                                       ".spreadsheetml.sheet")},
                       data={"sheet": ""})


@acc("ACC-IMP-MAP-001", "001-11")
def test_付款计划在通用面端到端_中文月日按年月补全_且幂等(client):
    """⭐ 第二个真域：认列 → 预览 → 落库 → **再落一次是"更新"而不是"新建"**（§9.5 幂等）。"""
    from app.core.db import session_scope
    from app.mod01_projects import repository as pj_repo
    from app.mod01_projects.models import TYPE_NORMAL
    from app.mod04_plan import repository as repo4

    wh = "__自检仓_IMP_M04_" + uuid.uuid4().hex[:8] + "__"
    # ⚠️ 年月必须**月份合法**（本域的中文月日只补"日"、且要同年月：`norm_pay_date` 会比对月份）；
    # ⚠️⚠️ 2026-09-23 修**本件自己的假红**（不是产品缺陷）：原先年份只有 **256** 种（`"20" + hex[:2]`）
    #    ⇒ 实测**撞过一次**（该年已在库里 ⇒ `created` 变 0、`updated` 变 2 ⇒ 断言红，而实现是对的）。
    #    ⇒ 两处一起改：① 年份空间放大到 **2000–9999**；② **先把该月清干净**
    #    （`merge_month(rows=[])` = 同一条落库出口的幂等清理，只清自动行、手动行保留）
    #    ⇒ 从此**确定性**，不再靠抽签。
    ym = f"{2000 + uuid.uuid4().int % 8000:04d}-09"
    with session_scope() as s:
        repo4.merge_month(s, year_month=ym, rows=[])       # 清该月（确定性；⛔ 不靠随机避开）
        pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full="__自检_B5b_付款计划__",
                               warehouse_name=wh, phid="")
    got = _parse(client, wh).json()
    assert got["ok"] and got["header_row"] == 2, got
    cols = {c["src"]: c for c in got["cols"]}
    assert cols["项目"]["field"] == "项目"
    assert cols["材料：其他支出付资产处/贸易公司（编号）"]["field"] == "材料单据", \
        "实拍长表头要被别名库认出（B2 的成果在通用面上同样生效）"
    assert {c["src"] for c in got["cols"] if c["ignored"]} == {"审批状态"}, "不采的列要显式说明理由"

    mapping = {"项目": "项目", "该流程金额": "该流程金额", "本月预付款金额": "本月预付款金额",
               "付款时间": "付款时间", "付款方式": "付款方式", "备注": "备注",
               "材料：其他支出付资产处/贸易公司（编号）": "材料单据"}
    body = {"token": got["token"], "mapping": mapping, "options": {"year_month": ym}}
    pre = client.post("/api/imp/m04_plan/preview", json=body).json()
    assert pre["ok"] and pre["total"] == 2, pre

    out = client.post("/api/imp/m04_plan/commit", json=body).json()
    assert out["ok"] and out["report"]["year_month"] == ym, out
    assert out["report"]["created"] == 2 and out["report"]["deleted"] == 0, out["report"]
    again = client.post("/api/imp/m04_plan/commit", json=body).json()
    assert again["report"]["created"] == 0 and again["report"]["updated"] == 2, \
        f"同源重跑必须「更新不重复」（§9.5）：{again['report']}"

    with session_scope() as s:
        rows = repo4.list_rows_of_month(s, year_month=ym)     # ⚠️ 回的是**模型对象**（不是 dict）
    pay_dates = sorted(str(getattr(r, "pay_date", "") or "") for r in rows)
    assert pay_dates == [f"{ym}-11", f"{ym}-15"], f"中文月日要按所选年月补全：{pay_dates}"


@acc()
def test_预览就列出项目匹配盘点_且不给假的将写入数(client):
    """⭐ 2026-09-26（`TAIL-106`）：③ 预览要**先把对不上项目的行列出来**。

    ⚠️ 为什么接的是现成件：`importer.match_summary` 当初**就是为预览写的**（注释原话"预览用的项目匹配
      盘点 …… 让人先看见再确认"），可它随旧导入页 2026-09-23 下架后**零调用** ⇒ 接上它 = 零风险复用，
      ⛔ 绝不另写一份盘点口径。

    ⚠️ 两条口径同时成立（正是本域与"逐项目"那两域最不一样的地方）：
      ① **对不上的行照样进库**（本域是 `merge_month` **整批按月重写**，跟"配不上就不写"的集采**不是一回事**）
         ⇒ 所以**不给** `writable`（界面上「将写入」仍是通用面的行数，⛔ 别说成"匹配上的行数"——那是假话）；
      ② 系统**不猜**项目：一个字没对上就标「未匹配」，只列出来给人看。
    """
    from app.core.db import session_scope
    from app.mod01_projects import repository as pj_repo
    from app.mod01_projects.models import TYPE_NORMAL
    from app.mod04_plan import repository as repo4

    wh = "__自检仓_IMP_PRE_" + uuid.uuid4().hex[:8] + "__"
    ym = f"{2000 + uuid.uuid4().int % 8000:04d}-09"
    with session_scope() as s:
        repo4.merge_month(s, year_month=ym, rows=[])          # 先清该月（确定性；⛔ 不靠随机避开）
        pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full="__自检_预览盘点__",
                               warehouse_name=wh, phid="")
    lost = "压根没有的项目名-自检"
    rows = [(wh, "1000", "1000", "9月11号", "承兑", "", "已审批", ""),
            (lost, "2000", "2000", "9月12号", "承兑", "", "已审批", "")]
    got = client.post("/api/imp/m04_plan/parse",
                      files={"file": ("计划.xlsx", _book(rows),
                                      "application/vnd.openxmlformats-officedocument"
                                      ".spreadsheetml.sheet")},
                      data={"sheet": ""}).json()
    assert got["ok"], got
    body = {"token": got["token"],
            "mapping": {"项目": "项目", "该流程金额": "该流程金额", "本月预付款金额": "本月预付款金额",
                        "付款时间": "付款时间", "付款方式": "付款方式", "备注": "备注"},
            "options": {"year_month": ym}}
    pre = client.post("/api/imp/m04_plan/preview", json=body).json()
    assert pre["ok"] and pre["total"] == 2, pre
    assert "writable" not in pre, \
        "本域**全行都写** ⇒ 不许给「将写入 = 匹配上的行数」（那会把「照样进库」那半句说成假话）"
    assert pre["kpis"]["项目未匹配"] == 1, pre.get("kpis")
    blk = [b for b in pre["blocks"] if "对不上" in b["title"]]
    assert blk and blk[0]["rows"], f"对不上项目的行要逐条列出来：{pre.get('blocks')}"
    assert lost in str(blk[0]["rows"][0]), blk[0]["rows"][0]
    with session_scope() as s:
        assert repo4.list_rows_of_month(s, year_month=ym) == [], "盘点也**不许写库**（预览零写库）"


@acc()
def test_缺年月要显式报错_不静默落库(client):
    """⚠️ 本域**必须先选年月**（本批数据全归该月，§4.3.3）⇒ 不给就明确拒绝。"""
    got = _parse(client, "__随便__").json()
    out = client.post("/api/imp/m04_plan/commit",
                      json={"token": got["token"], "mapping": {"项目": "项目", "该流程金额": "该流程金额"}}).json()
    assert out["ok"] is False and "年月" in out["message"], out


@acc()
def test_本域没有批次回滚_就不挂回滚端点(client):
    """⚠️ 口径：付款计划**无批次回滚**（同月重导 = 覆盖更新）⇒ 通用面**不该**给它一个回滚端点。"""
    # ⚠️ 没有这个端点 ⇒ FastAPI 给 **404**（405 是"路径在、方法不对"）
    assert client.post("/api/imp/m04_plan/rollback", json={"batch": "X"}).status_code in (404, 405)
    sch = client.get("/api/imp/m04_plan/schema").json()
    assert sch["batch"] is False and "审批状态" in {i["label"] for i in sch["ignored"]}


@acc()
def test_通用面预览阶段不写库_且坏token显式报错(client):
    """⭐ **两条 claim 从 `test_plan_import.py` 搬过来**（`TAIL-75` 余项 · 2026-09-23 **用户裁定**
    「只留通用面」⇒ `m04` 的页内导入端点连件删除）：**判词一字不改，只换落点**。

    ① **预览阶段一个字节都不写库**（`TAIL-69` 三条硬性之三）—— 这里**直接查库**证明
       （原先靠假会话的 `fake.added`；现在用真库 ⇒ **更强**：库真的没动）；
    ② **token 不存在 / 过期 ⇒ 显式报错**（⛔ 不静默当成空导入 —— 空导入会把该月清掉）。
       ⚠️ **形态**：通用面**恒 HTTP 200、成败看回包 `ok`**（全站写动作口径）⇒ 断言随之改形，claim 不变。
    """
    from app.core.db import session_scope
    from app.mod04_plan import repository as repo4

    ym = f"{2000 + uuid.uuid4().int % 8000:04d}-09"
    with session_scope() as s:
        repo4.merge_month(s, year_month=ym, rows=[])              # 先清该月（确定性，⛔ 不靠随机避开）
    wh = "__自检仓_IMP_M04_PREV_" + uuid.uuid4().hex[:8] + "__"
    got = _parse(client, wh).json()
    assert got["ok"] and got["token"], got
    body = {"token": got["token"], "mapping": {"项目": "项目", "该流程金额": "该流程金额"},
            "options": {"year_month": ym}}

    pre = client.post("/api/imp/m04_plan/preview", json=body).json()
    assert pre["ok"] and pre["total"] == 2, pre
    with session_scope() as s:
        assert repo4.list_rows_of_month(s, year_month=ym) == [], \
            "**预览阶段一个字节都不写库**（`TAIL-69` 三条硬性之三）"

    bad = client.post("/api/imp/m04_plan/commit",
                      json={"token": "deadbeefdeadbeefdeadbeefdeadbeef", "mapping": {},
                            "options": {"year_month": ym}}).json()
    assert bad["ok"] is False and str(bad.get("message") or "").strip(), \
        f"坏 token 必须**显式报错**（⛔ 不静默当成空导入 —— 空导入会把该月清掉）：{bad}"
    with session_scope() as s:
        assert repo4.list_rows_of_month(s, year_month=ym) == [], "坏 token 那次**也不许写库**"
