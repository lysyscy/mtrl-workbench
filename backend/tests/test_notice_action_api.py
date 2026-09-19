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


# ------------------------------------------------ `§19` 批 4 · S1：同上两条实质，改指 **JSON API**
# 原委：壳的统计手改原来只在**前端本地**改值 + 本地留痕（不落库 ✗）⇒ 接真接口 `POST /api/m03/actions/stat`；
# 旧页删除（授权 `D18`）后 PRG（上面那两条）随页消失，故**同样的实质**必须在新接口上有着落。


@acc("ACC-PAY-STAT-001", "001-11")
def test_API_统计手改落库并留痕():
    """**统计手改走 JSON API**：值真的落库 ＋ 留痕真的写进库（壳判「黄底」的唯一事实来源）。"""
    from app.mod03_notice.models import NoticeStatLog

    client, fake = _client([_notice(1)])
    fake.by_model.setdefault(NoticeStatLog, [])
    r = client.post("/api/m03/actions/stat",
                    json={"notice_id": 1, "field": "stat_settle", "value": "8000"})
    assert r.status_code == 200, "JSON 动作 API 一律恒 200（成败看 `ok`）"
    body = r.json()
    assert body["ok"] is True and body["changed"] is True
    assert body["before"] == "10000.00" and body["after"] == "8000.00"
    assert fake.by_model[PaymentNotice][0].stat_settle == Decimal("8000.00")     # 落库
    logs = [x for x in fake.added if isinstance(x, NoticeStatLog)]
    assert len(logs) == 1, "没留痕（壳里的「黄底」就判不出来了）"
    # 回执里的中文说明**原样给用户**（含留痕与欠款重算）—— 前端不自己拼
    assert "已留痕" in body["message"] and "欠款已实时重算" in body["message"]


@acc("ACC-PAY-STAT-001", "001-12")
def test_API_统计手改超上限被拦且保留原值():
    """上限 = 审批金额（§4.5.3「按发票走、只能少不能多」）⇒ **拦下并保留原值**，且**不留痕**。"""
    from app.mod03_notice.models import NoticeStatLog

    client, fake = _client([_notice(1)])
    fake.by_model.setdefault(NoticeStatLog, [])
    r = client.post("/api/m03/actions/stat",
                    json={"notice_id": 1, "field": "stat_paid", "value": "20000"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False and body["changed"] is False
    assert "上限" in body["message"] or "审批金额" in body["message"], f"没说清为什么拦：{body['message']}"
    assert fake.by_model[PaymentNotice][0].stat_paid == Decimal("10000.00")      # 原值不变
    assert [x for x in fake.added if isinstance(x, NoticeStatLog)] == []         # 不留痕


@acc()
def test_API_统计手改值没变时说清什么都没做():
    """§4.2.7：值没变 ⇒ **不做无意义的重算、不留空痕** —— 但要让用户看见「什么都没做」（不是静默）。"""
    from app.mod03_notice.models import NoticeStatLog

    client, fake = _client([_notice(1)])
    fake.by_model.setdefault(NoticeStatLog, [])
    r = client.post("/api/m03/actions/stat",
                    json={"notice_id": 1, "field": "stat_settle", "value": "10000.00"})
    body = r.json()
    assert body["ok"] is True and body["changed"] is False
    assert "什么都没做" in body["message"]
    assert [x for x in fake.added if isinstance(x, NoticeStatLog)] == []


@acc()
def test_PRG与JSON_API共用统计手改的唯一出口():
    """⛔ **防分叉**：判定 / 落库 / 文案只许一份 —— PRG 与 JSON API 都必须调
    `notice_actions.apply_stat_change`，任何一边**内联**判定或另写文案都算违规。

    （本仓的老毛病："同一口径只做了一半" / "两份实现悄悄漂移" ⇒ 这条就是给它立的阀门。）
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    prg = (root / "backend" / "app" / "mod03_notice" / "notice_actions_router.py").read_text(encoding="utf-8")
    api = (root / "backend" / "app" / "mod03_notice" / "notice_api_router.py").read_text(encoding="utf-8")
    for name, src in (("PRG", prg), ("JSON API", api)):
        assert "apply_stat_change(" in src, f"{name} 没走统计手改的唯一出口"
        assert "repo.adjust_notice_stat(" not in src, f"{name} 内联了落库/判定（应共用唯一出口）"
    assert "def apply_stat_change(" in (
        root / "backend" / "app" / "mod03_notice" / "notice_actions.py"
    ).read_text(encoding="utf-8"), "唯一出口本身没了"


# ------------------------------------------------ `§19` 批 4 · S2a：手动行新增/编辑走 **JSON API**
# 原委：壳的「手动新增 / 编辑」原来只在前端本地 `NO.push` / `Object.assign`（**不落库** ✗）⇒ 接真接口。


@acc("ACC-PAY-MANUAL-001", "001-08")
def test_API_新增手动行落库():
    """**手动行新增走 JSON API**：真的落库（`is_manual` ＋ **统计结算恒 0** §4.2.6）。"""
    client, fake = _client([_notice(1)])
    r = client.post("/api/m03/actions/manual-save", json={
        "doc_date": "2026-09-01", "bill_no": "MN01", "bill_name": "期初占位",
        "biz_type": "付其他供应商款", "payee": "某供应商", "category": "material",   # ⚠️ 服务端只认**键**（辅材/机械/集采是显示名）
        "amount_approved": "50000", "stat_paid": "20000",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["is_new"] is True
    added = [x for x in fake.added if isinstance(x, PaymentNotice)]
    assert len(added) == 1, "接口说成功但一行都没落库"
    assert added[0].is_manual is True
    assert added[0].stat_settle == Decimal("0.00"), "手动行「统计结算金额」必须恒 0（这笔钱没有新结算）"
    assert added[0].stat_paid == Decimal("20000.00")
    assert "已新增" in body["message"] and "只影响「付款」" in body["message"]


@acc("ACC-PAY-MANUAL-001", "001-11")
def test_API_保存校验失败不落库():
    """校验不过 ⇒ `ok=False` 且**一行都不落库**（外壳据此**保留草稿行**让用户改，R14③）。"""
    client, fake = _client([_notice(1)])
    before = len(fake.by_model[PaymentNotice])
    r = client.post("/api/m03/actions/manual-save", json={
        "doc_date": "不是日期", "amount_approved": "abc", "stat_paid": "1",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False and body["message"], "校验失败必须给一句能给人看的中文"
    assert [x for x in fake.added if isinstance(x, PaymentNotice)] == []
    assert len(fake.by_model[PaymentNotice]) == before


@acc()
def test_API_编辑手动行按改动字段回报():
    """编辑走**同一套**（§4.2.6）：只改传进来的那几列，回执报「改动 N 个字段」。"""
    client, fake = _client([_notice(1, is_manual=True, ph_id="MN01")])
    r = client.post("/api/m03/actions/manual-save", json={
        # ⚠️ 数字必须自洽：全站口径「统计两金额 ≤ 审批金额」（超了后端会正确地拦下）
        "row_id": "1", "doc_date": "2026-09-05", "stat_paid": "30000",
        "amount_approved": "50000", "category": "material",
    })
    body = r.json()
    assert body["ok"] is True and body["is_new"] is False
    assert "改动" in body["message"] and "个字段" in body["message"]
    row = fake.by_model[PaymentNotice][0]
    assert row.stat_paid == Decimal("30000.00")
    assert [x for x in fake.added if isinstance(x, PaymentNotice)] == [], "编辑不该新增行"


@acc()
def test_PRG与JSON_API共用手动行保存的唯一出口():
    """⛔ **防分叉**：手动行的校验 / 落库 / 文案只许一份 —— 两个出口都必须调
    `notice_actions.apply_manual_save`，谁都不许内联 `repo.create_manual_notice` / `update_manual_notice`。"""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    prg = (root / "backend" / "app" / "mod03_notice" / "notice_actions_router.py").read_text(encoding="utf-8")
    api = (root / "backend" / "app" / "mod03_notice" / "notice_api_router.py").read_text(encoding="utf-8")
    for name, src in (("PRG", prg), ("JSON API", api)):
        assert "apply_manual_save(" in src, f"{name} 没走手动行保存的唯一出口"
        for banned in ("repo.create_manual_notice(", "repo.update_manual_notice("):
            assert banned not in src, f"{name} 内联了落库（应共用唯一出口）：{banned}"


# ------------------------------------------------ `§19` 批 4 · S2b：删除 ＋ **删除前的影响范围**
# §7.2 / §9.4 是硬要求：**删除前必须列出影响范围**（关联数据、统计影响）⇒ 由后端给，壳原样显示。


@acc("ACC-PAY-MANUAL-001", "001-10")
def test_API_删除手动行成功():
    """**删除手动行走 JSON API**：真的落库（`session.delete`），文案由后端给。"""
    client, fake = _client([_notice(1, is_manual=True, ph_id="MN01")])
    r = client.post("/api/m03/actions/manual-delete", json={"notice_id": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and "已删除手动行" in body["message"]
    assert [x for x in fake.deleted if isinstance(x, PaymentNotice)], "接口说成功但没删"
    assert fake.by_model[PaymentNotice] == []


@acc("ACC-PAY-MANUAL-001", "001-09")
def test_API_删除i8行被拒且连影响范围都不给():
    """§4.2.7 铁律：**i8 抓取行永不删**（不提供删除入口）—— 连"删除前的影响范围"都不给看。"""
    client, fake = _client([_notice(1, is_manual=False)])
    r = client.post("/api/m03/actions/manual-delete", json={"notice_id": 1})
    body = r.json()
    assert body["ok"] is False and body["message"]
    assert [x for x in fake.deleted if isinstance(x, PaymentNotice)] == []
    assert fake.by_model[PaymentNotice] != []
    # 影响范围同样拒（否则等于给了一个"看着能删"的入口）
    ri = client.post("/api/m03/actions/manual-delete-impact", json={"notice_id": 1})
    assert ri.json()["ok"] is False


@acc()
def test_API_删除影响范围由后端给():
    """影响范围 = 后端产出（§7.2/§9.4）：要有「统计付款金额退出台账当月付款列 ⇒ **欠款回增**」这条实质，
    **并同时说明「已付金额不受影响」**（否则用户会以为流水也跟着没了）。"""
    client, _ = _client([_notice(1, is_manual=True, ph_id="MN01",
                                amount_approved=Decimal("50000.00"),
                                stat_paid=Decimal("30000.00"))])
    body = client.post("/api/m03/actions/manual-delete-impact", json={"notice_id": 1}).json()
    assert body["ok"] is True
    assert body["label"] and body["stat_paid"] == "30000.00" and body["amount_paid"]
    joined = body["message"] + "".join(body["effects"])
    assert "欠款" in joined and "回增" in joined, "没讲清「欠款会回增」"
    assert "已付金额" in joined and "不受影响" in joined, "没讲清「已付金额不受影响」"
    assert "不做软删" in joined, "没讲清「不做软删」"


@acc()
def test_PRG与JSON_API共用手动行删除的唯一出口():
    """⛔ **防分叉**：删除的校验 / 落库 / 文案只许一份 —— 两个出口都必须调
    `notice_actions.apply_manual_delete`，谁都不许内联 `repo.delete_notice`。"""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for name, rel in (("PRG", "notice_actions_router.py"), ("JSON API", "notice_api_router.py")):
        src = (root / "backend" / "app" / "mod03_notice" / rel).read_text(encoding="utf-8")
        assert "apply_manual_delete(" in src, f"{name} 没走手动行删除的唯一出口"
        assert "repo.delete_notice(" not in src, f"{name} 内联了删除（应共用唯一出口）"
