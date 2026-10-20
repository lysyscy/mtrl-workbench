"""`ACC-JC-*`（M5 集采域）· **读路径**（仓储 ＋ 装配 ＋ `/api/m11/*`）的验收断言。

⚠️ 库级断言**一律非破坏**：本机测试连的是**同一个测试库** ⇒ 每个用例末尾 `s.rollback()`（⛔ 一行不留）。

逐条对应（`claim` 原文见验收基线）：
- `ACC-JC-UI-001/001-02` 主表「项目」字段存在且**筛选键 = 仓库名**；筛选后行数 = **独立复算**、**复位后回到全量**
- `ACC-JC-UI-001/001-09` 主表金额列 = 只读汇总：**改子表即改欠款**（这里走真库 ＋ 装配再验一遍）
- `ACC-JC-UI-001/001-11` 「合计」行各金额列 = **独立复算**
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.core.db import session_scope
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL, Project
# ⚠️ `jc_payment.notice_id` 的外键指向 `payment_notice` ⇒ 触库前该模型必须在**元数据里注册**
#    （生产侧由 `main.py` import 各 router 顺带注册；测试进程没有那一步 ⇒ 显式引一次）。
from app.mod03_notice import models as _m03  # noqa: F401
from app.mod11_jc import domain as D
from app.mod11_jc import service as SV
from app.mod11_jc.models import TAG_IN, JcContract, JcInvoice, JcPayment

WH_A = "__自检仓_集采甲__"
WH_B = "__自检仓_集采乙__"


def _project(s, wh: str) -> Project:
    """造一个自检档案行（键 = 仓库名 · §2.7.4；用完 rollback ⇒ ⛔ 不留痕）。"""
    row = pj_repo.create_project(
        s, project_type=TYPE_NORMAL, name_full=f"{wh}项目", warehouse_name=wh, phid=""
    )
    s.flush()
    return row


def _contract(s, *, project_id: int, date: str, supplier: str, amount: str, tag: str = TAG_IN) -> JcContract:
    row = JcContract(project_id=int(project_id), contract_date=date, material_name="自检材料",
                     supplier=supplier, contract_amt=Decimal(amount), tag=tag)
    s.add(row)
    s.flush()
    return row


def _invoice(s, contract_id: int, kind: str, date: str, amount: str) -> JcInvoice:
    row = JcInvoice(contract_id=int(contract_id), kind=kind, invoice_date=date, amount=Decimal(amount))
    s.add(row)
    s.flush()
    return row


def _payment(s, contract_id: int, date: str, amount: str, source: str = "manual",
             notice_id: int | None = None) -> JcPayment:
    row = JcPayment(contract_id=int(contract_id), pay_date=date, amount=Decimal(amount),
                    source=source, notice_id=notice_id)
    s.add(row)
    s.flush()
    return row


def test_项目筛选键是仓库名_且筛选后行数独立复算_复位回全量():
    """⭐ 判据三条：① 键 = **仓库名**；② 筛选后行数 = **独立复算**；③ **复位后回到全量**。"""
    with session_scope() as s:
        pa, pb = _project(s, WH_A), _project(s, WH_B)
        _contract(s, project_id=pa.id, date="2026-09-01", supplier="业祥", amount="1000")
        _contract(s, project_id=pb.id, date="2026-09-02", supplier="尚坤", amount="2000", tag=TAG_IN)
        _contract(s, project_id=pb.id, date="2026-09-03", supplier="尚坤", amount="3000")

        # ① 筛选键 = 仓库名（⛔ 不是 project_id、也不是展示名）
        rows_a = SV.build_list(s, project_key=WH_A)["rows"]
        assert len(rows_a) == 1 and rows_a[0]["project_key"] == WH_A, "按仓库名筛：甲仓恰 1 条"

        # ② 独立复算：**另起一条 SQL 数**，⛔ 不用被测函数的返回值自证
        cnt_b = s.execute(
            select(func.count()).select_from(JcContract)
            .join(Project, Project.id == JcContract.project_id)
            .where(Project.warehouse_name == WH_B)
        ).scalar_one()
        rows_b = SV.build_list(s, project_key=WH_B)["rows"]
        assert len(rows_b) == int(cnt_b) == 2, f"乙仓独立复算 = {cnt_b}；筛选结果行数必须与之一致"

        # ③ 复位（不给任何筛选）= 全量：必须**包含**前面筛出来的行，且 count 与 rows 自洽
        all_ = SV.build_list(s)
        assert all_["count"] == len(all_["rows"]), "count 必须 = 返回行数（别让两处各算一遍）"
        assert {r["id"] for r in rows_a + rows_b} <= {r["id"] for r in all_["rows"]}, \
            "复位后要回到全量（原先筛出来的必须还在）"

        # 三态筛选（可多值）
        assert all(r["tag"] == TAG_IN for r in SV.build_list(s, tags=[TAG_IN])["rows"]), "三态筛选必须逐行生效"
        s.rollback()


def test_派生金额由子表现算_改子表即改欠款():
    """⭐ 「**改子表即改欠款**」在**真库 ＋ 装配**上再验一遍（域内核那条是纯函数层）。"""
    with session_scope() as s:
        p = _project(s, WH_A)
        c = _contract(s, project_id=p.id, date="2026-09-05", supplier="业祥", amount="9999")
        _invoice(s, c.id, "supplier", "2026-09-06", "1000")
        _payment(s, c.id, "2026-09-07", "400")

        row = next(r for r in SV.build_list(s, project_key=WH_A)["rows"] if r["id"] == c.id)
        assert row["settle"] == Decimal("1000.00") and row["debt"] == Decimal("600.00"), \
            "结算 = 子表合计；欠款 = 结算 − 付款"

        # 再加一张发票 ⇒ 同一入口**立刻**反映（⇒ 不存在"主表存了一份、忘了同步"）
        _invoice(s, c.id, "supplier", "2026-09-08", "250")
        row2 = next(r for r in SV.build_list(s, project_key=WH_A)["rows"] if r["id"] == c.id)
        assert row2["settle"] == Decimal("1250.00") and row2["debt"] == Decimal("850.00"), \
            "改子表即改欠款（经真库 ＋ 装配）"

        # 明细入口（子表弹窗的数据源）：两张同款发票子表**分开给**，付款子表另给
        detail = SV.build_detail(s, c.id)
        assert detail is not None and [r["amount"] for r in detail["supplier_invoices"]] == \
            [Decimal("1000.00"), Decimal("250.00")] and detail["trade_invoices"] == []
        assert len(detail["payments"]) == 1 and detail["debt"] == Decimal("850.00")
        s.rollback()


def test_合计行各金额列独立复算():
    """合计 = **逐行现算后相加**；这里用原生算术独立复算一遍（⛔ 不调 `service` 的合计）。"""
    with session_scope() as s:
        p = _project(s, WH_A)
        c1 = _contract(s, project_id=p.id, date="2026-09-09", supplier="业祥", amount="1000")
        c2 = _contract(s, project_id=p.id, date="2026-09-10", supplier="尚坤", amount="500")
        _invoice(s, c1.id, "supplier", "2026-09-11", "300")
        _invoice(s, c2.id, "supplier", "2026-09-12", "200")

        data = SV.build_list(s, project_key=WH_A)
        rows = data["rows"]
        assert rows, "自检仓下必须至少有一行（否则这条断言在空数据上就成「假绿」了）"
        assert data["totals"]["contract_amt"] == sum(r["contract_amt"] for r in rows), "合同金额列独立复算"
        assert data["totals"]["settle"] == sum(r["settle"] for r in rows), "结算列独立复算"
        assert data["totals"]["debt"] == sum(r["debt"] for r in rows), "欠款列独立复算"
        s.rollback()


def test_去重集合是全库的_跨合同也算已引用():
    """⭐ 判据原文点明「**不分合同**」⇒ 去重集合必须从**全库**取（不是"本合同的付款"）。

    这是 `repository.notice_ids_used`（取全集）＋ `domain.dedup_blocked`（判重）的**联动**断言。
    """
    from app.mod03_notice.models import PaymentNotice
    from app.mod11_jc import repository as R

    with session_scope() as s:
        p = _project(s, WH_A)
        c1 = _contract(s, project_id=p.id, date="2026-09-13", supplier="业祥", amount="100")
        c2 = _contract(s, project_id=p.id, date="2026-09-14", supplier="尚坤", amount="200")
        # 造两条**真通知书**（`jc_payment.notice_id` 有外键 ⇒ 不能凭空写 id）
        n1 = PaymentNotice(ph_id="__自检_ph_甲__")
        n2 = PaymentNotice(ph_id="__自检_ph_乙__")
        s.add_all([n1, n2])
        s.flush()
        _payment(s, c1.id, "2026-09-15", "50", source="notice", notice_id=n1.id)
        _payment(s, c2.id, "2026-09-16", "60", source="notice", notice_id=n2.id)
        _payment(s, c2.id, "2026-09-17", "70")                      # 手工录入（无通知书 id，不参与去重）

        used = R.notice_ids_used(s)
        assert {n1.id, n2.id} <= used, "去重集合必须含**全库**已引用的通知书（跨合同）"
        assert None not in used and 0 not in used, "手工录入的（无通知书 id）不参与去重"

        # 同一笔（哪怕被**另一张合同**引用过）⇒ 必须判重拦下
        assert D.dedup_blocked(notice_id=n1.id, existing_notice_ids=used) is True, \
            "已被别的合同引用过 ⇒ 也要拦（去重不分合同）"
        assert D.dedup_blocked(notice_id=987654, existing_notice_ids=used) is False
        s.rollback()


def test_列表每行带引用过的通知书id_否则m03的集采关联会静默变空():
    """`M5-7` 接线前补的实现层自检（⛔ 不绑判据点）。

    ⚠️ 这条守的是一个**静默失效点**：`m03`（付款通知书页）的「集采关联」是**反查**的 ——
    `jcUsedNids`（全库已引用集合）· `jcRefOf`（这条被哪张合同引用）都按"合同行的付款子表里有没有这个 id"判。
    列表接口**不带**它 ⇒ 接上壳之后候选列表会**静默变空**（页面看着只是"没数据"，不报错）。
    """
    from app.mod03_notice.models import PaymentNotice
    from app.mod11_jc import repository as R

    with session_scope() as s:
        p = _project(s, WH_A)
        c1 = _contract(s, project_id=p.id, date="2026-09-18", supplier="业祥", amount="100")
        c2 = _contract(s, project_id=p.id, date="2026-09-18", supplier="尚坤", amount="200")
        n1 = PaymentNotice(ph_id="__自检_ph_集采_甲__")
        s.add(n1)
        s.flush()
        _payment(s, c1.id, "2026-09-18", "50", source="notice", notice_id=n1.id)
        _payment(s, c2.id, "2026-09-18", "70")            # 手工录入 ⇒ 无 id ⇒ 不进 notice_ids

        rows = {r["id"]: r for r in SV.build_list(s, project_key=WH_A)["rows"]}
        assert rows[c1.id]["notice_ids"] == [n1.id], "引用了通知书的行必须带出它的 id"
        assert rows[c2.id]["notice_ids"] == [], "手工录入的付款（无通知书 id）不进 notice_ids"

        # 与"全库已引用集合"口径一致（壳侧 `jcUsedNids` 就是从这里派生）
        assert set(rows[c1.id]["notice_ids"]) <= R.notice_ids_used(s)
        s.rollback()


def test_主表字段数20列且列清单与两态取值域只有一个出口():
    """判据 `001-01`「主表字段数与字段名以 §6.4.1 为准」的**可机器化部分**：

    ⚠️ 判据原文说「**不在本文件复述数字**」⇒ 这里只钉两件**结构性**事实：
    ① 列清单**只有一个出口**（`domain.JC_COLUMNS`）且 **19 列**（数量与 §6.4.1 一致）；
    ② **两态**取值域同样只有一个出口（`domain.TAGS`）。⛔ 壳与 API 里都不得另抄一份。
    """
    with session_scope() as s:
        data = SV.build_list(s)
    assert [c["key"] for c in data["columns"]] == [c["key"] for c in D.JC_COLUMNS], "列清单必须来自 domain"
    assert len(data["columns"]) == 19, "§6.4.1 取消付款方式后的 19 列（序号 … 操作）"
    assert D.TAGS == (D.TAG_IN, D.TAG_OUT), "两态取值域的顺序即口径（⛔ 「待确认」已取消）"
