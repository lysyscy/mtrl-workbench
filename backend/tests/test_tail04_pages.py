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
from app.report_export import fl_export, nt_export
from tests.m03_action_helpers import FakeWriteSession, _notice

#: 壳里的 `data-act="exp"` 按钮的 `data-t`（**真源 = `index.html`**，本表只在测试里对账用）。
#: ⚠️ 2026-09-21：`i8 接口清单` 的卡片已随「接口清单删除」裁定移除（m02 清单卡）⇒ 从本表摘除。
#: ⚠️ 2026-09-28（`TAIL-124`）：`全量台账` 摘除 —— 那是 `m13` 「演示导出」枚假按钮的落点，
#:    本批把整页改成用户视角时把它删了（`m13` 无自有数据源 ⇒ 不设导出入口）。
BUTTON_T = (
    "付款通知书台账", "付款流水", "项目档案",
    "过程资料", "库存单据明细总表", "差异清单", "集采台账",
)




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




def test_两个新端点都挂上了():
    """⭐ "已接"必须**有落点**：两个端点真的在 FastAPI 的路由表里（⛔ 不是只有函数名）。

    ⚠️ 本版 FastAPI 把 `include_router` 的结果包成 `_IncludedRouter`（`app.routes` 里读不到 `path`）
       ⇒ 一律查 OpenAPI 表（`app.routes` 那条路本轮实测走不通）。
    """
    paths = set(create_app().openapi()["paths"])
    for p in ("/api/m03/notices/export",):
        assert p in paths, f"{p} 没挂上 —— 按钮按下去只会 404"
        assert "post" in create_app().openapi()["paths"][p], f"{p} 不是 POST（壳侧发的是 POST）"


# ============================================================== 列 = 页面表头


def test_导出列就是页面表头去掉勾选与操作():
    """⭐ 导出的列**不是**在这里"设计"的 —— 它必须**逐字等于页面表头**去掉「勾选 / 操作」。

    ⚠️ 为什么这条最重要：页面加一列/改一个列名、导出没跟 ⇒ **表与屏幕对不上号**，
       而且**没有任何报错**（本项目最怕的那类）。⇒ 用一个**单向真源**（`SHELL` 里的 `NT_THEAD` /
       `PL_THEAD`）来钉，⛔ 别用"两边都手写一遍再比"（那只是把同一份错抄两遍）。
    ⚠️ `✎`（`付款金额 ✎` 那三列）**必须留着** —— 它是页面表头原文，
       洗净了表头就对不上屏幕（口径见 `nt_export` 模块头）。
    """

    # 页面省略流水号，Excel按现行契约保留它供核对（fl_export模块头）。

    # ⭐⭐ 2026-10-11（`TAIL-298`）：`m11` 的**屏幕表头已不住壳里** —— 它 = 域内核那张列清单
    #   （`domain.JC_COLUMNS`，`V.m11` 的表头就是拿它生成的）⇒ 本件按同一条口径对账：
    #   次序 = 屏幕列序（去「操作」）；导出的字 = `export_label`（缺省 = `label`，屏幕注解不进 Excel）。
    from app.mod11_jc import domain as JC_D
    from app.report_export import jc_export  # noqa: PLC0415 —— 局部取件：本段只服务 m11 这一页
    jc_rows = [c for c in JC_D.JC_COLUMNS if c["key"] not in JC_D.PAGE_ONLY_KEYS]
    assert _export_labels(jc_export.COLUMNS) == [c.get("export_label") or c["label"] for c in jc_rows], (
        "`jc_export.COLUMNS` 与「屏幕表头（域内核列清单）去掉操作列」不一致 —— 表与屏幕对不上号了")
    assert len(jc_rows) == len(jc_export.COLUMNS) and jc_rows
    # ⛔ 壳里不许再长回那张 20 列字面量（有 ⇒ 又是两份列清单，`TAIL-298` 治的就是它）。
    #   ⚠️ 判"字面量退场"要认**声明**与**表头串**，⛔ 别拿标识符当判据 —— 注释里提 `JC_THEAD`
    #      （说"那个字面量已删"）是正常的，按标识符判会当场假红。


def test_朴素导出其余四页的列键都在该页行字典里(monkeypatch):
    """`TAIL-298`：`naive_export` 的**每个调用页**都要有一条「`COLUMNS` 的每个 key 都出现在**该页产出的
    行字典**里」的断言 —— 堵 `r.get(key)` 那类**静默空列**（键名漂了不报错，只是那一列永远空着）。
    （`m11` 那一页在 `tests/test_tail298_columns.py` —— 它走真库；本件管其余四页。）

    ⚠️ **每页的"真实行字典"必须来自该页自己的产出行代码**（⛔ 别拿 `COLUMNS` 造一行再自证 —— 那是循环论证）：
      · `nt` / `pl`：`_export_row(...)` —— 导出端点逐行调的就是它（纯函数，可直接调）；
      · `fl` / `pj`：那两页的行字典是**端点里现拼的字面量** ⇒ 打桩**内核**，把真正交给它的那批行截下来
        （走真端点那条路：取数 → 按 id 挑 → 拼行 → 交内核）。
        · `fl` 的取数是**注入的**（`load=` 形参）⇒ 给个桩即可，⛔ 不必替库；
        · `pj` 的取数走 `session_scope` ⇒ 只把那**一层**换成桩（本判据要验的是**行字典的键**，⛔ 不是 SQL）；
          真建档案行会写库，与"库级断言非破坏"冲突（走真库的那份在 `m11` 那条里做）。
    """
    from contextlib import nullcontext  # noqa: PLC0415
    from types import SimpleNamespace  # noqa: PLC0415

    from app.mod03_notice import notice_api_router as NTR  # noqa: PLC0415
    from app.mod05_flow import router as FLR  # noqa: PLC0415
    from app.mod01_projects import router as PJR  # noqa: PLC0415
    from app.report_export import pj_export  # noqa: PLC0415

    def _keys(mod) -> set[str]:
        return {k for _, k in mod.COLUMNS}

    def _capture(which: str):
        """把交给**内核**的那批行截下来（返回值只需是个 bytes —— 本判据不看书）。"""
        def _f(rows, **kw):
            got[which] = rows
            return b""
        return _f

    # ① nt / pl：行字典由 `_export_row` 产（空记录也走得通 —— 那几格留空本来就是本页口径）
    assert _keys(nt_export) <= set(NTR._export_row({})), "付款通知书导出有列在这页的行字典里不存在"

    # ② fl：行字典在端点里现拼 ⇒ 打桩内核截行（取数走注入的 `load`，一行够 —— 键才是判据）
    got: dict = {}
    monkeypatch.setattr(fl_export, "build_xlsx", _capture("fl"))
    FLR.export_flows(FLR.FlowExportIn(ids=[1]), load=lambda **kw: {"rows": [{"id": 1}]})
    assert got.get("fl"), "没截到 `fl` 的行 —— 那条路变了（⛔ 别让它静默通过）"
    assert _keys(fl_export) <= set(got["fl"][0]), "付款流水导出有列在这页的行字典里不存在"

    # ③ pj：同上，但取数那层的 `session_scope` 换成桩（列表本身仍是**端点里的真代码**）
    fake = SimpleNamespace(id=1, ord=1, project_type="normal", disp="自检展示名", warehouse_name="自检仓",
                           name_full="自检仓项目", phid="", status="active",
                           parent_shell_id=None, match_keywords=["自检词"])

    class _FakeSession:
        def execute(self, *_a, **_kw):
            return self

        def scalars(self):
            return self

        def all(self):
            return [fake]

    monkeypatch.setattr(PJR, "session_scope", lambda: nullcontext(_FakeSession()))
    monkeypatch.setattr(pj_export, "build_xlsx", _capture("pj"))
    PJR.export_projects(PJR.ProjectExportIn(ids=[1]))
    assert got.get("pj"), "没截到 `pj` 的行 —— 那条路变了（⛔ 别让它静默通过）"
    assert _keys(pj_export) <= set(got["pj"][0]), "项目档案导出有列在这页的行字典里不存在"


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




# ============================================================== 壳侧：pjVisible ⇄ V.m01
