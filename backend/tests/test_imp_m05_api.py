"""`m05` 历史付款流水 · **通用导入面**端到端（`TAIL-75` · `B5b` 第三步）—— 第四个真域挂上 `/api/imp/*`。

⭐ 本件钉四件事：
1. **端到端能跑**：`schema → parse（认列）→ preview → commit → rollback`；
2. **落库口径 = 既有出口**：域钩子只是把 records 装成 `ImportPlan` 再调 `importer.commit`
   （→ `repository.create_flow` → `sync_stat_paid`）⇒ 一次付款一条流水、统计自动重算；
3. ⭐ **域内三条口径在通用面上不许走样**：
   ① **未匹配的行绝不落库、但必须列出来**（判据 `ACC-FLOW-IMPORT-001/001-02`）；
   ② **付款方式为空 ⇒ 存空**（⛔ 不兜底「现汇」）；归不进四类 ⇒ 记「其他」＋**原文留备注**；
   ③ 金额必须 > 0 / 付款时间要认得出来 ⇒ 进**异常清单**、不入库；
4. ⭐ **核对报告**（漏记清单 ＋ **超付单列**）在回执里给出来（判据 `ACC-FLOW-IMPORT-003/003-04`）。

⚠️ 落库会**真写库**（走真 `session_scope`）⇒ 单据号 / 月份都取随机值（持久测试库），
   并在收尾**物理删掉**本件造的流水与通知书（存量数据会污染"漏记清单"的计数 ⇒ 只断言"我那张在里面"）。
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
# ⚠️ 必须先把 `project` / `payment_notice` 等表导进来：本件用**独立 FastAPI app**（不经过 `app.main`）。
from app.mod01_projects import models as _pj_models  # noqa: F401
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow import imp_spec
from tests.acc_plugin import acc

HEADER = ["单据号", "付款金额", "付款时间", "付款方式", "备注"]
APPROVED = Decimal("100.00")          # 审批金额**刻意很小** ⇒ 本批 3 条流水一定会"超付"（供验超付单列）


def _bill_no() -> str:
    """i8 形态的单据号（字母开头 ＋ ≥6 位数字）—— 取随机值，避免撞既有数据。"""
    return "FKTZS" + str(uuid.uuid4().int)[:12]


def _book(rows: list[tuple]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "付款流水"
    ws.append(list(HEADER))
    for row in rows:
        ws.append(list(row))
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


@acc()
def test_没挂options钩子的域也要200不许404(client):
    """⭐ 2026-09-26：`/options` **恒挂** —— 没给钩子的域回 **200 ＋ 空包**，⛔ 不许 404。

    为什么值得一条断言：壳问「这个域有哪些上下文」是**一条通用问句**（壳里零域号分支，见
      `test_imp_shell.py`）—— 没挂钩子的域若回 404，两处一起坏：
      ① 真机自检 `tools/probe/_shell_smoke.py` 的「console / page 错误」把浏览器里的 404 **判红**；
      ② "问不到"（404）与"真的没有上下文"（空包）在壳侧长得一样 ⇒ 壳只能靠吞异常猜。
    ⇒ 本域（`m05_flow` **没有** `options` 钩子）就是这条的活样本。
    """
    r = client.get("/api/imp/m05_flow/options")
    assert r.status_code == 200, "没挂 `options` 钩子的域**不许**回 404（壳一问就红了）"
    got = r.json()
    assert got["ok"] is True, got
    assert set(got) - {"ok"} == set(), f"没有域上下文就该给空包（⛔ 别塞看着像上下文的键）：{got}"


def _parse(client, rows: list[tuple]):
    return client.post("/api/imp/m05_flow/parse",
                       files={"file": ("付款流水.xlsx", _book(rows),
                                       "application/vnd.openxmlformats-officedocument"
                                       ".spreadsheetml.sheet")},
                       data={"sheet": ""})


def _seed(ym: str, bill_no: str) -> list[tuple[int, str]]:
    """造两张通知书（同一个月）：① = `bill_no`（会有流水 ⇒ 供验**超付单列**）
    ② 另一张一条流水都没有（⇒ 供验**漏记清单**）。"""
    from app.core.db import session_scope

    out: list[tuple[int, str]] = []
    with session_scope() as s:
        for no in (bill_no, _bill_no()):
            row = PaymentNotice(ph_id=f"__自检_IMP_M05_{uuid.uuid4().hex}__", bill_no=no,
                                doc_date=f"{ym}-15", project_name="__自检_付款流水__",
                                amount_approved=APPROVED)
            s.add(row)
            s.flush()
            out.append((int(row.id), no))
    return out


def _drop(ids: list[int]) -> None:
    """物理清掉本件造的数据（⛔ 不留在测试库里污染后续的"漏记清单"计数）。"""
    from sqlalchemy import delete

    from app.core.db import session_scope
    from app.mod05_flow.models import PaymentFlow

    with session_scope() as s:
        s.execute(delete(PaymentFlow).where(PaymentFlow.notice_id.in_(list(ids))))
        s.execute(delete(PaymentNotice).where(PaymentNotice.id.in_(list(ids))))


@acc("ACC-IMP-MAP-001", "001-13")
def test_付款流水在通用面端到端_未匹配与异常不入库_核对报告单列(client):
    """⭐ 第四个真域：认列 → 预览（**未匹配 / 异常 / 未识别**都在）→ 落库 → 核对报告 → 整批回滚。"""
    ym = "20" + str(uuid.uuid4().int)[:2] + "-07"        # ⚠️ 年份必须是**数字**（域内日期解析要真认得出）
    bill_no, missing = _bill_no(), _bill_no()
    seeded = _seed(ym, bill_no)
    (mine, mine_no), (lonely, lonely_no) = seeded
    rows = [
        (bill_no, 300, f"{ym}-05", "电汇", "首款"),      # ✅ 可写（付款方式归一「现汇」）
        (bill_no, 300, f"{ym}-20", "", ""),              # ✅ 可写（**付款方式为空 ⇒ 存空**）
        (missing, 100, f"{ym}-11", "现汇", ""),          # ⚠️ 未匹配（本地查不到 ⇒ 不落库）
        (bill_no, 0, f"{ym}-12", "现汇", ""),            # ⚠️ 异常（金额必须 > 0 ⇒ 不落库）
        (bill_no, 50, f"{ym}-21", "微信红包", ""),       # ✅ 可写（归入「其他」＋原文留备注）
    ]
    try:
        got = _parse(client, rows).json()
        assert got["ok"] and got["header_row"] == 1, got
        cols = {c["src"]: c["field"] for c in got["cols"]}
        assert cols["单据号"] == "单据号" and cols["付款金额"] == "付款金额", cols
        assert cols["付款时间"] == "付款时间" and cols["备注"] == "备注", cols

        body = {"token": got["token"], "mapping": {lb: lb for lb in HEADER}}
        pre = client.post("/api/imp/m05_flow/preview", json=body).json()
        assert pre["ok"], pre
        assert pre["total"] == 5, pre
        # ⭐ 「将写入」= **匹配上的**条数（⛔ 不是解析行数 —— 未匹配/异常不落库）
        assert pre["writable"] == 3, pre
        assert pre["kpis"] == {"未匹配": 1, "异常": 1, "未识别付款方式": 1}, pre["kpis"]
        titles = [b["title"] for b in pre["blocks"]]
        assert any("未匹配清单" in t for t in titles), titles
        assert any("异常清单" in t for t in titles), titles
        assert any("未识别的付款方式" in t for t in titles), titles
        un = next(b for b in pre["blocks"] if "未匹配清单" in b["title"])
        assert [r[1] for r in un["rows"]] == [missing], un
        # ⭐ **预览阶段一个字节都不写库**（判据 001-06）
        assert not _flows_of(mine), "预览就把流水写进去了 —— 确认前必须零写库"

        out = client.post("/api/imp/m05_flow/commit", json=body).json()
        assert out["ok"] and out["report"]["written"] == 3, out
        assert out["report"]["unmatched"] == 1 and out["report"]["anomalies"] == 1, out["report"]
        assert out["report"]["unknown_methods"] == 1, out["report"]
        # ⭐ 2026-09-26（用户报障「**落库结果可读性比较差**」）：回执还必须**自报人话指标**（`kpis`）——
        #    ⚠️ 词与**本域自己的预览**（上面第 147 行那三个）**完全一样** —— 同一个数在两屏不许换说法。
        kpi = out["report"]["kpis"]
        assert kpi["写入流水"] == 3 and kpi["未匹配"] == 1, f"回执没自报人话指标：{kpi!r}"
        assert kpi["异常"] == 1 and kpi["未识别付款方式"] == 1, f"`kpis` 少项：{kpi!r}"
        assert "超付（实付 ＞ 审批金额）" in kpi, f"核对报告的两个数也要人话（漏记 / 超付）：{kpi!r}"
        batch = str(out["report"]["batch"])
        assert batch.startswith("IMP-"), out["report"]

        flows = _flows_of(mine)
        assert len(flows) == 3, flows                                     # 一次付款一条独立流水
        assert {str(f.import_batch) for f in flows} == {batch}, flows
        assert sorted(str(f.pay_method) for f in flows) == ["", "其他", "现汇"], \
            "空必须存空（⛔ 不兜底「现汇」）；归不进四类 ⇒ 「其他」"
        assert any("微信红包" in str(f.remark) for f in flows), "未识别取值的**原文必须留在备注**"
        assert _stat_paid(mine) == Decimal("650.00"), "导入后「统计付款金额」要按已付重算（§4.4.7）"

        # ⭐ 核对报告：漏记清单（同月里"一条流水都没有"的那张）＋ **超付单列**（650 > 审批 100）
        blocks = {b["title"]: b for b in out["report"]["blocks"]}
        missed = next(b for t, b in blocks.items() if "漏记清单" in t)
        assert lonely_no in [r[0] for r in missed["rows"]], missed
        over = next(b for t, b in blocks.items() if "超付清单" in t)
        assert mine_no in [r[0] for r in over["rows"]], over

        back = client.post("/api/imp/m05_flow/rollback", json={"batch": batch}).json()
        assert back["ok"] and back["report"]["revoked"] == 3, back
        assert len(_flows_of(mine)) == 3, "回滚是**置撤销**、⛔ 不物理删"
        assert {str(f.status) for f in _flows_of(mine)} == {"revoked"}, back
        assert _stat_paid(mine) == Decimal("0.00"), "回滚后统计付款金额要回退"
    finally:
        _drop([mine, lonely])


@acc()
def test_域声明与列契约同源_且本域有批次回滚():
    """⚠️ 本域的五列**直接取** `importer.COLUMNS`（§4.4.6 的固定列序）⇒ 字段清单/必填只此一处。"""
    from app.mod05_flow import importer as I

    assert len(imp_spec.FIELDS) == len(I.COLUMNS) == 5
    assert [f.required for f in imp_spec.FIELDS] == [bool(c[2]) for c in I.COLUMNS]
    assert imp_spec.SPEC.required == ("单据号", "付款金额", "付款时间"), imp_spec.SPEC.required
    assert imp_spec.SPEC.batch is True, "本域有批次 ⇒ 通用面必须挂回滚端点"
    assert imp_spec.HOOKS.preview is not None and imp_spec.HOOKS.rollback is not None


# ---------------------------------------------------------------- 取数小工具（只用真库）


def _flows_of(notice_id: int) -> list:
    from sqlalchemy import select

    from app.core.db import session_scope
    from app.mod05_flow.models import PaymentFlow

    with session_scope() as s:
        return list(s.execute(select(PaymentFlow).where(
            PaymentFlow.notice_id == int(notice_id))).scalars().all())


def _stat_paid(notice_id: int) -> Decimal:
    from app.core.db import session_scope

    with session_scope() as s:
        return Decimal(str(s.get(PaymentNotice, int(notice_id)).stat_paid))
