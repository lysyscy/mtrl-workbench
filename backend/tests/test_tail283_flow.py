"""`TAIL-283`：付款流水**补通知书五项** ＋ 改对「操作人 / 流水号」两处列义（装配层 ＋ 导出逐格）。

**它守什么**（票面验收）：
  ① 五项通知书信息（日期 / 名称 / 收款单位 / 审批金额 / 分类）由 `_flow_dict` 用**一次预读**的
     通知书字典装配 ⇒ ⛔ 不逐行查库（本件用「执行次数不随行数增长」钉住）；
  ② 「操作人」= `created_by`；「流水号」= 真 `flow_no` —— 页面看到的、Excel 导出的、搜索匹配的**同一件事**；
  ③ **合计只加实付**（审批金额在同通知书的每笔上重复出现 ⇒ 纵向加起来是假数）；
  ④ `notice_id` 为空 / 指向已删除通知书的流水**照旧能查**，新列留空、审批金额 `None`（⛔ 不伪 0，
     而**真等于 0** 写 `0.00`）；
  ⑤ 导出走**全量装配**（页面上看得见的历史月份流水，导出来不许是空的）。

⚠️ 与 `test_acc_flow_list.py` 的分工：那件守**域内核**（筛选 / 合计 / 撤销），本件守**装配与导出**。
"""
from __future__ import annotations

import base64
import io

import openpyxl

from app.main import create_app
from app.mod05_flow import service as svc
from app.mod05_flow.models import CATEGORY_JC, CATEGORY_MATERIAL, FLOW_REVOKED, PaymentFlow
from app.mod03_notice.models import PaymentNotice
from app.mod01_projects.models import Project
from app.report_export import fl_export as FL
from tests._auth import TestClient          # ⭐ 带会话票（同其余端点用例）
from tests.acc_plugin import acc
from tests.m05_helpers import FakeSession, make_flow, make_notice_row


def _notice(nid: int, *, bill_name: str = "", payee: str = "", **kw) -> PaymentNotice:
    """一行通知书 —— `make_notice_row` 造好之后再补两处（它没有 `fields` / `payee` 参数）。"""
    n = make_notice_row(nid, **kw)
    n.fields = {"BillName": bill_name}
    n.payee = payee
    return n


def _flow(fid: int, *, created_by: str = "", **kw) -> PaymentFlow:
    f = make_flow(fid, **kw)
    f.created_by = created_by
    return f


def _session(flows, notices=(), projects=()) -> FakeSession:
    return FakeSession({Project: list(projects), PaymentNotice: list(notices),
                        PaymentFlow: list(flows)})


def _client(flows, notices=(), projects=(), seen: dict | None = None) -> TestClient:
    """真端点 ＋ **真装配**（`svc.build_flows`）—— 注入的只是"库里有这些行"，不是结果本身。

    ⚠️ `seen` 记下端点**实际传进来的取数参数**（`year_month` 那一项是本票的一条验收：
    导出必须显式要**全量**，否则历史月份的流水屏幕上有、导出来没有）。
    """
    import app.mod05_flow.router as m05_router

    app = create_app()

    def _loader(**kw):
        if seen is not None:
            seen.update(kw)
        return svc.build_flows(_session(flows, notices, projects), **kw)

    app.dependency_overrides[m05_router.get_flows_data] = lambda: _loader
    return TestClient(app)


def _cells(body: dict) -> list[list]:
    ws = openpyxl.load_workbook(io.BytesIO(base64.b64decode(body["content_b64"]))).active
    return [[c.value for c in row] for row in ws.iter_rows()]


def _idx() -> dict[str, int]:
    return {k: i for i, (_, k) in enumerate(FL.COLUMNS)}


# ---------------------------------------------------------------- ① 装配：五项 ＋ 失联


@acc()
def test_装配补五项且失联流水照常出行():
    """五项全取后端（⛔ 不依赖前端 `NO` 缓存）；**失联不是消失**：
    `notice_id` 为空 / 指向已删除通知书 ⇒ 流水照出、五项留空、审批金额 `None`。"""
    notices = [
        _notice(101, bill_no="D1", doc_date="2026-09-01", bill_name="钢材付款", payee="甲公司",
                category=CATEGORY_JC, settle="1000", paid="200"),
        _notice(102, bill_no="D2", doc_date="2026-09-02", bill_name="零审批的单", payee="丙公司",
                category=CATEGORY_MATERIAL, settle="0", paid="0"),
    ]
    flows = [
        _flow(71, flow_no="FL-X9", notice_id=101, amount="300.00"),
        _flow(72, flow_no="FL-Y1", notice_id=None, amount="200.00"),      # 从没关联过通知书
        _flow(73, flow_no="FL-Z1", notice_id=999, amount="100.00"),       # 指向已删除的通知书
        _flow(74, flow_no="FL-Z2", notice_id=102, amount="0.00"),         # 审批额**真的**是 0
    ]
    data = svc.build_flows(_session(flows, notices), year_month="")
    rows = {r["id"]: r for r in data["rows"]}
    assert set(rows) == {71, 72, 73, 74}, "失联的流水被 join 式装配丢掉了"

    a = rows[71]
    assert (a["doc_date"], a["bill_name"], a["payee"], a["amount_approved"], a["category_label"]) \
        == ("2026-09-01", "钢材付款", "甲公司", "1000.00", "集采"), "五项通知书信息没装配出来"
    assert a["flow_no"] == "FL-X9" and a["amount"] == "300.00"
    # ⭐ 「失联」与「真是 0」是两件事 —— 一个留空（None），一个写 0.00
    for fid in (72, 73):
        r = rows[fid]
        assert r["amount_approved"] is None, f"{fid}：失联时审批金额被伪成了 0"
        assert (r["doc_date"], r["bill_name"], r["payee"], r["category_label"]) \
            == ("", "", "", ""), f"{fid}：失联时新列没有如实留空"
        assert r["amount"] and r["flow_no"], f"{fid}：流水本身必须照常出行"
    assert rows[74]["amount_approved"] == "0.00", "审批金额真是 0 时必须写 0.00（不许留空）"


@acc()
def test_装配不逐行查库():
    """⛔ 不许 N+1：通知书**一次预读**成字典，行数翻十倍，取数次数**不变**。"""
    notices = [_notice(i, bill_no=f"D{i}", settle="10") for i in range(1, 4)]

    class _Counting(FakeSession):
        def __init__(self, by_model) -> None:
            super().__init__(by_model)
            self.calls = 0

        def execute(self, stmt):  # noqa: ANN001
            self.calls += 1
            return super().execute(stmt)

    def _calls(n: int) -> int:
        flows = [_flow(700 + i, notice_id=1 + (i % 3), amount="1.00") for i in range(n)]
        s = _Counting({Project: [], PaymentNotice: list(notices), PaymentFlow: flows})
        svc.build_flows(s, year_month="")
        return s.calls

    small, big = _calls(3), _calls(30)
    assert small == big, f"取数次数随行数增长（{small} → {big}）⇒ 逐行查库了（N+1）"
    assert small <= 6, f"一次列表装配查了 {small} 次库，不像'一次预读 ＋ 全量读流水'"


# ---------------------------------------------------------------- ② 导出：逐格 ＋ 口径


@acc()
def test_导出全量装配并逐格对上页面列():
    """导出 = **页面表头去掉「操作」**那 14 列，取值 = 页面显示的值；首列「流水号」是真 `flow_no`
    （⛔ 数据库行号只作定位、不进导出）；合计**只加实付**、审批金额不参与。"""
    notices = [
        _notice(101, bill_no="D1", doc_date="2026-09-01", bill_name="钢材付款", payee="甲公司",
                category=CATEGORY_JC, settle="1000", paid="200"),
        _notice(102, bill_no="D2", doc_date="2026-09-02", bill_name="普通单据", payee="乙公司",
                category=CATEGORY_MATERIAL, settle="500", paid="100"),
    ]
    flows = [
        # ⚠️ 付款日期故意放在**历史月份**：默认当月装配会一行都挑不到 ⇒ 这条同时守"全量"
        _flow(71, flow_no="FL-A", notice_id=101, amount="300.00", pay_date="2026-08-05",
              created_by="甲"),
        _flow(72, flow_no="FL-B", notice_id=102, amount="200.00", pay_date="2026-08-06",
              pay_method="承兑", created_by="乙"),
        _flow(73, flow_no="FL-C", notice_id=None, amount="100.00", pay_date="2026-08-07",
              status=FLOW_REVOKED, revoke_reason="冲正"),
    ]
    seen: dict = {}
    client = _client(flows, notices, seen=seen)
    r = client.post("/api/m05/flows/export", json={"ids": [73, 71, 72]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["rows"] == 3
    assert seen.get("year_month") == "", "导出没显式要全量 ⇒ 历史月份的流水会导不出来"

    cells = _cells(body)
    idx = _idx()
    assert cells[0] == [label for label, _ in FL.COLUMNS], "表头与 `fl_export.COLUMNS` 不一致"
    assert [row[0] for row in cells[1:4]] == ["FL-C", "FL-A", "FL-B"], \
        "行序没跟传入的 id 走（= 屏幕上的行序）"
    # ⭐ 首列是真流水号：数据库行号 71/72/73 一个都不许出现在这一列
    assert not [row for row in cells[1:4] if str(row[0]) in {"71", "72", "73"}], \
        "「流水号」列又拿数据库行号顶上去了"
    row_a = cells[2]
    assert row_a[idx["doc_no"]] == "D1"
    assert row_a[idx["doc_date"]] == "2026-09-01"
    assert row_a[idx["bill_name"]] == "钢材付款"
    assert row_a[idx["payee"]] == "甲公司"
    assert row_a[idx["category_label"]] == "集采"
    assert row_a[idx["amount_approved"]] == 1000.0, "审批金额没写成数字"
    assert row_a[idx["pay_date"]] == "2026-08-05"
    assert row_a[idx["amount"]] == 300.0
    assert row_a[idx["created_by"]] == "甲", "「操作人」不是 `created_by`"
    assert row_a[idx["status_text"]] == "生效"
    # 失联那行：流水照出，通知书五项留空（⛔ 不写 0、不丢行）
    row_c = cells[1]
    assert row_c[idx["amount_approved"]] in ("", None), "失联流水的审批金额写成了数（应留空）"
    # ⚠️ 空串经 openpyxl 往返读回来可能是 `None`（空串与空单元格在 xlsx 里是同一件事）
    #   ⇒ 判"留空"一律 `in ("", None)`；要判"**不许是 0**"得单独钉（下面那条 amount_approved）。
    assert row_c[idx["bill_name"]] in ("", None) and row_c[idx["payee"]] in ("", None)
    assert row_c[idx["amount"]] == 100.0
    assert row_c[idx["status_text"]] == "已撤销（冲正）", "撤销原因没并进状态格"
    # 合计：只加**生效**（300 ＋ 200），已撤销那 100 不进；审批金额那一格**留空**
    tail = cells[-1]
    assert tail[0] == "合计"
    assert tail[idx["amount"]] == 500.0, "合计不是「只加生效实付」"
    assert tail[idx["amount_approved"]] in ("", None), \
        "审批金额参与了合计（同一张单的每笔是**对照数**，加起来是假数）"
    assert len(cells) == 5, "行数不对（表头 ＋ 3 数据行 ＋ 合计行）—— 合计之外不许有伪数据行"


@acc()
def test_只有已撤销时导出仍写零合计且无伪数据行():
    """边界：选中行**全是已撤销** ⇒ 屏幕写「合计（生效 0 条）¥0.00」⇒ Excel 同步写零合计，
    ⛔ 但**不许**为凑合计而凭空添一行付款数据。"""
    flows = [_flow(73, flow_no="FL-C", notice_id=None, amount="100.00", pay_date="2026-08-07",
                   status=FLOW_REVOKED, revoke_reason="冲正")]
    body = _client(flows).post("/api/m05/flows/export", json={"ids": [73]}).json()
    cells = _cells(body)
    idx = _idx()
    assert len(cells) == 3, f"行数不对（表头 ＋ 1 数据行 ＋ 合计行）：{len(cells)}"
    assert cells[1][idx["amount"]] == 100.0, "被撤销的那笔本身要导出（带原因）"
    assert cells[1][idx["status_text"]] == "已撤销（冲正）"
    assert cells[-1][idx["amount"]] == 0.0, "全已撤销时合计应是 0.00（与屏幕一致）"


@acc()
def test_导出没挑到行时不留幽灵合计():
    """反面：传入的 id 一个都挑不到（页面上已经删掉的行）⇒ `rows=0`，⛔ 不写合计行。"""
    flows = [_flow(71, flow_no="FL-A", notice_id=None, amount="300.00", pay_date="2026-08-05")]
    body = _client(flows).post("/api/m05/flows/export", json={"ids": [999]}).json()
    assert body["ok"] is True and body["rows"] == 0
    assert len(_cells(body)) == 1, "一行数据都没有却写了合计行（凭空一排 0 = 假值）"
