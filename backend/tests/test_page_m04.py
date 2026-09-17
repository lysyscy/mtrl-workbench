"""`MOD-04` **页面与组装层**的工程自检（离线 · 不连库）。

⚠️ 本文件**不绑定 `ACC-*` 判据点**（`@acc()` 显式声明）—— `ACC-PLAN-UI-001` 的判据在
`test_acc_plan_ui.py` 里已由**纯函数**钉住；本文件守的是**页面装配**这层：
五段骨架 / 合计行带 `sumrow` / 可改列只在「未匹配」行 / 删除前先列影响范围 / 两档归并的筛选真的生效。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.money import to_money
from app.main import create_app
from app.mod03_notice.page import LIST_PAGE_SEGMENTS, segment_sequence, tip_block_count
from app.mod04_plan.domain import BUCKET_MATCHED, BUCKET_UNMATCHED, R_MATCHED
from app.mod04_plan.router import get_page_data
from app.mod04_plan.service import build_page_data
from app.mod04_plan.view import COLUMNS
from tests.acc_plugin import acc
from tests.m04_helpers import FakeSession, dataset


def _loader(**kw):
    return build_page_data(FakeSession(dataset()), **kw)


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_page_data] = lambda: _loader
    return TestClient(app)


@acc()
def test_页面五段骨架与单折叠块():
    r = _client().get("/m04", params={"year_month": "2026-09"})
    assert r.status_code == 200
    html = r.text
    assert segment_sequence(html)[:4] == list(LIST_PAGE_SEGMENTS[:4])
    assert tip_block_count(html) == 1
    assert 'class="fbar" data-seg="filter"' in html
    assert "口径说明 · " in html


@acc()
def test_合计行带sumrow且只有一个():
    html = _client().get("/m04", params={"year_month": "2026-09"}).text
    assert 'class="sum sumrow" data-pin="1"' in html
    assert html.count('data-pin="1"') == 1


def _row_ids(html: str) -> list[int]:
    """从 tbody 里取**数据行**的计划行号（首格是纯数字；合计行/空态行首格非数字 ⇒ 自动排除）。"""
    import re

    body = re.search(r"<tbody\b[^>]*>([\s\S]*?)</tbody>", html)
    out: list[int] = []
    for tr in re.findall(r"<tr\b[^>]*>[\s\S]*?</tr>", body.group(1) if body else ""):
        m = re.match(r"<tr[^>]*><td>(\d+)</td>", tr)
        if m:
            out.append(int(m.group(1)))
    return out


@acc()
def test_筛选两档归并与年月闭区间真的生效():
    c = _client()
    allm = _row_ids(c.get("/m04", params={"year_month": "2026-09"}).text)
    assert allm == [1, 2]                                          # 9 月两行；8 月那行不出现
    only_matched = _row_ids(c.get("/m04", params={"year_month": "2026-09", "review": BUCKET_MATCHED}).text)
    assert only_matched == [1]
    only_un = _row_ids(c.get("/m04", params={"year_month": "2026-09", "review": BUCKET_UNMATCHED}).text)
    assert only_un == [2]                                          # 「未匹配」= 其余 5 种
    assert _row_ids(c.get("/m04", params={"year_month": ""}).text) == [1, 2, 3]   # 全部月份
    assert _row_ids(c.get("/m04", params={"year_month": "2026-08"}).text) == [3]  # 单月闭区间


@acc()
def test_可改列只在未匹配行出现且操作列不可排():
    html = _client().get("/m04", params={"year_month": "2026-09"}).text
    assert 'action="/m04/cell"' in html
    assert "再次匹配" in html                    # 未匹配行才有
    # 完全匹配行（id=1）的单据号是只读文本；未匹配行（id=2）是可改输入框
    assert 'value="D1"' not in html
    labels = [c["label"] for c in COLUMNS if not c["sortable"]]
    assert "操作" in labels and "已付款金额" in labels


@acc()
def test_删除前先列影响范围():
    c = _client()
    confirm = c.get("/m04/delete", params={"ids": "2", "year_month": "2026-09"})
    assert confirm.status_code == 200
    assert "将删除 1 行付款计划数据" in confirm.text
    assert "只影响付款计划表" in confirm.text
    assert "审查结果" in confirm.text
    # 影响范围含「行号 / 所属年月 / 审查结果」三列
    assert ">2026-09<" in confirm.text and ">2<" in confirm.text


@acc()
def test_回报条转义_不得反射注入():
    """⭐ `TAIL-05`：`message` / `message_kind` 走**查询串**（`?msg=` / `?msgkind=`）⇒ 属外部输入。

    漏转义 = **反射型注入面**（台账原按"消息都是内部拼的"低估了；实测 `router.page_m04`
    把 `msg` 直接透传进来）。`MOD-03` 同款位置（`notice_page.py` / `notice_pay.py`）一直用 `esc()`。
    """
    html = _client().get(
        "/m04", params={"year_month": "2026-09", "msg": "<script>alert(1)</script>"}
    ).text
    assert "<script>alert(1)</script>" not in html            # 原样不得落 HTML
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html      # 只允许转义后出现

    kind_html = _client().get(
        "/m04", params={"year_month": "2026-09", "msg": "hi", "msgkind": 'a"b'}
    ).text
    assert 'class="notice a&quot;b"' in kind_html             # kind 也不得逃出属性引号


@acc()
def test_已付金额按生效流水派生_未命中留空():
    data = _loader(year_month="2026-09", project_ids=(), audit_bucket="全部", sort_col="", sort_dir=0)
    row1 = next(r for r in data["rows"] if r["id"] == 1)
    assert row1["paid_amount"] == "200.00"          # 流水汇总
    assert row1["unpaid_amount"] == "800.00"        # 审批金额 1000 − 已付 200
    assert row1["audit_result"] == R_MATCHED
    row2 = next(r for r in data["rows"] if r["id"] == 2)
    assert row2["paid_amount"] == "" and row2["unpaid_amount"] == ""   # 未命中 ⇒ 留空，不猜
    assert to_money(data["summary"]["flow_amount"]) == to_money("1500.00")
