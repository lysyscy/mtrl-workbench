"""`ACC-JC-*`（M5 集采域）· **抓取落库**（`M5-6` 的落库半片）的验收断言。

⚠️ 库级断言**一律非破坏**：每个用例末尾 `s.rollback()`（⛔ 一行不留）。

逐条对应（`claim` 原文见验收基线）：
- `ACC-JC-FETCH-001/001-09` 再次导入**不覆盖旁路字段**（分类 / 集采实际供应商 / 调整单 —— 本模块对应
  三态 / 存档三列 / 备注 / 付款方式 / 贸易公司）
- `ACC-JC-FETCH-001/001-08` 三态标记**不留痕**（**无留痕载体**）
- （另加一条 `@acc()` 实现层自检：幂等键 = 合同编号）

⚠️ 判据 `001-10`「抓取**不覆盖已人工标记的行**」也在这里顺带钉住（它是 `001-09` 的姊妹条，
   已在 `M5-2` 的域内核断言里绿过；本文件从**落库**这一侧再验一次）。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import inspect

from app.core.db import get_engine, session_scope
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL, Project
from app.mod11_jc import repository as R
from app.mod11_jc.models import TAG_IN, TAG_OUT, TAG_PENDING, JcContract
from tests.acc_plugin import acc

WH_F = "__自检仓_集采抓__"


def _project(s, wh: str = WH_F) -> Project:
    row = pj_repo.create_project(
        s, project_type=TYPE_NORMAL, name_full=f"{wh}项目", warehouse_name=wh, phid=""
    )
    s.flush()
    return row


def _fetched(no: str, *, date: str = "2026-09-15", supplier: str = "业祥",
             amount: str = "100", material: str = "主材钢材") -> dict:
    """一条 `API-04` 取数结果（字段名 = `contract_source._map_record` 的输出形状）。"""
    return {"contract_no": no, "sign_date": date, "material_name": material,
            "supplier_name": supplier, "contract_amt": amount, "remark": "增补原合同"}


@acc("ACC-JC-FETCH-001", "001-09")
def test_再次导入不覆盖旁路字段_且不动已人工标记的行():
    """⭐ 两条判据一起验（它们本就是一件事的两面）：

    ① `001-09` **再次导入不覆盖旁路字段** —— 重抓同一张合同时，⛔ 不许把人工填的东西冲掉；
    ② `001-10` **抓取不覆盖已人工标记的行** —— 人工标过的三态，重抓后必须**原样还在**。
    """
    with session_scope() as s:
        p = _project(s)
        first = R.upsert_fetched_contracts(s, project_id=p.id, rows=[_fetched("__自检_CGHT_1__")])
        assert first["inserted"] == 1 and first["refreshed"] == 0

        row = R.one_by_no(s, "__自检_CGHT_1__")
        assert row.tag == TAG_PENDING, "新抓的默认「待确认」（⛔ 不是「纳入台账」）"

        # 人把它标成「不纳入」＋ 填了存档三列 / 备注 / 付款方式 / 贸易公司
        row.tag = TAG_OUT
        row.arch, row.arch_no, row.ret_date = "已存档", "7", "2026-09-20"
        row.remark, row.method, row.trade_co = "我写的备注", "60±7天承兑", "维萨"
        s.flush()

        # 再过一遍抓取（同一编号，且**抓取值变了**）
        again = R.upsert_fetched_contracts(
            s, project_id=p.id,
            rows=[_fetched("__自检_CGHT_1__", date="2026-09-16", supplier="尚坤", amount="999")])
        assert again["inserted"] == 0 and again["refreshed"] == 1, "同编号 ⇒ 只刷新、不新增"

        same = R.one_by_no(s, "__自检_CGHT_1__")
        # ① 抓取字段**确实刷新了**（说明 upsert 真的在做事，⛔ 不是"整个跳过"）
        assert (same.contract_date, same.supplier) == ("2026-09-16", "尚坤")
        assert same.contract_amt == Decimal("999.00"), "抓取的合同金额必须被刷新"
        # ② 人工字段**一个都没被冲掉**（`001-09` 的核心）
        assert same.tag == TAG_OUT, "⭐ 已人工标记的三态必须原样保留（001-10）"
        assert (same.arch, same.arch_no, same.ret_date) == ("已存档", "7", "2026-09-20")
        assert (same.remark, same.method, same.trade_co) == ("我写的备注", "60±7天承兑", "维萨")
        s.rollback()


@acc("ACC-JC-FETCH-001", "001-08")
def test_三态标记不留痕_没有留痕载体():
    """⭐ 判据原文「三态标记**不留痕**（**无留痕载体**）」—— 这是一条**约束型**判据：
    它要的不是"某功能存在"，而是"**某个东西不许存在**" ⇒ 只能靠**结构**来钉。
    """
    cols = {c.name for c in JcContract.__table__.columns}
    banned = {"tag_log", "tag_history", "tag_changed_at", "tag_by", "tag_note",
              "prev_tag", "old_tag", "tag_operator"}
    assert not (cols & banned), f"⛔ 不许给三态加留痕列（命中：{cols & banned}）"

    names = set(inspect(get_engine()).get_table_names())
    assert "jc_tag_log" not in names and "jc_tag_history" not in names, \
        "⛔ 不许有「标记历史」表（判据 001-08：无留痕载体）"


@acc()
def test_落库幂等_按合同编号_且无编号的行被跳过并计数():
    """实现层自检（⛔ 不绑判据点）：幂等键 = **合同编号**；没编号的行**跳过并计数**（禁静默）。"""
    with session_scope() as s:
        p = _project(s)
        rows = [_fetched("__自检_CGHT_A__"), _fetched("__自检_CGHT_B__"), {"contract_no": ""}]
        r1 = R.upsert_fetched_contracts(s, project_id=p.id, rows=rows)
        assert (r1["inserted"], r1["refreshed"], r1["skipped"]) == (2, 0, 1), "无编号 ⇒ 跳过并计数"

        r2 = R.upsert_fetched_contracts(s, project_id=p.id, rows=rows)
        assert (r2["inserted"], r2["refreshed"], r2["skipped"]) == (0, 2, 1), "重跑 ⇒ 零新增"

        # 行数只由"有编号的新行"决定（独立复算）
        assert R.count_contracts(s) >= 2
        s.rollback()


# ============================================== 001-11 · 集采匹配 = 付款侧同一套归属（TAIL-92）


@acc("ACC-JC-FETCH-001", "001-11")
def test_集采匹配走付款侧同一套归属_不得挂到壳上():
    """⭐ 2026-09-25 用户口径：「**集采合同抓取和付款通知书抓取用同一套匹配逻辑**」＋ 铁律 §9.8-6。

    **壳与具体小微共用同一个全名**（《说明书》§2.2 / §2.6）⇒ 拿全名去撞项目表**必然**命中 `[壳, 小微]`，
    而壳**没有仓库、不进任何候选** ⇒ 取到壳 = 那批合同"没有项目"、**欠款无从归集**（实测 23 条）。

    ⇒ 本判据钉两件事：① 分堆**只委托** `mod01_projects.domain.resolve_ownership`（⛔ 本层不自己判一遍）；
       ② 「壳全名 ＋ 单据名命中某小微」⇒ 落**那个小微**；命中多个 / 一个没中 / 未建档 ⇒ **不落库**且报出类别。
    """
    from types import SimpleNamespace

    from app.mod01_projects.models import TYPE_NORMAL, TYPE_SHELL, TYPE_SMALL
    from app.mod11_jc.fetch_service import match_projects

    def _p(pid, kind, full, *, wh=None, parent=None, kw=None):
        return SimpleNamespace(id=pid, project_type=kind, name_full=full, warehouse_name=wh,
                               parent_shell_id=parent, match_keywords=kw or [])

    full_shell = "第四工程公司2026年小微项目(TBLX2026070003)"
    shell = _p(10, TYPE_SHELL, full_shell)
    small = _p(19, TYPE_SMALL, full_shell, wh="兰考金不换前置车间项目",
               parent=10, kw=["兰考金不换"])
    normal = _p(7, TYPE_NORMAL, "晋江污泥处理中心一期工程核心设备安装工程(TBLX2024040013)",
                wh="晋江污泥处理项目")
    projects = [shell, small, normal]

    def _row(full, bill):
        return {"contract_no": "CGHT-X", "project_name": full, "fields": {"BillName": bill}}

    # ① 普通项目：照旧落库
    m = match_projects([_row(normal.name_full, "晋江污泥处理中心…/钢材/…")], projects)
    assert [r["project_id"] for r in m["matched"]] == [7] and not m["unmatched"]

    # ② 壳全名 ＋ 单据名命中该壳下**唯一**小微 ⇒ **落到那个小微**（⛔ 不是壳！）
    m = match_projects([_row(full_shell, "第四工程公司兰考金不换项目亿管通钢材付款")], projects)
    assert [r["project_id"] for r in m["matched"]] == [19], "壳全名被挂到了壳上（§9.8-6 违规）"
    assert 10 not in [r["project_id"] for r in m["matched"]], "⛔ 落到了壳（壳没有仓库、不进候选）"

    # ③ 壳全名 ＋ 单据名一个关键词都没命中 ⇒ **不落库**，且**报出类别**（禁静默）
    m = match_projects([_row(full_shell, "第四工程公司某笔没见过的项目付款")], projects)
    assert not m["matched"] and len(m["unmatched"]) == 1
    assert m["unmatched"][0]["unsettled_kind"] == "needs_keyword"

    # ④ 项目未建档 ⇒ 不落库（走链路 A 建档后重判）
    m = match_projects([_row("根本不存在的项目全名(XMCB0000000000)", "x")], projects)
    assert not m["matched"] and m["unmatched"][0]["unsettled_kind"] == "not_archived"


# ============================================== 001-12 · 集采「归属未走完」可读回（TAIL-93）


@acc("ACC-JC-FETCH-001", "001-12")
def test_集采未走完清单只认最近一次抓取_且认得出域():
    """⭐ `TAIL-93`：集采的「归属未走完」要**能被读回**（否则界面上无从处理，只能人工写脚本建档案）。

    口径**逐条对齐付款侧**（`GET /api/m03/notices/unresolved` · `TAIL-29`-② / `TAIL-41`）：
    · 写侧出口 `repository.fetch_detail` **一律带标记**（三种结局都要写 —— 漏一条，"最近一次"就指不住，
      读侧会掉回更早的记录 ⇒ 用户对着**已解决**的清单白干）；
    · 读侧 `repository.latest_unsettled` **只认最近一次**带标记的记录：它没带清单 ⇒ **返回空**，
      ⛔ **不回溯更早的那次**（这正是 `TAIL-41` 那条修复的骨血）；
    · 认不出域（付款 / 材料的记录）⇒ **跳过**，不误当集采清单。

    ⚠️ 「弹窗能点通、补完再抓即归位」由**真机 `_shell_smoke`** 兜 —— 本条刻意不 mock 端点（免造第二套口径）。
    """
    from app.mod11_jc import repository as R

    class _Res:
        def __init__(self, rows): self._rows = rows
        def scalars(self): return self
        def all(self): return self._rows

    class _Sess:
        def __init__(self, recs): self._recs = recs
        def execute(self, _stmt): return _Res(self._recs)

    class _Rec:
        def __init__(self, rid, detail): self.id = rid; self.detail = detail

    # ① 写侧出口：一律带标记（caller 只管传业务字段）
    d = R.fetch_detail(jc_unsettled=[{"contract_no": "A"}])
    assert d[R.JC_FETCH_MARK] is True and d["jc_unsettled"] == [{"contract_no": "A"}]

    # ② 只认**最近一次**带标记的记录（更早那次有清单也不看）
    recs = [_Rec(3, {"reason": "别的域"}),
            _Rec(2, {"jc_fetch": True, "jc_unsettled": [{"contract_no": "A"}]}),
            _Rec(1, {"jc_fetch": True, "jc_unsettled": [{"contract_no": "B"}]})]
    assert R.latest_unsettled(_Sess(recs)) == [{"contract_no": "A"}]

    # ③ 最近一次**已走完**（没带清单）⇒ 空，⛔ 不回溯更早那次（`TAIL-41` 的教训）
    recs = [_Rec(4, {"jc_fetch": True}),
            _Rec(2, {"jc_fetch": True, "jc_unsettled": [{"contract_no": "A"}]})]
    assert R.latest_unsettled(_Sess(recs)) == []

    # ④ 别的域的记录（付款 / 材料）⇒ 跳过，不误认
    recs = [_Rec(5, {"notice_fetch": True, "unresolved": [{"x": 1}]}),
            _Rec(2, {"jc_fetch": True, "jc_unsettled": [{"contract_no": "A"}]})]
    assert R.latest_unsettled(_Sess(recs)) == [{"contract_no": "A"}]
