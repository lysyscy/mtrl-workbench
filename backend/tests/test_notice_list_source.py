"""`GET /api/m03/notice-list` 的**取数层**口径：必须给全（含剔除 / i8 已撤单行）。

⚠️⚠️ 用户 2026-09-20 实测：「抓取付款通知书，那些被剔除的单据**似乎没有落库**，
   **筛选剔除单据后全是空的**，你要修一下，**要落库**，不然误剔除的永远没法改」。

⭐⭐ **真因不是没落库**（取证：库里 `excluded=True` 有 **71 行**、抓取记录也如实报 `excluded=44/27`），
   而是 **这个端点把"页面的默认隐藏"也搬到服务端砍了一刀**：
   实测 **库 200 行 → 接口只回 129 行（= 200 − 71）** ⇒ **壳里从来没有剔除行** ⇒
   壳切「分类 = 剔除」（`ntHit` 里 `ex=arch(n)`）**必然全空**。

⚠️ 而这条口径本仓**早已写明**（`repository.notice_rows` 的 docstring）：
   「剔除与撤单行的『默认隐藏』是**筛选层**的事（`list_view.filter_rows`），不是取数层 ——
     **取数层必须给全**，否则计数与『分类 = 剔除』视图都算不出来。」
   ⇒ 本文件钉的就是这一句：**取数层给全，隐藏交给筛选层**。
"""

from __future__ import annotations

from app.core.db import session_scope
from app.mod03_notice.list_data import build_rows
from app.mod03_notice.list_view import NoticeFilters, filter_rows
from app.mod03_notice.notice_api_router import notice_filters


def test_接口筛选解析标了取数层给全():
    """**结构**：`/api/m03/notice-list` 的筛选解析必须声明"这是取数层、要给全"。

    ⚠️ 这条**不能只靠行为测**：行为测在"库里恰好没有剔除行"时是**假绿**
       （0 == 0 也过）⇒ 必须有一条与数据无关的钉法。
    """
    f = notice_filters("", [], "", "", "")
    assert f.include_archived is True, (
        "`/api/m03/notice-list` 的筛选解析没标「取数层给全」⇒ 服务端会按页面的默认隐藏砍掉剔除行 ⇒ "
        "壳里没有它们 ⇒ 切「分类 = 剔除」全空（用户 2026-09-20 实测：库 200 行 → 接口 129 行）")


def test_开了给全开关就多出剔除与撤单行():
    """**行为**：同一批行，`include_archived=True` 必须把「剔除 / i8 已撤单」那些行**原样带上**。

    差值必须**恰好等于** `in_exclude_view` 的行数 —— ⛔ 不是"不为零就行"：
    差少了说明还有别的口径在取数层误砍，差多了说明它把不该放的也放了。
    """
    with session_scope() as s:
        rows = build_rows(s)          # 库里全部行（取数层出口，含剔除/撤单）

    on = filter_rows(rows, NoticeFilters(period="", include_archived=True))
    off = filter_rows(rows, NoticeFilters(period="", include_archived=False))
    arch = [r for r in rows if r.in_exclude_view]

    assert len(on) - len(off) == len(arch), (
        f"`include_archived=True` 应当把 {len(arch)} 行剔除/撤单行带出来，"
        f"实际只多了 {len(on) - len(off)} 行 —— 说明「默认隐藏」那一刀还在**取数层**砍。"
        "（用户 2026-09-20：库 200 行 → 接口只回 129 行 ⇒ 壳切「分类 = 剔除」全是空的）")
    # ⛔ 反面：`False` 时它们必须**不在**里面（页面视图的默认隐藏不能因此失效）
    assert not [r for r in off if r.in_exclude_view], \
        "`include_archived=False` 时剔除/撤单行不该出现（页面视图的默认隐藏被弄坏了）"


def test_home_todos_match_list_window_through_payment_and_link_changes(rollback_db, monkeypatch):
    from decimal import Decimal
    from app.mod01_projects.models import Project
    from app.mod03_notice import repository
    from app.mod03_notice.models import PaymentNotice
    from app.mod03_notice.notice_api_router import get_home_todos, get_notice_list
    from app.mod05_flow.models import PaymentFlow
    from app.mod11_jc.models import JcContract, JcPayment

    # Exercise the real cap/order on a small, tied-date window in the rollback schema.
    window = repository._notice_list_window
    def test_window(stmt, limit):
        assert limit == repository.NOTICE_LIST_LIMIT
        return window(stmt.where(PaymentNotice.ph_id.startswith("test-home-todo-")), 7)
    monkeypatch.setattr(repository, "_notice_list_window", test_window)

    with session_scope() as s:
        def check(ownership, jc, void, count=7):
            expected = {"notice_count": count, "ownership": ownership, "jc": jc, "void": void}
            assert get_home_todos(session=s) == expected
            items = get_notice_list(period="", project=[], category="", approve_status="", pay_status="",
                                    sort="", dir=0, session=s)["items"]
            live = [row for row in items if not row["is_excluded"] and
                    (not row["is_revoked"] or Decimal(row["amount_paid"]) > 0 or row["has_link"])]
            assert (len(items), sum(row["ownership_id"] is None for row in live),
                    sum(row["category"] == "jc" and not row["has_link"] and row["pay_status"] == "未付清"
                        for row in live), sum(row["is_revoked"] for row in live)) == (count, ownership, jc, void)

        check(0, 0, 0, 0)
        project = Project(warehouse_name="首页待办测试仓", name_full="测试项目", phid="test-home-todo-project")
        s.add(project)
        s.flush()
        contract = JcContract(project_id=project.id)
        s.add(contract)
        def notice(name, **fields):
            row = PaymentNotice(ph_id="test-home-todo-" + name, doc_date="2026-11-22",
                                amount_approved=10, amount_paid=100, stat_paid=100, **fields)
            s.add(row)
            s.flush()
            return row
        notice("outside", category="jc")
        unpaid = notice("unpaid", category=" jc ")
        paid = notice("paid", category="jc", ownership_id=project.id)
        revoked = notice("reversed", category="jc", i8_revoked=True)
        joint = notice("joint", category="material", i8_revoked=True)
        linked = notice("linked", category="jc", i8_revoked=True)
        notice("excluded", category="jc", excluded=True)
        notice("assigned", category="material", ownership_id=project.id)
        link = JcPayment(contract_id=contract.id, source="notice", notice_id=linked.id)
        s.add_all([link, PaymentFlow(notice_id=joint.id, amount=1),
                   PaymentFlow(notice_id=revoked.id, amount=10, status="revoked"),
                   PaymentFlow(notice_id=paid.id, amount=10, status="")])
        s.flush()
        check(3, 1, 2)
        unpaid.ownership_id = project.id
        s.delete(link)
        s.add(PaymentFlow(notice_id=unpaid.id, amount=10))
        s.flush()
        check(1, 0, 1)
