"""`TAIL-04` 的**最后两页**（`MOD-03` 付款通知书台账 · `MOD-04` 付款计划审查结果）＋ ⭐ **`exp` 真分发**。

绑 `ACC-X-EXP-001/001-01`（**逐页都有导出入口**）与 `001-08`（**导出内容须与当前筛选一致**）——
⚠️ 这两条**早已有主**（`test_acc_x_exp.py` / `test_path1_weldgas.py`）；本件是**加绑**，
   不是抢注：`acc_report` 对"一据点多测试"的口径是**有红即红,否则绿**（`acc_report.py` L129）。
   ⭐ 为什么必须加绑：那两条此前**只在路径①（模板填充）那几页成立** ——
   4 个列表页的按钮按下去只弹「尚未落地」（`exp` 那时是一条诚实提示）⇒
   "逐页都有导出入口"其实**没有落点**，"与当前筛选一致"更无从谈起。本件把它补上。

⚠️ **本件守的三件"会静默失效"的事**（都踩过同类）：
1. **导出列与页面表头脱钩** —— 页面加了一列、导出没跟 ⇒ 表与屏幕对不上，**不报错**；
2. **合计行口径** —— `MOD-03` 只合「有效行」（`NoticeRow.is_live`）、`MOD-04` 只合**两列**；
   写错就是**悄悄多算/少算几笔**（`list_data.summary_row` 就是这么错了好几个月）；
3. **`pjVisible` 与 `V.m01` 的筛选失配** —— 两份是**故意**的（理由见 `core.js` 那段注释），
   所以**必须钉住**它们逐字一致；否则导出的是"另一个筛选"的结果，**页面上一点看不出来**。
"""

from __future__ import annotations

import base64
import io
import re

import openpyxl
import pytest
from tests._auth import TestClient          # ⭐ 带会话票（见该件注释）

from app.main import create_app
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_api_router import get_session
from app.report_export import nt_export, pl_export
from tests.acc_plugin import acc
from tests.m03_action_helpers import FakeWriteSession, _notice
from tests.shell_load_helpers import exp_routes
from tests.shell_src import SHELL, const_src  # noqa: F401  ← `P4`① 读取点收敛

#: 壳里的 `data-act="exp"` 按钮的 `data-t`（**真源 = `index.html`**，本表只在测试里对账用）。
#: ⚠️ 2026-09-21：`i8 接口清单` 的卡片已随「接口清单删除」裁定移除（m02 清单卡）⇒ 从本表摘除。
#: ⚠️ 2026-09-28（`TAIL-124`）：`全量台账` 摘除 —— 那是 `m13` 「演示导出」枚假按钮的落点，
#:    本批把整页改成用户视角时把它删了（`m13` 无自有数据源 ⇒ 不设导出入口）。
BUTTON_T = (
    "付款通知书台账", "付款计划审查结果", "付款流水", "项目档案",
    "过程资料", "库存单据明细总表", "差异清单", "集采台账",
)


def _th_labels(name: str) -> list[str]:
    """从壳的 `<th>` 串（`NT_THEAD` / `PL_THEAD`）抽**列名** —— 去掉 HTML 标签与 JS 注释。

    ⭐ 2026-10-03（`TAIL-219` 批 2b）：取句改走壳的语义口径 `const_src`（⛔ 别在本件再写正则）。
    """
    raw = re.sub(r"/\*.*?\*/", "", const_src(name), flags=re.S)
    return [re.sub(r"<[^>]+>", "", t).strip()
            for t in re.findall(r"<th\b[^>]*>(.*?)</th>", raw, re.S)]


def _export_labels(columns) -> list[str]:
    return [label for label, _ in columns]


def _read(blob: bytes) -> tuple[list[str], list[tuple]]:
    """成品字节 ⇒ `(表头, 全部数据行)`（含合计行）。"""
    wb = openpyxl.load_workbook(io.BytesIO(blob))
    ws = wb.active
    rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
    return list(rows[0]), rows[1:]


def _row_by_first(rows: list[tuple], first) -> tuple:
    hit = [r for r in rows if r[0] == first]
    assert hit, f"成品里找不到首格为 {first!r} 的行（现有首格：{[r[0] for r in rows]}）"
    return hit[0]


# ============================================================== 001-01 · 逐页都有导出入口


@acc("ACC-X-EXP-001", "001-01")
def test_四个列表页的导出按钮都已真分发():
    """claim：「**逐页**都有导出入口」—— ⚠️ 本件补的是**"入口真的通到后端"**那一半。

    ⚠️ 「有个按钮」不等于「有导出入口」：改之前 4 个按钮按下去只弹「尚未落地」
       （`test_acc_x_exp.py` 那条按 claim 的字面只验"按钮在不在页面上"，
        它**看不见**按钮通到哪儿 —— 这正是本件存在的理由）。

    ⚠️ 断言**两端都要**：① 页面上有按钮（`data-t` 在）；② 分发表里那一条**指向本模块的端点**
       （`U4` 的同款精神：⛔ 光有 `url` 字段、指到别处也算没接）。
    """
    routes = exp_routes()
    # ① 页面上那 9 个 `data-t` 与测试里登记的名单**双向**钉住（冒出新的 / 少了一个都红）
    on_page = set(re.findall(r'data-act="exp" data-t="([^"]+)"', SHELL))
    assert on_page == set(BUTTON_T), (
        f"壳里的 `data-act=\"exp\"` 按钮名单变了：{sorted(on_page ^ set(BUTTON_T))} —— "
        "⚠️ 这不是「名单过期」，是**有页新增 / 删除了导出按钮** "
        "⇒ 同步本名单，并想清楚那一页接不接后端（不接就得走兜底说实话）")

    # ② 接上的那 4 页：端点必须是**本模块**的（⛔ 别指到别的页去）
    want = {
        "项目档案": "/api/m01/projects/export",
        "付款流水": "/api/m05/flows/export",
        "付款通知书台账": "/api/m03/notices/export",
        "付款计划审查结果": "/api/m04/plans/export",
    }
    assert routes == want, (
        "`EXP_ROUTES` 与登记不符：\n"
        f"  壳里  = {routes}\n  期望 = {want}\n"
        "⇒ 要么新增页没登记，要么有人把某页接到了**别的**端点（那种错页面上看不出来）")

    # ③ 没接的页**必须在页面上说实话**（⛔ 不许静默：那 5 个按钮的落点逐个都要有交代）
    for t in set(BUTTON_T) - set(routes):
        assert t not in routes, t
    # ⚠️ 2026-09-27（守则 §2.2/§3.1 · `TAIL-117` 批次 2）：「尚未落地」换成人话「还没有导出功能」
    #    （原措辞带内部台账编号与后端术语）⇒ token 同步，**"必须诚实兜底"这条口径一字未改**。
    # ⚠️ 2026-09-28（`TAIL-124`）：`m13` 那枚「演示导出」按钮**已删**（它本来就是"点了只弹兜底提示"的
    #    假按钮）⇒ 它**不再是**这条兜底的消费者；⛔ 别据此以为兜底可以删 —— 上面那几页仍在。
    assert "还没有导出功能" in SHELL, (
        "兜底那句「这一页还没有导出功能」不见了 —— 没落点的页（i8 接口清单 / 库存单据朴素那份 / "
        "过程资料朴素那份 / 已取消的差异清单）就只剩沉默或假成功")


@acc("ACC-X-EXP-001", "001-01")
def test_两个新端点都挂上了():
    """⭐ "已接"必须**有落点**：两个端点真的在 FastAPI 的路由表里（⛔ 不是只有函数名）。

    ⚠️ 本版 FastAPI 把 `include_router` 的结果包成 `_IncludedRouter`（`app.routes` 里读不到 `path`）
       ⇒ 一律查 OpenAPI 表（`app.routes` 那条路本轮实测走不通）。
    """
    paths = set(create_app().openapi()["paths"])
    for p in ("/api/m03/notices/export", "/api/m04/plans/export"):
        assert p in paths, f"{p} 没挂上 —— 按钮按下去只会 404"
        assert "post" in create_app().openapi()["paths"][p], f"{p} 不是 POST（壳侧发的是 POST）"


# ============================================================== 列 = 页面表头


@acc()
def test_导出列就是页面表头去掉勾选与操作():
    """⭐ 导出的列**不是**在这里"设计"的 —— 它必须**逐字等于页面表头**去掉「勾选 / 操作」。

    ⚠️ 为什么这条最重要：页面加一列/改一个列名、导出没跟 ⇒ **表与屏幕对不上号**，
       而且**没有任何报错**（本项目最怕的那类）。⇒ 用一个**单向真源**（`SHELL` 里的 `NT_THEAD` /
       `PL_THEAD`）来钉，⛔ 别用"两边都手写一遍再比"（那只是把同一份错抄两遍）。
    ⚠️ `✎`（`付款金额 ✎` 那三列）**必须留着** —— 它是页面表头原文，
       洗净了表头就对不上屏幕（口径见 `nt_export` 模块头）。
    """
    nt_page = _th_labels("NT_THEAD")
    assert nt_page[0] == "" and nt_page[-1] == "操作", f"`NT_THEAD` 首/末列不是预期：{nt_page}"
    assert _export_labels(nt_export.COLUMNS) == nt_page[1:-1], (
        "`nt_export.COLUMNS` 与 `NT_THEAD`（去掉勾选 / 操作）不一致 —— 表与屏幕对不上号了")

    pl_page = _th_labels("PL_THEAD")
    assert pl_page[0] == "" and pl_page[-1] == "操作", f"`PL_THEAD` 首/末列不是预期：{pl_page}"
    assert _export_labels(pl_export.COLUMNS) == pl_page[1:-1], (
        "`pl_export.COLUMNS` 与 `PL_THEAD`（去掉勾选 / 操作）不一致")


# ============================================================== 001-08 · 合计行口径


def _nt_export_row(**kw) -> dict:
    """一行**导出值**（键 = `nt_export.COLUMNS` 的第二项）。"""
    base = dict(doc_date="2026-09-05", bill_no="B1", project_display="甲仓", category_text="辅材",
                bill_name="材料款", biz_type="付其他供应商款", payee="某供应商", jc_supplier="",
                input_by="王潜森", amount_approved="100.00", pay_amount="60.00",
                amount_paid="40.00", stat_settle="100.00", stat_paid="40.00",
                approve_status="已批", pay_status="未付清")
    base.update(kw)
    return base


@acc("ACC-X-EXP-001", "001-08")
def test_付款通知书导出的合计只算有效行():
    """claim：「导出内容须与当前筛选一致」—— 本件补的是**合计行**那一半（§4.2.7）。

    ⚠️ **合计不是"把导出的行加起来"** —— 页面 `sumRowOf(NT_THEAD, list.filter(ntLive), …)`：
      · **剔除行不计入**（§4.2.2「别算我」）；
      · ⚠️ **但"有牵涉的撤单行"仍要计入** —— i8 侧单据被删、可本系统里还挂着付款流水 ⇒
        **不许静默丢账**（§4.2.7），得等人处理完它才退场。
    ⇒ 两条**方向相反**，只写其中一条就是**悄悄少算/多算**。
    ⚠️ 反向也要钉：**一行有效行都没有 ⇒ 不写合计行**（切到「分类 = 剔除」时页面就没有合计行，
       ⛔ 凭空补一排 0 = 假值）。
    """
    live = _nt_export_row(amount_approved="100.00")
    excluded = _nt_export_row(amount_approved="1000.00")                      # 剔除 ⇒ 不算
    revoked_free = _nt_export_row(amount_approved="1000.00")                  # 撤单无牵涉 ⇒ 不算
    revoked_joint = _nt_export_row(amount_approved="500.00")                  # 撤单有牵涉 ⇒ **算**
    blob = nt_export.build_xlsx(
        [live, excluded, revoked_free, revoked_joint], live_rows=[live, revoked_joint])

    _, rows = _read(blob)
    total = _row_by_first(rows, "合计")
    approved_i = _export_labels(nt_export.COLUMNS).index("审批金额")
    assert total[approved_i] == pytest.approx(600.00), (
        f"合计 = {total[approved_i]}，应为 100 ＋ 500 = 600 —— "
        "把剔除行算进来（=1000 那两行之一）或漏掉「撤单有牵涉」那一档都会得到别的数")

    # 反向：一行有效行都没有 ⇒ **没有合计行**（页面同口径）
    blob2 = nt_export.build_xlsx([excluded], live_rows=[])
    _, rows2 = _read(blob2)
    assert [r[0] for r in rows2] != ["合计"], "一行有效行都没有却写了合计行 —— 那是一排凭空捏造的 0"
    assert len(rows2) == 1, f"不该多出行：{rows2}"


@acc()
def test_is_live两条口径方向相反且都成立():
    """`NoticeRow.is_live` 的四挡（⛔ 它是**唯一出口**，导出与统计都吃它）。"""
    def _r(**kw):
        base = dict(excluded=False, i8_revoked=False, amount_paid=0, has_link=False)
        base.update(kw)
        return base

    from app.mod03_notice.list_view import NoticeRow

    def live(**kw) -> bool:
        return NoticeRow(notice_id=1, **_r(**kw)).is_live

    assert live() is True, "正常行必须算有效"
    assert live(excluded=True) is False, "剔除行不计入（§4.2.2）"
    assert live(i8_revoked=True) is False, "撤单且无牵涉 ⇒ 退出统计（§4.2.7）"
    assert live(i8_revoked=True, amount_paid=1) is True, \
        "撤单但**挂着付款流水** ⇒ 仍算有效（§4.2.7：不许静默丢账）"
    assert live(i8_revoked=True, has_link=True) is True, \
        "撤单但**挂着集采关联** ⇒ 仍算有效（同上）"


# ============================================================== 001-08 · 行集与顺序


@acc("ACC-X-EXP-001", "001-08")
def test_付款计划导出的合计只合两列且未命中留空():
    """`MOD-04` 的合计口径与 `MOD-03` **不一样**，照抄就会错：

    · 页面 `sumRowOf(PL_THEAD, list, {5:…, 8:…})` ⇒ **只合「i8 流程金额」与「本月预付款金额」**；
    · 「已付款金额 / 剩余付款金额」是**金额**（要写数字，Excel 里能求和）但**页面不合计它们**
      —— `naive_export` 把"写数字"（`MONEY_KEYS`）与"要合计"（`TOTAL_KEYS`）拆成两个集合正是为此。
    · 单据号**没命中** i8 通知书 ⇒ 那两列在页面上是「—」⇒ 导出**留空**（⛔ 不写 0 ——
      "没这个数"与"是 0"是两件事）。
    """
    rows = [{
        "id_text": "7", "year_month": "2026-09", "project_text": "甲仓", "doc_no": "D1",
        "flow_amount": "1000.00", "paid_amount": "400.00", "unpaid_amount": "600.00",
        "planned_amount": "300.00", "pay_date": "2026-09-10", "pay_method": "现汇",
        "remark": "", "audit_text": "完全匹配", "handle_text": "无需处理",
    }, {
        "id_text": "8", "year_month": "2026-09", "project_text": "乙仓库（未匹配）", "doc_no": "",
        "flow_amount": "2000.00", "paid_amount": "", "unpaid_amount": "",
        "planned_amount": "100.00", "pay_date": "", "pay_method": "", "remark": "",
        "audit_text": "单据号查不到", "handle_text": "未处理",
    }]
    _, got = _read(pl_export.build_xlsx(rows))
    labels = _export_labels(pl_export.COLUMNS)
    total = _row_by_first(got, "合计")
    assert total[labels.index("i8 流程金额")] == pytest.approx(3000.00)
    assert total[labels.index("本月预付款金额")] == pytest.approx(400.00)
    # ⚠️ openpyxl 把**空格子**读成 `None`（⛔ 不是 `""`）—— 判"留空"要认这两种
    for col in ("已付款金额", "剩余付款金额"):
        assert total[labels.index(col)] in ("", None), \
            f"「{col}」被合计了 —— 页面**不合计**这两列（凭空多出两个数）"
    # 未命中那行：留空，⛔ 不写 0；且金额列**是数字**（Excel 里能求和/排序）
    r2 = _row_by_first(got, "8")
    assert r2[labels.index("已付款金额")] in ("", None) and r2[labels.index("剩余付款金额")] in ("", None)
    assert isinstance(r2[labels.index("i8 流程金额")], (int, float)), "金额列写成了字符串（Excel 里没法求和）"


@acc()
def test_付款计划导出的项目列与处理列按页面口径():
    """「项目」与「处理」两列在页面上**不是**一个字段，而是"并进一格"的产物 —— 逐条照抄。

    · 项目：**唯一命中 ⇒ 展示名**；0 命中 ⇒ 填报原值 ＋「未匹配」；多命中 ⇒ 填报原值 ＋「重名 N 条」；
    · 处理：完全匹配 ⇒ 「无需处理」；已强制 ⇒ **强制备注**（页面那格显示的就是它）；否则 ⇒ 「未处理」。
      ⚠️「未处理」**不是新造的词** —— 页面口径说明与「取消强制通过」按钮的提示语都写「回到「未处理」态」。
    """
    from app.mod04_plan.router import _export_row

    matched = _export_row(dict(id=1, audit_result="完全匹配", match_status="matched",
                               project_input="甲仓", project_display="甲公司仓库",
                               forced_through=False, forced_remark="", is_manual=False))
    assert matched["project_text"] == "甲公司仓库", "唯一命中必须显示**展示名**（不是填报原值）"
    assert matched["handle_text"] == "无需处理"
    assert matched["audit_text"] == "完全匹配"

    unmatched = _export_row(dict(id=2, audit_result="单据号查不到", match_status="unmatched",
                                 project_input="查无此仓", match_candidates=0, is_manual=True))
    assert unmatched["project_text"] == "查无此仓（未匹配）"
    assert unmatched["handle_text"] == "未处理", "没强制过 ⇒ 未处理（页面上那格是个按钮，不是数据）"
    assert unmatched["id_text"] == "2（手动）", "手动徽标要并进同一格（另开一列就跟屏幕对不上号）"

    amb = _export_row(dict(id=3, audit_result="金额不符", match_status="ambiguous",
                           project_input="重名仓", match_candidates=3))
    assert amb["project_text"] == "重名仓（重名 3 条）"

    forced = _export_row(dict(id=4, audit_result="金额不符", match_status="matched",
                              project_input="甲仓", project_display="甲公司仓库",
                              forced_through=True, forced_remark="项目已确认"))
    assert forced["audit_text"] == "金额不符（已强制通过）", "强制标记要并进审查结果那格（页面就是并进去的）"
    assert forced["handle_text"] == "项目已确认", "已强制 ⇒ 那格显示的是**强制备注**"


@acc("ACC-X-EXP-001", "001-08")
def test_付款通知书端点按传入id顺序出行且合计只算有效行():
    """⭐ **行 = 传入的那些 id**（⛔ 不是全表）· **顺序 = 传入顺序**（= 屏幕上的行序）
    · **合计只算有效行**。

    ⚠️⚠️ **必须打端点、⛔ 不能直接喂 `nt_export.build_xlsx`**：那样 `live_rows` 是**测试自己算的**，
       `NoticeRow.is_live` 那条口径就**没人守**了（实测：把 `is_live` 改成恒真，直喂版**仍然全绿**，
       是一处**假绿**——反向灵敏度第 6 条抓到）。⇒ 本件走 `POST /api/m03/notices/export`，
       `is_live` 才真的在链路上。
    ⚠️ **剔除行要放进传入的 id 里**（模拟用户切到「分类 = 剔除」再看）：否则"剔除不计入"这条
       **根本没被验到**（它不在行集里，算不算都看不出来）。

    造数四挡（`is_live` 的正反面都要有）：
      · `B1` 正常 ⇒ **算**；· `B2` 剔除 ⇒ 不算（§4.2.2）；
      · `B3` i8 撤单、无牵涉 ⇒ 不算；· `B4` i8 撤单、**挂着生效流水** ⇒ **仍算**（§4.2.7 不许静默丢账）。
    合计（审批金额）= `B4 500 ＋ B1 100 = 600`；⚠️ 若剔除行被算进来会得 **1600**。
    """
    from decimal import Decimal

    from tests.m03_action_helpers import _client
    from tests.m05_helpers import make_flow

    notices = [
        _notice(1, bill_no="B1", amount_approved=Decimal("100.00")),
        _notice(2, bill_no="B2", excluded=True, amount_approved=Decimal("1000.00")),
        _notice(3, bill_no="B3", i8_revoked=True, amount_approved=Decimal("1000.00")),
        _notice(4, bill_no="B4", i8_revoked=True, amount_approved=Decimal("500.00")),
    ]
    flows = [make_flow(1, notice_id=4, amount="30.00")]     # 第 4 行**有牵涉** ⇒ 仍算有效
    client, _ = _client(notices, flows=flows)

    r = client.post("/api/m03/notices/export", json={"ids": [2, 4, 1]})
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    body = r.json()
    assert body["rows"] == 3, f"应当只导传入的 3 行（库里有 4 行）：{body['rows']}"
    labels, got = _read(base64.b64decode(body["content_b64"]))
    codes = [row[labels.index("单据编码")] for row in got[:3]]
    assert codes == ["B2", "B4", "B1"], f"行序没跟传入 id 走（实得 {codes}）"
    total = _row_by_first(got, "合计")
    assert total[labels.index("审批金额")] == pytest.approx(600.00), (
        f"合计 = {total[labels.index('审批金额')]}，应为 500 ＋ 100 = 600 —— "
        "算成 1600 是把**剔除行**也算进来了（§4.2.2）；算成 100 是漏了「撤单但有牵涉」那一档")
    assert body["filename"].startswith("付款通知书台账_") and body["filename"].endswith(".xlsx")


@acc("ACC-X-EXP-001", "001-08")
def test_付款计划端点按传入id顺序出行且未命中留空():
    """同上，`MOD-04` 那侧 —— 取数走 `Depends(get_page_data)`（可注入 ⇒ 离线）。

    ⚠️ 同样**必须打端点**：`paid_amount` / `unpaid_amount` 那两个「未命中 ⇒ 留空」是由
       `router._export_row` 决定的 —— 直喂 `pl_export.build_xlsx` 就把它绕过去了
       （反向灵敏度第 11 条实测：改成写 `0` 仍全绿）。
    """
    import app.mod04_plan.router as m04_router

    rows = [{"id": i, "year_month": "2026-09", "project_input": f"仓{i}", "match_status": "unmatched",
             "match_candidates": 0, "doc_no": f"D{i}", "flow_amount": "1.00", "paid_amount": "",
             "unpaid_amount": "", "planned_amount": "1.00", "pay_date": "", "pay_method": "",
             "remark": "", "audit_result": "完全匹配", "forced_through": False,
             "forced_remark": "", "is_manual": False} for i in (1, 2, 3)]
    app = create_app()
    app.dependency_overrides[m04_router.get_page_data] = lambda: (lambda **kw: {"rows": rows})
    client = TestClient(app)
    r = client.post("/api/m04/plans/export", json={"ids": [3, 2]})
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    body = r.json()
    assert body["rows"] == 2
    labels, got = _read(base64.b64decode(body["content_b64"]))
    assert [row[0] for row in got[:2]] == ["3", "2"], f"行序没跟传入 id 走：{[row[0] for row in got]}"
    # 未命中的派生两列 **留空**（⛔ 不写 0：「没这个数」与「是 0」是两件事 —— 铁律四）
    assert got[0][labels.index("已付款金额")] in ("", None), \
        "未命中却写了 0 —— 「没这个数」被装成了「是 0」"
    assert got[0][labels.index("剩余付款金额")] in ("", None)


# ============================================================== 壳侧：pjVisible ⇄ V.m01


def _strip_js_comments(seg: str) -> str:
    """去掉 JS 注释 —— ⚠️ **必须先去掉**：`pjVisible` 上面那段注释里**逐字引了**这三件套
    （「`const TYPE=…; const q=…; const rows=pjSort(PJs.filter(p=>…));`（逐字见下）」），
    不去掉就会先匹配到**注释里那一份**，得到恒等的假绿。"""
    seg = re.sub(r"/\*.*?\*/", "", seg, flags=re.S)
    return re.sub(r"//[^\n]*", "", seg)


def _filter_bits(text: str) -> tuple[str, str, str]:
    """从一段 JS 里抽「筛选三件套」：`TYPE` 映射 / `q` / `PJs.filter(...)` —— 去注释、**归一化空白**。"""
    t = re.sub(r"\s+", "", _strip_js_comments(text))
    type_m = re.search(r"constTYPE=(\{[^{}]*\})\[fPj\.type\]\|\|'';", t)
    q_m = re.search(r"constq=fPj\.q\.trim\(\);", t)
    filt = re.search(r"PJs\.filter\(p=>.*?\);", t)
    assert type_m and q_m and filt, f"筛选三件套抽不出来（形态变了就同批改本件）：{t[:200]}"
    return type_m.group(1), q_m.group(0), filt.group(0)


@acc()
def test_项目档案的可见行出口与V_m01的筛选逐字一致():
    """⭐ `pjVisible()`（导出用）与 `V.m01` 里那段内联筛选**必须逐字一致**。

    ⚠️⚠️ **这是"故意存在的第二份"** —— 为什么不把 `V.m01` 改成调 `pjVisible()`：`V.` 切片是
       `ui_parity` 的 `U1` 逐行比对的**原件**，配对的原型在「面」；改一处要同改另一处，
       还会连带原型导读的逐页「行号区间 + 行数」表、`_smoke` 四检、追溯表、验收基线
       （理由与出处见 `core.js` 里 `pjVisible` 上面那段注释）。
    ⇒ 于是**用这条测试当保险**：谁只改一处，这里当场点名。
       ⛔ 别把它当"重复代码告警"删掉 —— 删了之后，导出会**静默地**按另一套筛选出行，
          而页面上**一点看不出来**（正是本项目最贵的那类错）。
    """
    i = SHELL.index("V.m01=()=>{")
    v_body = SHELL[i:SHELL.index("const typeTag=", i)]
    j = SHELL.index("const pjVisible = () => {")
    p_body = SHELL[j:SHELL.index("function adaptProject(", j)]
    assert _filter_bits(v_body) == _filter_bits(p_body), (
        "`pjVisible()` 与 `V.m01` 的筛选条件**不一致**了 —— 两处必须一起改：\n"
        f"  V.m01    = {_filter_bits(v_body)}\n  pjVisible = {_filter_bits(p_body)}")
