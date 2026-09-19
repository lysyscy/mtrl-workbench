"""`ACC-JC-PAY-001`（`M5-5` 付款域双向引用）的验收断言 —— 关联 / 解绑 / 一对一 / 全库去重。

⚠️ 库级断言**一律非破坏**：每个用例末尾 `s.rollback()`（⛔ 一行不留）。

逐条对应（`claim` 原文见验收基线）：
- `ACC-JC-PAY-001/001-01` **两个方向写同一份关联记录、双向可见**
- `ACC-JC-PAY-001/001-03` **一条通知书只能关联一个合同**（一对一；换合同 = **先解绑再写新**）
- （另加实现层自检：解绑 · 幂等 · **零金额也允许引用** · 非集采分类不许填供应商）
"""

from __future__ import annotations

from decimal import Decimal

from app.core.db import session_scope
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL, Project
from app.mod03_notice.list_view import _links_by_notice
from app.mod03_notice.models import PaymentNotice
from app.mod11_jc import repository as R
from app.mod11_jc import service as SV
from tests.acc_plugin import acc

WH_L = "__自检仓_集采关联__"


def _project(s, wh: str = WH_L) -> Project:
    row = pj_repo.create_project(
        s, project_type=TYPE_NORMAL, name_full=f"{wh}项目", warehouse_name=wh, phid=""
    )
    s.flush()
    return row


def _contract(s, *, project_id: int, supplier: str = "业祥", amount: str = "100"):
    from app.mod11_jc.models import JcContract

    row = JcContract(project_id=int(project_id), contract_date="2026-09-19",
                     material_name="自检材料", supplier=supplier, contract_amt=Decimal(amount))
    s.add(row)
    s.flush()
    return row


def _notice(s, *, ph: str, category: str = "jc", paid: str = "500",
            approved: str = "500") -> PaymentNotice:
    row = PaymentNotice(ph_id=ph, doc_date="2026-09-18", amount_approved=Decimal(approved),
                        stat_paid=Decimal(paid), category=category)
    s.add(row)
    s.flush()
    return row


@acc("ACC-JC-PAY-001", "001-01")
def test_两个方向写同一份记录_双向可见():
    """⭐ 判据原文「两个方向写**同一份**关联记录、**双向可见**」。

    ⭐ 这条判据的机器化落点 = **关联关系不另建表**：它只存在 `jc_contract` 的**付款子表**
    （`source=notice` ＋ `notice_id`）。于是两侧读的是**同一张表**：
      · 「集采侧」= 合同的付款子表行（`repository.payments_of` / `payment_of_notice`）；
      · 「付款域侧」= `list_view._links_by_notice`（`m03` 那侧唯一的接入点）算出的"已关联"态。
    ⇒ 双向可见是**结构上的必然**（⛔ 不是"两边各写一遍、再想办法同步"）。
    """
    with session_scope() as s:
        p = _project(s)
        c = _contract(s, project_id=p.id)
        n = _notice(s, ph="__自检_ph_关联甲__")

        # 关联**之前**：两侧都答"没有"
        assert _links_by_notice(s)(n.id) == [], "付款域侧：未关联"
        assert R.payment_of_notice(s, n.id) is None, "集采侧：未关联"

        r = SV.act_link_notice(s, notice_id=n.id, contract_id=c.id)
        assert r["ok"] is True and r["changed"] is True, r

        # 关联**之后**：两侧同时变"已关联"（因为它们读的是同一份记录）
        assert _links_by_notice(s)(n.id) == [c.id], "付款域侧必须**看到**这条关联（同一张表）"
        pay = R.payment_of_notice(s, n.id)
        assert pay is not None and int(pay.contract_id) == c.id, "集采侧：关联记录在"
        assert pay.source == "notice" and int(pay.notice_id) == n.id, "来源与通知书 id 都要对"
        assert len(R.payments_of(s, c.id)) == 1, "集采侧：合同付款子表里正好一条"
        s.rollback()


@acc("ACC-JC-PAY-001", "001-03")
def test_一对一_换合同先解绑再写新():
    """⭐ 判据原文「一条集采通知书**只能关联一个合同**（一对一；换合同 = **先解绑再写新**）」。

    ⚠️ 这条最容易写成"新插一条、旧的忘摘" —— 那样全库就有**两条**指向同一通知书的记录，
       而唯一键只能防"同一个 notice 两行"、防不住"两行分别指向不同合同"（那是**语义**问题）。
    """
    with session_scope() as s:
        p = _project(s)
        c1 = _contract(s, project_id=p.id, supplier="业祥")
        c2 = _contract(s, project_id=p.id, supplier="尚坤")
        n = _notice(s, ph="__自检_ph_关联乙__")

        r1 = SV.act_link_notice(s, notice_id=n.id, contract_id=c1.id)
        assert r1["ok"] and r1["contract_id"] == c1.id and r1["moved_from"] is None

        r2 = SV.act_link_notice(s, notice_id=n.id, contract_id=c2.id)
        assert r2["ok"] and r2["moved_from"] == c1.id, "换合同必须报出「从哪张摘过来的」"

        assert len(R.payments_of(s, c1.id)) == 0, "⛔ 旧合同上那条必须摘掉（否则一对多）"
        assert len(R.payments_of(s, c2.id)) == 1, "新合同上有且只有一条"
        assert len(R.payments_of(s, c1.id)) + len(R.payments_of(s, c2.id)) == 1, "全库仍只有一条"
        assert _links_by_notice(s)(n.id) == [c2.id], "付款域侧跟着变成新合同"

        # 幂等：再点一次同一张 ⇒ 什么都不做（⛔ 不重复插）
        r3 = SV.act_link_notice(s, notice_id=n.id, contract_id=c2.id)
        assert r3["ok"] is True and r3["changed"] is False, "重复关联同一张 = 幂等"
        assert len(R.payments_of(s, c2.id)) == 1
        s.rollback()


@acc()
def test_解绑_零金额引用_与非集采分类不许填供应商():
    """实现层自检（⛔ 不绑判据点）—— 三件容易漏的事。"""
    from app.mod03_notice.notice_actions import jc_supplier_problem

    with session_scope() as s:
        p = _project(s)
        c = _contract(s, project_id=p.id)
        # ① **零金额也允许引用**：关联是"关系"，不是"录入" ⇒ ⛔ 不受"子表金额必须 > 0"那条约束
        #    ⚠️ 要**两个金额都为 0** 才走到 0 —— 引用金额取「统计付款金额」，**没填（0）则退到审批金额**
        #    （`stat_paid or amount_approved`：`Decimal(0)` 是 falsy ⇒ 0 视为"没填"）。
        n0 = _notice(s, ph="__自检_ph_零额__", paid="0", approved="0")
        r = SV.act_link_notice(s, notice_id=n0.id, contract_id=c.id)
        assert r["ok"] is True, "金额为 0 也必须能关联（金额以后核，关系先建上）"
        assert Decimal(str(R.payment_of_notice(s, n0.id).amount)) == Decimal("0")
        # 再验"兜底"那一半：统计付款额为 0、审批额有值 ⇒ 取审批额（不是 0）
        n1 = _notice(s, ph="__自检_ph_兜底__", paid="0", approved="888")
        SV.act_link_notice(s, notice_id=n1.id, contract_id=c.id)
        assert Decimal(str(R.payment_of_notice(s, n1.id).amount)) == Decimal("888.00")
        SV.act_unlink_notice(s, notice_id=n1.id)

        # ② 解绑：两侧同时变回"未关联"
        un = SV.act_unlink_notice(s, notice_id=n0.id)
        assert un["ok"] is True and R.payment_of_notice(s, n0.id) is None
        assert _links_by_notice(s)(n0.id) == [], "解绑后付款域侧也看不到"
        # 再解一次 ⇒ 明确报"没有关联"（⛔ 不静默成功）
        assert SV.act_unlink_notice(s, notice_id=n0.id)["ok"] is False

        # ③ 「集采实际供应商」：**只有集采分类能填** —— 测**判定出口**（`notice_actions.jc_supplier_problem`），
        #    ⛔ 不调端点：端点内部要 `commit()` ⇒ 会把本用例的构造数据真提交，破坏"非破坏"纪律。
        nm = _notice(s, ph="__自检_ph_分类__", category="material")
        assert jc_supplier_problem(None) == "找不到该付款通知书"
        assert "集采" in str(jc_supplier_problem(nm)), "非集采分类必须被拒（判定在后端，⛔ 前端不许自行判定）"
        nj = _notice(s, ph="__自检_ph_分类集采__")
        assert jc_supplier_problem(nj) is None, "集采分类放行"
        s.rollback()
