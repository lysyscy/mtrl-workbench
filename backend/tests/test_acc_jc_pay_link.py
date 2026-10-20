"""`ACC-JC-PAY-001`（`M5-5` 付款域双向引用）的验收断言 —— 关联 / 解绑 / 一对一 / 全库去重。

⚠️ 库级断言**一律非破坏**：每个用例末尾 `s.rollback()`（⛔ 一行不留）。

逐条对应（`claim` 原文见验收基线）：
- `ACC-JC-PAY-001/001-01` **两个方向写同一份关联记录、双向可见**
- `ACC-JC-PAY-001/001-03` **一条通知书只能关联一个合同**（一对一；换合同 = **先解绑再写新**）
- （另加实现层自检：解绑 · 幂等 · **零金额也允许引用** · 非集采分类不许填供应商）
- ⭐ 2026-10-08 新增：**恢复剔除时回填归属**（规则剔除行落库时故意不带归属 ⇒ 恢复后必须补上）
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

WH_L = "__自检仓_集采关联__"


def test_恢复剔除时自动回填归属_判不出则如实保持空():
    """⭐ 2026-10-08 BUG 钉子：被**规则剔除**的行恢复后，**付款项目显示"未建档"**、
    且**一选项目筛选就再也勾不上**（用户实测报障）。

    ⚠️ 根因在抓取管线（`classify.rows_needing_ownership` 的注释写明）：规则剔除的行
    **故意 `ownership_id=None`**（否则整批归属校验会被误拦）⇒ 恢复时必须**补上归属**。
    ⚠️ 判据同时钉住三条边界：
      ① **归一化后能命中**（档案全名末尾带 i8 编号、单据全名不带 —— 库里 30 行都是这个形态）；
      ② **已指定过归属的行不被覆盖**（人工判断优先，同 `merge.PROTECTED`）；
      ③ **判不出就保持空**并报数 —— 不硬塞、也不让整次恢复失败。
    """
    from app.mod03_notice.notice_actions import refill_ownership

    with session_scope() as s:
        p = pj_repo.create_project(s, project_type=TYPE_NORMAL,
                                   name_full="__自检_恢复归属__项目",
                                   warehouse_name="__自检_恢复归属__仓库__", phid="")
        s.flush()
        hit = PaymentNotice(ph_id="__自检_ph_恢复归属_命中__", doc_date="2026-08-23",
                            project_name="__自检_恢复归属__项目(TBLX999)",
                            fields={"BillName": "自检单据"}, category="jc",
                            ownership_id=None, excluded=False, exclude_source="")
        manual = PaymentNotice(ph_id="__自检_ph_恢复归属_已指定__", doc_date="2026-08-23",
                               project_name="__自检_恢复归属__项目(TBLX999)",
                               fields={"BillName": "自检单据"}, category="jc",
                               ownership_id=int(p.id), excluded=False, exclude_source="")
        none = PaymentNotice(ph_id="__自检_ph_恢复归属_判不出__", doc_date="2026-08-23",
                             project_name="__自检_压根没有这个项目__",
                             fields={"BillName": "自检单据"}, category="jc",
                             ownership_id=None, excluded=False, exclude_source="")
        s.add_all([hit, manual, none])
        s.flush()
        ids = [int(hit.id), int(manual.id), int(none.id)]

        rep = refill_ownership(s, ids)
        assert rep.filled == [ids[0]], f"归一化后应能命中档案（实际={rep.filled}）"
        assert rep.kept == [ids[1]], "已指定过归属的行不该被回填覆盖"
        assert rep.unresolved == [ids[2]], "判不出的行应如实进 `unresolved`（不硬塞归属）"
        assert hit.ownership_id == int(p.id), "回填没落到行上"
        assert none.ownership_id is None, "判不出的行不该被塞一个归属"
        assert "未建档" in rep.message, "回执没告诉人「判不出」时会看到什么"
        assert "保持不变" in rep.message, "回执没说明已指定过的行保持不变"
        # 端点回执拼上这段（前端原样显示）
        assert refill_ownership(s, []).message == "", "空 id 不该产生任何回执噪音"
        s.rollback()


def test_恢复剔除端点真的调了回填_不是只写了函数没人用():
    """⚠️ 上一条只测了 `refill_ownership` **函数本身** —— 把它从端点上摘掉，那条照样绿。
    ⇒ 这条钉**端点 → 回填**这段接线（反向灵敏度：端点里改成 `refill_ownership(session, [])` ⇒ 本条必红）。

    场景 = 抓取时的真实形态：规则剔除行 `ownership_id=None`、项目全名与档案全名差一段 i8 编号。
    """
    from app.mod03_notice.notice_api_router import IdsIn, api_restore

    with session_scope() as s:
        p = pj_repo.create_project(s, project_type=TYPE_NORMAL,
                                   name_full="__自检_端点回填__项目",
                                   warehouse_name="__自检_端点回填__仓库__", phid="")
        s.flush()
        n = PaymentNotice(ph_id="__自检_ph_端点回填__", doc_date="2026-08-23",
                          project_name="__自检_端点回填__项目(TBLX888)",
                          fields={"BillName": "自检单据"}, category="jc",
                          ownership_id=None, excluded=True, exclude_source="rule")
        s.add(n)
        s.flush()
        nid = int(n.id)

        r = api_restore(IdsIn(ids=[nid]), session=s)
        assert r["ok"] is True and r["restored"] == [nid], f"恢复没成功：{r}"
        assert r.get("ownership_filled") == [nid], \
            f"恢复后**没有回填归属**（这正是用户报障那条）：{r}"
        assert "回填" in r["message"], f"回执没提回填：{r['message']!r}"
        s.expire_all()
        assert s.get(PaymentNotice, nid).ownership_id == int(p.id), "归属没落到行上"
        s.rollback()


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


def test_解绑_零金额引用_与非集采分类不许填供应商():
    """实现层自检（⛔ 不绑判据点）—— 三件容易漏的事。"""
    from app.mod03_notice.notice_actions import jc_supplier_problem

    with session_scope() as s:
        p = _project(s)
        c = _contract(s, project_id=p.id)
        # ① **零金额也允许引用**：关联是"关系"，不是"录入" ⇒ ⛔ 不受"子表金额必须 > 0"那条约束
        # 统计付款为零也保持零，不回退审批金额。
        n0 = _notice(s, ph="__自检_ph_零额__", paid="0", approved="0")
        r = SV.act_link_notice(s, notice_id=n0.id, contract_id=c.id)
        assert r["ok"] is True, "金额为 0 也必须能关联（金额以后核，关系先建上）"
        assert Decimal(str(R.payment_of_notice(s, n0.id).amount)) == Decimal("0")
        # 审批额有值也不能当成统计付款额
        n1 = _notice(s, ph="__自检_ph_兜底__", paid="0", approved="888")
        SV.act_link_notice(s, notice_id=n1.id, contract_id=c.id)
        assert R.payments_of(s, c.id)[-1]["amount"] == Decimal("0.00")
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


def test_集采走付款域同一通道_识别方式只认收款单位():
    """⭐ `DEV-P-05`（§4.4.3）：**集采付款走付款计划、⛔ 不独立成通道**；
    识别方式 = **收款单位「资产处集中采购」**。2026-09-20 由「口径侧登记（待回问）」转为判据点。

    ⚠️ 这条此前**缺**，不是"测试没写"，而是**口径本身**没写死"怎么认" —— 基线 `C_dev_boundary`
       自己记着「真缺口是**口径本身缺一条可观测判据**（该补的是口径、不是测试）」，
       计划 §7.3 也明令「`DEV-P-05` 我不自行补判据 …… ⛔ 不在工程里臆造」。
       口径 **2026-09-19 已定**（§4.4.3）⇒ 现在才谈得上落判据。

    钉的是**这条链**（⛔ 不重复已有的三条：分类三类 / 禁配剔除规则 / 双向关联）：

    ```
    收款单位「资产处集中采购」
      ⇒ 付款域出口   mod05_flow.domain.classify            = 集采
      ⇒ 通知书域出口 mod03_notice.classify.decide_placement = 集采，且 excluded=False（不参与剔除）
      ⇒ 两域说的"集采"是【同一个值】⇒ 走的是【同一条通道】，⛔ 没有第二条
      ⇒ 且该行真的能走完付款域那条路（可关联集采合同 / 可填集采实际供应商）
    ```

    ⚠️⚠️ 为什么值得一条判据：这里有 **两个字面量 + 两个出口**，只要有一处独立漂移，
       "**怎么认**"就**静默分叉** —— 分类说它是集采、禁配规则按另一串认、关联又是第三套
       ⇒ 界面上一切正常，只有真机撞上才发现（本项目最贵的一类错）。
    """
    from app.mod03_notice import classify as NC
    from app.mod03_notice.notice_actions import jc_supplier_problem
    from app.mod05_flow import domain as FD
    # ⚠️ 复用**同一个**记录构造器（`tests.test_classify._rec`）⇒ ⛔ 不另造一份"记录形状"，
    #    否则两处形状一漂，这条断言测的就不是同一种输入了。
    from tests.test_classify import _rec

    # ① **识别字面量只有一份** —— 两处必须就是同一串（⛔ 不是"碰巧相等、将来可能各改一半"）
    assert FD.PAYEE_JC == NC.FORBIDDEN_PAYEE_VALUE == "资产处集中采购", (
        f"「集采」的识别方式在两处分叉了：mod05={FD.PAYEE_JC!r} · mod03={NC.FORBIDDEN_PAYEE_VALUE!r}")

    # ② **付款域出口**：识别靠「收款单位」；优先级 = 机械 > 集采 > 辅材（§4.2.3 的顺序）
    assert FD.classify("", FD.PAYEE_JC) == FD.CATEGORY_JC, "收款单位 = 资产处集中采购 ⇒ 集采"
    assert FD.classify("付设备租赁款", FD.PAYEE_JC) == FD.CATEGORY_MECH, (
        "「付设备租赁款」**优先于**集采收款单位（§4.2.3 的三档顺序）")
    assert FD.classify("", "某某公司") == FD.CATEGORY_MATERIAL, "其余 ⇒ 辅材（⛔ 没有第四类）"

    # ③ **通知书域出口**：同一行必须给**同一个分类**，且**不参与剔除**
    pl = NC.decide_placement(_rec(payee=NC.FORBIDDEN_PAYEE_VALUE))
    assert pl.category == FD.CATEGORY_JC, (
        f"付款域与通知书域对同一行给了不同分类：{pl.category!r} vs {FD.CATEGORY_JC!r}")
    assert pl.excluded is False, "集采**不走剔除**（§4.2.2：它参与分类）"

    # ④ **"同一条通道"的机器化落点**：集采分类的行**能**走完付款域那条路 ——
    #    可关联集采合同 ＋ 可填「集采实际供应商」。⛔ 没有"集采专用"的第二条路。
    with session_scope() as s:
        p = _project(s)
        c = _contract(s, project_id=p.id)
        n = _notice(s, ph="__自检_ph_集采通道__")
        assert jc_supplier_problem(n) is None, "集采分类的行要能填「集采实际供应商」"
        r = SV.act_link_notice(s, notice_id=n.id, contract_id=c.id)
        assert r["ok"] is True, f"集采分类的行要能关联集采合同（走的就是付款域那条路）：{r}"
        assert R.payment_of_notice(s, n.id) is not None
        assert _links_by_notice(s)(n.id), "付款域侧也要看得到（双向可见）"
        s.rollback()
