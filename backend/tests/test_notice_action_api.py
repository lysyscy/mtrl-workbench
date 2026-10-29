"""`MOD-03` **端点面**的验收断言（`/api/m03/*` JSON 动作与列表查询）。

- `ACC-PAY-ACTION-001` —— API 必须剔除「操作」列（按钮 / 表单 HTML 只在页面上成立）⇒ `§4.4.5`
- `ACC-PAY-CAT-001`    —— 批量改分类 / 恢复剔除的**动作**（落库 ＋ 回报）⇒ `§4.2.4` / `§4.2.2`
- `ACC-PAY-MANUAL-001` —— 手动行新增 / 删除 / 校验失败不落库 ⇒ `§4.2.6`
- `ACC-PAY-STAT-001`   —— 统计手改（落库 ＋ 留痕 / 超上限拦截）⇒ `§4.5.3`
- `ACC-PAY-BATCH-001`  —— 批量付款（落流水 / 幂等 / 整批不落半批 / 兜底现汇）⇒ `§4.4.4`

⚠️ 2026-09-16 自 `test_notice_actions.py` 拆出（**断言一字未改**）。
⚠️ 2026-09-19（`§19` 批 4 · **S4⑤**）：旧页删净（授权 `D18`）⇒ 原先的 **PRG 表单向用例**随之作废
   （`/m03/notices/*` 那批路由已删）。处置分两类，一条判据都没丢：
   ① 那些**已在新 JSON 端点上有对应件**的（手动行 / 统计手改 / 批量付款）⇒ 直接删掉 PRG 那半边；
   ② 「批量改分类 / 恢复剔除」三条**原先只有 PRG 面** ⇒ 本轮**如实改指 JSON API**（同一实质、换观测面）。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.mod01_projects.models import Project
from app.mod03_notice.list_data import build_page_data
from app.mod03_notice.list_view import NoticeFilters
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow.models import PaymentFlow
from tests.m03_action_helpers import _client, _notice, FakeWriteSession


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


# ============================================================ 动作端点（JSON API）
# ⚠️ 2026-09-19（`§19` 批 4 · S4⑤）：这一段原先打的是 **PRG**（`/m03/notices/*` → 303 回跳），
#    旧页删净 ⇒ 同一实质改指 JSON API。其中「手动行」与「统计手改」的新端点件本就在下文
#    （`S1`/`S2a`/`S2b` 各轮已补），故那几条 PRG 用例**直接删除**（判据由对应 API 用例承载）。


def test_API_批量改分类落库并回报():
    """**批量改分类**（§4.2.4）：真的落库 ＋ 回一句**可直接给人看**的中文（前端原样显示）。

    ⚠️ 新壳的下拉框值是**中文标签**（辅材/机械/集采），服务端只认**键**（material/…）⇒
       壳侧做映射（`CAT_API`）。本用例按服务端契约**只认键**。
    """
    client, fake = _client([_notice(1)])
    r = client.post("/api/m03/actions/category", json={"category": "mechanical", "ids": [1]})
    assert r.status_code == 200, "JSON 动作 API 一律恒 200（成败看 ok）"
    body = r.json()
    assert body["ok"] is True and body["changed"] == [1] and body["category"] == "mechanical"
    assert body["message"] == "已将 1 条改为「机械」"
    assert "warning" not in body
    assert fake.by_model[PaymentNotice][0].category == "mechanical"      # 真落库


def test_API_未勾选改分类被拒且不改库():
    """⛔ **必须先勾选**（§4.2.4：批量 = 对勾选集操作，不是对整表操作）—— 空勾选 ⇒ 拒绝且一行不动。"""
    client, fake = _client([_notice(1)])
    body = client.post("/api/m03/actions/category",
                       json={"category": "mechanical", "ids": []}).json()
    assert body["ok"] is False and "勾选" in body["message"]
    assert fake.by_model[PaymentNotice][0].category == "material"        # 原分类不变


def test_API_未勾选恢复剔除被拦():
    """「恢复剔除」同样**必须先勾选**（§4.2.2：不做整表一键放回）—— 空勾选 ⇒ 拒绝并给原因。"""
    client, _ = _client([_notice(1)])
    body = client.post("/api/m03/actions/restore", json={"ids": []}).json()
    assert body["ok"] is False and "勾选" in body["message"]


def test_API_恢复剔除真的落库且两类都放回():
    """⭐ 2026-10-08 BUG 钉子（端点层 · **落库**这一段原先全仓 0 覆盖）。

    用户报障：被规则剔除的单据点「恢复剔除」没反应。
    端点此前回 `ok:true` ＋ `restored:[]`（规则命中的被归入"不恢复"）⇒ **一行都没改**，
    而前端只弹一句回执 ⇒ 看着像按钮坏了。
    ⚠️ 判据 = **两个字段都要落库**：`excluded=False` **且** `exclude_source` 清空
    ——只清前者的话，来源还留着"规则命中"，界面与后续判断都会继续当它被剔除了。
    """
    rows = [
        _notice(1, excluded=True, exclude_source="manual"),
        _notice(2, excluded=True, exclude_source="rule"),      # ⭐ 规则命中的也要放回
        _notice(3, excluded=False, exclude_source=""),
    ]
    client, fake = _client(rows)
    body = client.post("/api/m03/actions/restore", json={"ids": [1, 2, 3]}).json()
    assert body["ok"] is True and sorted(body["restored"]) == [1, 2], \
        f"规则命中的没被恢复（这正是用户报障那条）：{body}"
    assert body["message"] == "已恢复 2 条"
    assert "warning" not in body
    got = {n.id: n for n in fake.by_model[PaymentNotice]}
    for nid in (1, 2):                                     # ⚠️ 逐条验，别只验一条
        assert got[nid].excluded is False, f"第 {nid} 条 `excluded` 没置回 False（还在剔除态）"
        assert str(got[nid].exclude_source or "") == "", \
            f"第 {nid} 条 `exclude_source` 没清空（来源还留着 ⇒ 界面继续当它被剔除）"
    assert got[3].excluded is False                        # 本就未剔除的行不受影响


@pytest.mark.parametrize("action, result_key, message", [
    ("category", "changed", "已将 1 条改为「机械」"),
    ("exclude", "marked", "已剔除 1 条"),
    ("restore", "restored", "已恢复 1 条"),
])
@pytest.mark.parametrize("missing", [False, True])
def test_API_动作仅对待处理结果返回警告(action, result_key, message, missing):
    client, _ = _client([_notice(1, excluded=action == "restore",
                                  exclude_source="manual" if action == "restore" else "")])
    payload = {"ids": [1, 99] if missing else [1], "category": "mechanical"}
    body = client.post(f"/api/m03/actions/{action}", json=payload).json()
    assert body["ok"] is True and body[result_key] == [1]
    assert body["message"] == message
    if missing:
        assert body["warning"] == message + "；1 条记录未找到，请重新读取后核对"
    else:
        assert "warning" not in body


def test_API_恢复后归属未匹配持久提示处理方式():
    client, fake = _client([_notice(1, excluded=True, exclude_source="rule", ownership_id=None)])
    body = client.post("/api/m03/actions/restore", json={"ids": [1, 99]}).json()
    assert body["ok"] is True and body["restored"] == [1]
    assert body["message"] == "已恢复 1 条"
    assert body["warning"] == (
        "已恢复 1 条；1 条记录未找到，请重新读取后核对；"
        "1 条付款项目未匹配，请到项目档案核对项目和关键词后重试"
    )
    assert fake.by_model[PaymentNotice][0].ownership_id is None


# ============================================================ 列表查询（能力 11 · 统计列的纯度）


def test_API的统计列仍不含HTML():
    """页面才注入输入框；`/api/m03/notice-list` 的显示值必须是纯文本。"""
    # ⚠️ 2026-10-01：本用例原先**不传 `filters`** ⇒ 走缺省「当月」（`default_period("notice")`），
    #    而桩件 `doc_date` 固定 `2026-09-05` ⇒ **10 月跑就被月份筛掉**（`rows` 空 ⇒ 下标越界）。
    #    ⇒ 按桩件**自己的单据月**显式给筛选：断言一字未动，只是把"今天"这个不确定因素去掉。
    n = _notice(1)
    session = FakeWriteSession({PaymentNotice: [n], Project: [], PaymentFlow: []})
    data = build_page_data(session, filters=NoticeFilters(period=str(n.doc_date)[:7]),
                           sort_col="", sort_dir=0, flows_of=lambda nid: [])
    item = {k: v for k, v in data["rows"][0].items() if k != "_row"}
    assert item["stat_settle_text"] == "10,000.00"
    assert not any("<input" in str(v) for v in item.values())


# ------------------------------------------------ `§19` 批 4 · S1：同上两条实质，改指 **JSON API**
# 原委：壳的统计手改原来只在**前端本地**改值 + 本地留痕（不落库 ✗）⇒ 接真接口 `POST /api/m03/actions/stat`；
# 旧页删除（授权 `D18`）后 PRG（上面那两条）随页消失，故**同样的实质**必须在新接口上有着落。


@pytest.mark.parametrize('manual', [False, True])
def test_API_统计手改落库并留痕(manual):
    """**统计手改走 JSON API**：值真的落库 ＋ 留痕真的写进库（壳判「黄底」的唯一事实来源）。"""
    from app.mod03_notice.models import NoticeStatLog

    client, fake = _client([_notice(1, is_manual=manual)])
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


def test_统计手改的API只许走唯一出口():
    """⛔ **防分叉**：判定 / 落库 / 文案只许一份 —— JSON API 必须调
    `notice_actions.apply_stat_change`，⛔ 不许内联 `repo.adjust_notice_stat`。

    （本仓的老毛病："同一口径只做了一半" / "两份实现悄悄漂移" ⇒ 这条就是给它立的阀门。）
    ⚠️ `§19` 批 4 · S4⑤：原先还查 PRG 那半边；旧页删净 ⇒ 观测面收敛到本 API。
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    api = (root / "backend" / "app" / "mod03_notice" / "notice_api_router.py").read_text(encoding="utf-8")
    assert "apply_stat_change(" in api, "统计手改的 API 没走唯一出口"
    assert "repo.adjust_notice_stat(" not in api, "API 内联了落库/判定（应共用唯一出口）"
    assert "def apply_stat_change(" in (
        root / "backend" / "app" / "mod03_notice" / "notice_actions.py"
    ).read_text(encoding="utf-8"), "唯一出口本身没了"


# ------------------------------------------------ `§19` 批 4 · S2a：手动行新增/编辑走 **JSON API**
# 原委：壳的「手动新增 / 编辑」原来只在前端本地 `NO.push` / `Object.assign`（**不落库** ✗）⇒ 接真接口。


@pytest.mark.parametrize('settle', [None, '20000'])
def test_API_新增手动行落库(settle):
    """省略结算仍为0，显式金额原样校验并落库。"""
    client, fake = _client([_notice(1)])
    r = client.post("/api/m03/actions/manual-save", json={
        "doc_date": "2026-09-01", "bill_no": "MN01", "bill_name": "期初占位",
        "biz_type": "付其他供应商款", "payee": "某供应商", "category": "material",   # ⚠️ 服务端只认**键**（辅材/机械/集采是显示名）
        "amount_approved": "50000", "stat_paid": "20000",
        **({'stat_settle': settle} if settle is not None else {}),
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["is_new"] is True
    added = [x for x in fake.added if isinstance(x, PaymentNotice)]
    assert len(added) == 1, "接口说成功但一行都没落库"
    assert added[0].is_manual is True
    assert added[0].stat_settle == Decimal(settle or '0')
    assert added[0].stat_paid == Decimal("20000.00")
    assert "已新增" in body["message"] and "按单据日期计入台账" in body["message"]


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


def test_API_编辑手动行按改动字段回报():
    """编辑走**同一套**（§4.2.6）：只改传进来的那几列，回执报「改动 N 个字段」。"""
    client, fake = _client([_notice(1, is_manual=True, ph_id="MN01")])
    r = client.post("/api/m03/actions/manual-save", json={
        # ⚠️ 数字必须自洽：全站口径「统计两金额 ≤ 审批金额」（超了后端会正确地拦下）
        "row_id": "1", "doc_date": "2026-09-05", "stat_paid": "30000",
        "amount_approved": "50000", "stat_settle": "20000", "category": "material",
    })
    body = r.json()
    assert body["ok"] is True and body["is_new"] is False
    assert "改动" in body["message"] and "个字段" in body["message"]
    row = fake.by_model[PaymentNotice][0]
    assert row.stat_paid == Decimal("30000.00")
    assert row.stat_settle == Decimal("20000.00")
    assert [x for x in fake.added if isinstance(x, PaymentNotice)] == [], "编辑不该新增行"


def test_手动行保存的API只许走唯一出口():
    """⛔ **防分叉**：手动行的校验 / 落库 / 文案只许一份 —— JSON API 必须调
    `notice_manual_actions.apply_manual_save`，⛔ 不许内联 `repo.create_manual_notice` / `update_manual_notice`。"""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    api = (root / "backend" / "app" / "mod03_notice" / "notice_api_router.py").read_text(encoding="utf-8")
    assert "apply_manual_save(" in api, "手动行保存的 API 没走唯一出口"
    for banned in ("repo.create_manual_notice(", "repo.update_manual_notice("):
        assert banned not in api, f"API 内联了落库（应共用唯一出口）：{banned}"


# ------------------------------------------------ `§19` 批 4 · S2b：删除 ＋ **删除前的影响范围**
# §7.2 / §9.4 是硬要求：**删除前必须列出影响范围**（关联数据、统计影响）⇒ 由后端给，壳原样显示。


def test_API_删除手动行成功():
    """**删除手动行走 JSON API**：真的落库（`session.delete`），文案由后端给。"""
    client, fake = _client([_notice(1, is_manual=True, ph_id="MN01")])
    r = client.post("/api/m03/actions/manual-delete", json={"notice_id": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and "已删除手动行" in body["message"]
    assert [x for x in fake.deleted if isinstance(x, PaymentNotice)], "接口说成功但没删"
    assert fake.by_model[PaymentNotice] == []


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


def test_手动行删除的API只许走唯一出口():
    """⛔ **防分叉**：删除的校验 / 落库 / 文案只许一份 —— JSON API 必须调
    `notice_manual_actions.apply_manual_delete`，⛔ 不许内联 `repo.delete_notice`。"""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    api = (root / "backend" / "app" / "mod03_notice" / "notice_api_router.py").read_text(encoding="utf-8")
    assert "apply_manual_delete(" in api, "手动行删除的 API 没走唯一出口"
    assert "repo.delete_notice(" not in api, "API 内联了删除（应共用唯一出口）"


# ------------------------------------------------ `§19` 批 4 · S3：批量付款走 **JSON API**
# 这四条原先**卡着**（壳里没有落库 ⇒ 搬过去就是假绿）⇒ 接真接口后才**如实**落到这里。
# ⚠️ 语义变化要说清：动作改走后端之后，「取消」= **不调接口**（不再有服务端状态要回滚）。


def test_API_批量付款落流水且一条付款一条流水():
    """**落库**：一条勾选 ⇒ **一条**独立流水，金额 / 方式 / 单据号 / **`request_id`** 都要对。"""
    from app.mod05_flow.models import PaymentFlow

    client, fake = _client([_notice(1, bill_no="D1")])
    r = client.post("/api/m03/actions/batch-pay", json={
        "ids": [1], "drafts": {"1": {"pay_method": "承兑", "amount": "300"}},
        "pay_date": "2026-09-10", "request_id": "R-1",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["count"] == 1
    flows = [f for f in fake.added if isinstance(f, PaymentFlow)]
    assert len(flows) == 1, "接口说成功但没落流水"
    assert flows[0].amount == Decimal("300.00") and flows[0].notice_id == 1
    assert flows[0].pay_method == "承兑" and flows[0].request_id == "R-1"
    assert "已登记 1 条付款流水" in body["message"]


def test_API_重复提交被拒():
    """§4.4.4：**同一个 `request_id` 再提交 ⇒ 拒绝**，且**只产生一条**流水（幂等的意义就在这）。"""
    from app.mod05_flow.models import PaymentFlow

    client, fake = _client([_notice(1)])
    payload = {"ids": [1], "drafts": {"1": {"amount": "10"}},
               "pay_date": "2026-09-10", "request_id": "R-5"}
    assert client.post("/api/m03/actions/batch-pay", json=payload).json()["ok"] is True
    second = client.post("/api/m03/actions/batch-pay", json=payload).json()
    assert second["ok"] is False and "重复提交" in second["message"]
    assert len([f for f in fake.added if isinstance(f, PaymentFlow)]) == 1


def test_API_提交时库中已变不可付则整批不落():
    """兜底：窗口打开时是「已批」、提交时库里已变「未批」⇒ **整批不落**（不产生任何流水）。"""
    from app.mod05_flow.models import PaymentFlow

    client, fake = _client([_notice(1, approve_status="未批")])
    body = client.post("/api/m03/actions/batch-pay", json={
        "ids": [1], "drafts": {"1": {"amount": "100"}},
        "pay_date": "2026-09-10", "request_id": "R-2",
    }).json()
    assert body["ok"] is False and body["message"]
    assert [f for f in fake.added if isinstance(f, PaymentFlow)] == []


def test_API_付款方式缺省时兜底现汇():
    """§4.4.2：**默认取付款计划的值、取不到兜底「现汇」** —— 这里守"兜底"那半边
    （取计划那半边由 `default_pay_method` 的纯函数断言守着，见 `test_wired_m03_pay.py`）。"""
    from app.mod05_flow.models import PaymentFlow

    client, fake = _client([_notice(1, bill_no="没有计划的行")])
    body = client.post("/api/m03/actions/batch-pay", json={
        "ids": [1], "drafts": {"1": {"amount": "10"}},
        "pay_date": "2026-09-10", "request_id": "R-6",
    }).json()
    assert body["ok"] is True
    flows = [f for f in fake.added if isinstance(f, PaymentFlow)]
    assert flows and flows[0].pay_method == "现汇", "取不到计划值时应兜底「现汇」"


def test_批量付款的API只许走唯一出口():
    """⛔ **防分叉**：批量付款的整条管线（整批重算 / 不落半批 / 幂等 / 落流水）只许一份
    —— JSON API 必须调 `notice_pay_actions.apply_batch_pay`。

    ⚠️ `§19` 批 4 · S4⑤：原先还查 PRG（`notice_pay_router.py`）那半边；旧页删净 ⇒ 收敛到本 API。
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    api = (root / "backend" / "app" / "mod03_notice" / "notice_api_router.py").read_text(encoding="utf-8")
    assert "apply_batch_pay(" in api, "批量付款的 API 没走唯一出口"
    assert "flow_repo.create_flow(" not in api, "API 内联了落流水（应共用唯一出口）"
    assert "confirm_batch(" not in api, "API 内联了判定（应共用唯一出口）"


@pytest.mark.parametrize('remark', ['本批付款备注：补材料款', ''])
def test_批量付款备注保存到每条流水(remark):
    from app.mod05_flow.models import PaymentFlow

    client, fake = _client([_notice(1, bill_no='D1'), _notice(2, bill_no='D2')])
    result = client.post('/api/m03/actions/batch-pay', json={
        'ids': [1, 2], 'drafts': {'1': {'amount': '10'}, '2': {'amount': '20'}},
        'pay_date': '2026-10-13', 'remark': remark, 'request_id': 'R-remark',
    }).json()
    assert result['ok'] is True and result['count'] == 2
    flows = [f for f in fake.added if isinstance(f, PaymentFlow)]
    assert len(flows) == 2
    assert [f.remark for f in flows] == [remark, remark]


def test_API_rule_hint_uses_current_config_without_changing_exclusion():
    from app.mod03_notice.models import ExcludeRuleRow
    client, fake = _client([
        _notice(1, excluded=True, exclude_source='rule', input_by='张三'),
        _notice(2, excluded=True, exclude_source='rule', input_by='李四'),
        _notice(3, excluded=True, exclude_source='manual', input_by='张三'),
    ])
    fake.by_model[ExcludeRuleRow] = [ExcludeRuleRow(id=1, ord=0, kind='input_by', values='张三')]
    items=client.get('/api/m03/notice-list',params={'period':''}).json()['items']
    by_id={n['notice_id']:n for n in items}
    assert '录入人（张三）' in by_id[1]['exclude_rule_hint']
    assert '历史命中规则未保存' in by_id[1]['exclude_rule_hint']
    assert '当前无匹配规则' in by_id[2]['exclude_rule_hint']
    assert by_id[3]['exclude_rule_hint']==''
    assert all(n.excluded for n in fake.by_model[PaymentNotice])
