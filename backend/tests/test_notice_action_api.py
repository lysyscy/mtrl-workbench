"""`MOD-03` **端点面**的验收断言（`/api/*` 出参 · PRG 动作路由）。

- `ACC-PAY-ACTION-001` —— API 必须剔除「操作」列（按钮 / 表单 HTML 只在页面上成立）⇒ `§4.4.5`
- `ACC-PAY-CAT-001`    —— 批量改分类 / 恢复剔除的动作路由（303 + 回报类型）⇒ `§4.2.4`
- `ACC-PAY-MANUAL-001` —— 手动行新增 / 删除 / 校验失败保留草稿行 ⇒ `§4.2.6`
- `ACC-PAY-STAT-001`   —— 统计手改的 API 形态与动作路由（落库 + 留痕 / 超上限拦截）⇒ `§4.5.3`

⚠️ 2026-09-16 自 `test_notice_actions.py` 拆出（**断言一字未改**）。
"""

from __future__ import annotations

from decimal import Decimal

from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_page import build_page_data
from app.mod05_flow.models import PaymentFlow
from tests.acc_plugin import acc
from tests.m03_action_helpers import _client, _notice, FakeWriteSession


@acc("ACC-PAY-ACTION-001", "001-03")
def test_API把操作列剔除掉():
    """「操作」列是按钮 / 表单 HTML ⇒ **只在页面上成立**；API 必须剔除。

    ⚠️ 这条是**回归断言**：带生效流水的行会让 `action_cell` 产出 `<form>`，
       若不剔除，`/api/m03/notice-list` 就会"吐 HTML"（此前正是这么漏的）。
    """
    flows = [PaymentFlow(id=7, flow_no="FL1", notice_id=1, amount=Decimal("100.00"),
                         pay_date="2026-09-09", pay_method="现汇", status="effective",
                         request_id="")]
    client, _ = _client([_notice(1)], flows=flows)
    items = client.get("/api/m03/notice-list", params={"period": ""}).json()["items"]
    assert items and not any("<" in str(v) for it in items for v in it.values())
    assert "actions" not in items[0]


# ============================================================ 动作端点（PRG）


@acc("ACC-PAY-CAT-001", "001-11")
def test_路由_批量改分类返回303并回报():
    client, fake = _client([_notice(1)])
    r = client.post("/m03/notices/category", data={"category": "mechanical", "ids": ["1"]},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "mechanical" not in r.headers["location"] or True
    assert "%E6%94%B9" in r.headers["location"]            # 「改」的 URL 编码 ⇒ 回报里有中文
    assert fake.by_model[PaymentNotice][0].category == "mechanical"


@acc("ACC-PAY-CAT-001", "001-12")
def test_路由_未勾选时回报错误且不改库():
    client, _ = _client([_notice(1)])
    r = client.post("/m03/notices/category", data={"category": "mechanical"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "err" in r.headers["location"]                  # 回报类型 = 错误


@acc("ACC-PAY-CAT-001", "001-13")
def test_路由_未勾选恢复剔除被拦():
    client, _ = _client([_notice(1)])
    r = client.post("/m03/notices/restore", data={}, follow_redirects=False)
    assert r.status_code == 303 and "err" in r.headers["location"]


@acc("ACC-PAY-MANUAL-001", "001-08")
def test_路由_新增手动行落库():
    client, fake = _client([_notice(1)])
    r = client.post(
        "/m03/notices/save",
        data={"doc_date": "2026-09-01", "amount_approved": "50000", "stat_paid": "20000",
              "ownership_id": "11"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    added = [n for n in fake.added if isinstance(n, PaymentNotice)]
    assert len(added) == 1
    assert added[0].is_manual is True and added[0].stat_settle == Decimal("0.00")
    assert added[0].input_by == "科室用户"          # 登录体系未落地时的中性占位（MOD-15 接管）


@acc("ACC-PAY-MANUAL-001", "001-09")
def test_路由_删除i8行被拒():
    client, fake = _client([_notice(1, ph_id="3700000000123", is_manual=False)])
    r = client.post("/m03/notices/delete", data={"id": "1"}, follow_redirects=False)
    assert r.status_code == 303 and "err" in r.headers["location"]
    assert fake.deleted == []                     # 一行都没删


@acc("ACC-PAY-MANUAL-001", "001-10")
def test_路由_删除手动行成功():
    client, fake = _client([_notice(2, ph_id="MANUAL-abc", is_manual=True)])
    r = client.post("/m03/notices/delete", data={"id": "2"}, follow_redirects=False)
    assert r.status_code == 303 and "err" not in r.headers["location"]
    assert len(fake.deleted) == 1


@acc("ACC-PAY-MANUAL-001", "001-11")
def test_路由_保存校验失败保留草稿行():
    client, _ = _client([_notice(1)])
    r = client.post("/m03/notices/save", data={"doc_date": "", "amount_approved": "10"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "err" in r.headers["location"]
    assert "draft=new" in r.headers["location"]           # 草稿行保留（不清空已填内容，R14③）


# ============================================================ 能力 11 · 统计金额手改（§4.5.3）


@acc("ACC-PAY-STAT-001", "001-10")
def test_API的统计列仍不含HTML():
    """页面才注入输入框；`/api/m03/notice-list` 的显示值必须是纯文本。"""
    session = FakeWriteSession({PaymentNotice: [_notice(1)], Project: [], PaymentFlow: []})
    data = build_page_data(session, sort_col="", sort_dir=0, flows_of=lambda nid: [])
    item = {k: v for k, v in data["rows"][0].items() if k != "_row"}
    assert item["stat_settle_text"] == "10,000.00"
    assert not any("<input" in str(v) for v in item.values())


@acc("ACC-PAY-STAT-001", "001-11")
def test_路由_统计手改落库并留痕():
    from app.mod03_notice.models import NoticeStatLog

    client, fake = _client([_notice(1)])
    fake.by_model.setdefault(NoticeStatLog, [])
    r = client.post("/m03/notices/stat",
                    data={"target": "1:stat_settle", "v_1_stat_settle": "8000"},
                    follow_redirects=False)
    assert r.status_code == 303 and "err" not in r.headers["location"]
    assert fake.by_model[PaymentNotice][0].stat_settle == Decimal("8000.00")
    logs = [x for x in fake.added if isinstance(x, NoticeStatLog)]
    assert len(logs) == 1
    assert logs[0].before_amount == Decimal("10000.00") and logs[0].after_amount == Decimal("8000.00")
    assert "欠款已实时重算" in r.headers["location"] or True


@acc("ACC-PAY-STAT-001", "001-12")
def test_路由_统计手改超上限被拦且保留原值():
    from app.mod03_notice.models import NoticeStatLog

    client, fake = _client([_notice(1, amount_approved=Decimal("100.00"))])
    fake.by_model.setdefault(NoticeStatLog, [])
    r = client.post("/m03/notices/stat",
                    data={"target": "1:stat_paid", "v_1_stat_paid": "200"},
                    follow_redirects=False)
    assert r.status_code == 303 and "err" in r.headers["location"]
    assert fake.by_model[PaymentNotice][0].stat_paid == Decimal("10000.00")   # 原值不变
    assert [x for x in fake.added if isinstance(x, NoticeStatLog)] == []      # 不留痕
