"""`MOD-04` **PRG 表单端点**的请求级自检（离线 · 不连库）。

⭐ **为什么单独有它**（2026-09-17 **真机实测**发现的缺陷）：
    `act_cell` / `act_delete` / `act_re_match` 三处，页面表单提交的是 **POST body**（hidden inputs），
    而端点参数却声明为 `Query(...)` ⇒ **真机提交一律 422**（按钮点了没反应）。
    实测：`POST /m04/cell` = **422**；对照同样形态的 `/m04/row/draft`（用 `Form`）= **303**。
    ⚠️ 而当时的断言只有 `assert 'action="/m04/cell"' in html`（**只查字符串在不在**）⇒ **假绿**。

⇒ 本文件的纪律：**真的按表单提交一次**，断言「**不是 422**」。
   ⚠️ 与 `tools/chain_audit.py` 同一初心 —— **判据要钉住"这条路真的走得通"，不是"零件在不在"**。
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod04_plan.models import PlanRow
from app.mod04_plan.router import get_db, get_page_data
from app.mod04_plan.service import build_page_data
from app.mod05_flow.models import PaymentFlow
from tests.acc_plugin import acc
from tests.m03_action_helpers import FakeWriteSession
from tests.m04_helpers import FakeSession, dataset


def _client(plan_rows=(), page_rows=None):
    """离线 client：**页面取数**与**会话**都注入桩（不连库）。

    · `plan_rows` = 给**写**路径（会话里的行）；
    · `page_rows` = 给**页面渲染**（默认用演示数据集 —— 两条路各有各的桩，别混）。
    """
    app = create_app()
    ds = dataset()
    if page_rows is not None:
        ds[PlanRow] = list(page_rows)

    def _loader(**kw):
        return build_page_data(FakeSession(ds), **kw)

    fake = FakeWriteSession({PlanRow: list(plan_rows), Project: [], PaymentFlow: [], PaymentNotice: []})
    app.dependency_overrides[get_db] = lambda: fake
    app.dependency_overrides[get_page_data] = lambda: _loader
    return TestClient(app, raise_server_exceptions=False), fake


def _row(**kw) -> PlanRow:
    """一条**未匹配**计划行（`forced_through` 初始为假）。"""
    vals = dict(
        id=2, year_month="2026-09", project_input="乙仓库", project_id=None,
        match_status="unmatched", match_candidates=0, doc_no="D9",
        flow_amount=Decimal("1000.00"), planned_amount=Decimal("800.00"),
        pay_date="", pay_method="", remark="", forced_through=False, forced_remark="",
        is_manual=False, raw={},
    )
    vals.update(kw)
    return PlanRow(**vals)


# ============================================================ 强制通过（§4.3.4 · 001-09）


@acc("ACC-PLAN-AUDIT-001", "001-09")
def test_强制通过_按表单提交即落库并留痕():
    """⭐ 请求级：**照页面表单提交一次**（body）⇒ 303 且两列都落库。"""
    row = _row()
    client, _ = _client(plan_rows=[row])
    r = client.post(
        "/m04/force", data={"row_id": "2", "remark": "已向项目核实，金额无误"},
        follow_redirects=False,
    )
    assert r.status_code == 303, f"表单提交应为 303，实际 {r.status_code}"
    assert "msgkind=err" not in r.headers["location"]
    assert row.forced_through is True
    assert row.forced_remark == "已向项目核实，金额无误"


@acc("ACC-PLAN-AUDIT-001", "001-09")
def test_强制通过_空备注被拒且不落库():
    """★ 口径：系统只提示不拦截，但**放行必须写备注** ⇒ 空备注 ⇒ 报错回执 ＋ **一行都不改**。"""
    row = _row()
    client, _ = _client(plan_rows=[row])
    r = client.post("/m04/force", data={"row_id": "2", "remark": "   "}, follow_redirects=False)
    assert r.status_code == 303 and "msgkind=err" in r.headers["location"]
    assert row.forced_through is False and row.forced_remark == ""


@acc("ACC-PLAN-AUDIT-001", "001-09")
def test_取消强制通过_回到原判定且备注清空():
    """★ 口径：**取消不留痕** —— 备注清空、判定回到原值，且**不产生任何残余**。"""
    row = _row(forced_through=True, forced_remark="上次的理由")
    client, _ = _client(plan_rows=[row])
    r = client.post("/m04/force-cancel", data={"row_id": "2"}, follow_redirects=False)
    assert r.status_code == 303 and "msgkind=err" not in r.headers["location"]
    assert row.forced_through is False and row.forced_remark == ""


# ============================================================ 防复发（端点形态）


@acc()
def test_PRG表单端点必须接受body编码():
    """⛔ **防复发**：这些端点的输入来自 `<form method="post">` 的 **body** ⇒ 必须按 `Form` 声明。

    ⚠️ 只断言「**不是 422**」：离线桩不覆盖全部写路径（可能 500），但**参数层必须收得下** ——
       这正是本轮真机实测抓到的那类缺陷（`Query` 声明 ⇒ 表单提交 422）。
    """
    row = _row()
    client, _ = _client(plan_rows=[row])
    payload = {"row_id": "2", "ids": "2", "column": "remark", "value": "x", "remark": "理由"}
    for path in ("/m04/cell", "/m04/re-match", "/m04/delete", "/m04/force", "/m04/force-cancel"):
        r = client.post(path, data=payload, follow_redirects=False)
        assert r.status_code != 422, f"{path} 表单提交返回 422 —— 参数声明与提交方式不一致"


@acc()
def test_草稿行的归月字段不与筛选月同名():
    """⭐ 防复发：草稿行的「归月」字段名必须是 `row_ym`。

    ⛔ 若叫 `year_month`，会与 `hidden_filters` 放进同一表单 body 的**筛选月**撞名 ⇒
       `FormData` 只取**第一个**（筛选值）⇒ **用户填的「归月」被静默忽略**（2026-09-17 修）。
    """
    client, _ = _client()
    html = client.get("/m04", params={"year_month": "2026-09", "draft": "new"}).text
    assert 'name="row_ym"' in html, "草稿行的「归月」字段名不是 row_ym ⇒ 会与筛选月撞名"


@acc()
def test_强制通过入口按行态呈现():
    """页面入口三态（照原型 `PL` 页）：完全匹配 ⇒ 无需处理；已放行 ⇒ 备注 ＋ 取消；否则 ⇒ 强制通过。"""
    client, _ = _client(plan_rows=[_row(id=2, doc_no="D9")])
    html = client.get("/m04", params={"year_month": "2026-09"}).text
    assert 'action="/m04/force"' in html
    assert 'name="remark"' in html                       # 备注输入（服务端渲染过渡形态）
    assert 'action="/m04/force-cancel"' not in html      # 未放行 ⇒ 不该出现取消入口

    forced = _row(id=2, doc_no="D9", forced_through=True, forced_remark="已核实")
    client2, _ = _client(page_rows=[forced])
    html2 = client2.get("/m04", params={"year_month": "2026-09"}).text
    assert 'action="/m04/force-cancel"' in html2
    assert "已核实" in html2
    assert 'action="/m04/force"' not in html2            # 已放行 ⇒ 不再显示「强制通过」入口
