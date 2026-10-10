"""`MOD-11` 集采台账 · **装配层**（把仓储行 + 域内核算成"页面要的形状"；⛔ 不写判定）。

⭐ 本层是**派生金额的唯一落点**：发票合计 / 付款合计 / 结算 / 欠款**全部现场算**
   （`domain.contract_amounts`）—— §6.4.1 末行要求"派生显示、不单独存储"，
   判据 `ACC-JC-UI-001/001-09` 要的"**改子表即改欠款**"就是靠"每次现算"满足的。

⚠️ 出参是**语义形状**；转成原型演示形状是**壳适配层**的职责（后端出语义、前端 `adapt*` 转形）。
⚠️ 金额在 `api` 层转字符串（`numeric(18,2)` 精度保护）⇒ 本层照实回 `Decimal`。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.mod11_jc import domain as D
from app.mod11_jc import repository as R
from app.mod11_jc.models import INVOICE_KINDS, SRC_MANUAL, SRC_NOTICE, TAG_IN, JcPayment
from app.core.money import sum_money


def build_list(s: Session, *, tags: list[str] | None = None, arch: str = "",
               supplier: str = "", project_key: str = "") -> dict:
    """集采台账**主表**（含派生金额与合计行）—— 判据 `ACC-JC-UI-001/001-02` / `001-11` 的数据源。

    ⚠️ **筛选后的行数就是 `count`**；判据要求「筛选后行数 = **独立复算**、**复位后回到全量**」⇒
       本函数**不缓存、不带隐式默认筛选**（不给参数 = 全量）。
    """
    rows = R.list_contracts(s, tags=tags, arch=arch, supplier=supplier, project_key=project_key)
    inv_map = R.invoices_of_many(s, [r["id"] for r in rows])
    pay_map = R.payments_of_many(s, [r["id"] for r in rows])

    out: list[dict] = []
    totals = {k: D.ZERO for k in D.SUM_KEYS}
    for r in rows:
        amounts = D.contract_amounts(
            trade_co=r["trade_co"],
            invoices=inv_map.get(r["id"], []),
            payments=pay_map.get(r["id"], []),
        )
        row = {**r, **amounts}
        # ⭐ **本行引用过的付款通知书 id**（`M5-7` 接线时补 —— 子表**本来就在内存里**，只差带出来）。
        # ⚠️ 为什么必须带：`m03`（付款通知书页）的「集采关联」是**反查**的 ——
        #    `jcUsedNids`（全库已引用集合）· `jcRefOf`（这条被哪张合同引用）· `jcLinkCands`（候选）
        #    全都按"合同行的付款子表里有没有这个通知书 id"来判。**不带 ⇒ 它们静默变空**
        #    （候选列表消失，页面看起来只是"没数据"，不报错）—— 这正是"接后端时最该防"的那类错。
        # ⛔ 只给 **id 集合**，⛔ 不搬整张子表（那是 `/api/m11/detail` 的活）。
        row["notice_ids"] = [int(p["notice_id"]) for p in (pay_map.get(r["id"]) or [])
                             if p.get("notice_id") is not None]
        for k in D.SUM_KEYS:
            totals[k] = totals[k] + Decimal(str(row.get(k) or 0))
        out.append(row)

    return {
        "rows": out,
        "count": len(out),
        "totals": {k: v.quantize(Decimal("0.01")) for k, v in totals.items()},
        "columns": [dict(c) for c in D.JC_COLUMNS],
        "projects": R.project_choices(s),
    }


def payment_display_rows(s: Session, payments: list[dict]) -> list[dict]:
    """统计与实付一致才按笔展示；关联与合同金额仍用原始付款行。"""
    from app.mod05_flow import service as flows

    ids = [int(p["notice_id"]) for p in payments if p["source"] == SRC_NOTICE and p["notice_id"] is not None]
    by_notice: dict[int, list] = {}
    for f in flows.flows_of_notices(s, ids):
        if f.status == "effective":
            by_notice.setdefault(f.notice_id, []).append(f)
    out = []
    for p in payments:
        if p["source"] != SRC_NOTICE:
            out.append({**p, "display_kind": "manual"})
            continue
        live = by_notice.get(p["notice_id"], [])
        if not live and p["amount"] == 0:
            continue
        if live and p["amount"] == sum_money(f.amount for f in live):
            out.extend({**p, "date": f.pay_date, "amount": f.amount,
                        "flow_id": f.id, "display_kind": "flow"} for f in live)
        else:
            out.append({**p, "display_kind": "stat", "mismatch": True})
    return out


def notice_payment_effect(s: Session, notice_id: int) -> dict | None:
    """读取关联合同的付款合计，供撤销事务前后回执使用。"""
    link = R.payment_of_notice(s, notice_id)
    if link is None:
        return None
    c = R.contract_of(s, link.contract_id)
    amounts = D.contract_amounts(trade_co=c.trade_co, invoices=R.invoices_of(s, c.id),
                                 payments=R.payments_of(s, c.id))
    return {"contract_id": c.id, "pay_sum": amounts["pay_sum"]}


def build_detail(s: Session, contract_id: int) -> dict | None:
    """单个合同的**明细**（两张发票子表 + 付款子表 + 派生金额）—— 子表弹窗的数据源。

    ⚠️ 两张发票子表**同款同规则**（§6.4.2）⇒ 这里按 `kind` 分组返回，⛔ 不写两套取数。
    """
    c = R.contract_of(s, contract_id)
    if c is None:
        return None
    invoices = R.invoices_of(s, contract_id)
    payments = R.payments_of(s, contract_id)
    amounts = D.contract_amounts(trade_co=c.trade_co, invoices=invoices, payments=payments)
    return {
        "id": c.id,
        "date": c.contract_date,
        "material": c.material_name,
        "supplier": c.supplier,
        "contract_amt": c.contract_amt,
        "trade_co": c.trade_co,
        "trade_contract_amt": c.trade_contract_amt,
        "method": c.method,
        "remark": c.remark,
        "tag": c.tag,
        "arch": c.arch,
        "arch_no": c.arch_no,
        "ret_date": c.ret_date,
        "supplier_invoices": [r for r in invoices if r["kind"] != "trade"],
        "trade_invoices": [r for r in invoices if r["kind"] == "trade"],
        "payments": payments,
        "payment_display_rows": payment_display_rows(s, payments),
        **amounts,
    }


def debt_of_ledger(s: Session) -> Decimal:
    """**集采欠款合计**（⭐ **只计「纳入台账」**的合同）—— 供付款域**注入**用（`TAIL-100`）。

    ⚠️ **为什么必须有它**：付款域的口径是「集采欠款**不在本域算** —— 由集采台账负责」
       （§4.5.1 / 判据 `ACC-FLOW-DEBT-001/001-03`）⇒ 那边**需要一个注入方**。
       而原先这个"注入方"**从来没人实现** ⇒ 看板与欠款页的「集采欠款」**恒 ¥0.00**
       （少算 7444 万级、页面还完全看不出来 —— 典型的「看着正常的错数」）。
    ⭐ **唯一出口**：算法留在集采域（⛔ 付款域不自己 sum），取值走 `build_list`
       ⇒ 与**集采台账页**显示的「集采欠款」**必然是同一个数**。
    """
    total = D.ZERO
    for r in build_list(s)["rows"]:
        if str(r.get("tag") or "") == TAG_IN:
            total += Decimal(str(r.get("debt") or 0))
    return total.quantize(Decimal("0.01"))


# ============================================================ 写动作（`M5-4`）
# ⚠️ 判定（三态归一 / 子表校验 / 去重）一律调 `domain` 出口；本层只做**编排 ＋ 回执**。
# ⚠️ 回执统一形状 `{"ok", "kind", "message", ...}`（同 `m09` 手写动作的口径）；⛔ 不抛业务异常。

#: 手工新增 / Excel 导入的**两态默认值** = 「纳入台账」。
#: 依据：判据 `ACC-JC-FETCH-001/001-07` **原文**就是「三态默认值 = 纳入台账」（现为两态）。
#: ⭐ `TAIL-97`（用户 2026-09-25 取消「待确认」）之后：**抓取与手工新增的默认值已经合流**
#:   —— 两条路都是 `TAG_IN`（`models.JcContract.tag` 的列默认也一并改成它）。
#:   ⚠️ 本常量**保留**：它仍是"人工新增这一条路"的名义出口（判据 `001-07` 指着它）。
DEFAULT_TAG_ON_CREATE = TAG_IN


def act_add_contract(s: Session, *, project_id: int, **fields) -> dict:
    """手工新增合同 ⇒ **建档**（判据 `ACC-JC-UI-001/001-13`「保存真的建档」）。

    ⚠️「取消不入库」= 前端**不调本接口**（本接口一旦被调用就落库）⇒ 本层⛔ 没有"草稿态"。
    """
    tag = D.normalize_tag(fields.pop("tag", None) or DEFAULT_TAG_ON_CREATE)
    row = R.insert_contract(s, project_id=int(project_id), tag=tag, **fields)
    return {"ok": True, "kind": "ok", "id": int(row.id), "tag": tag,
            "message": f"已建档（三态 = 「{tag}」）"}


def act_set_tag(s: Session, *, contract_id: int, tag) -> dict:
    """单条三态标记（判据 `001-03` 的"逐条"那一半）。"""
    t = D.normalize_tag(tag)
    if not R.set_tag(s, contract_id, t):
        return {"ok": False, "kind": "err", "message": f"找不到合同 {contract_id}"}
    return {"ok": True, "kind": "ok", "id": int(contract_id), "tag": t,
            "message": f"已标记为「{t}」"}


def act_batch_tag(s: Session, *, contract_ids, tag) -> dict:
    """**批量**三态标记（判据 `001-03` 的"批量"那一半 ＋ `001-05`）。

    ⭐ `001-05` 的三条：**只作用于勾选行** · **动作后清空勾选** · **不改行数**
    ⇒ 返回 `affected_ids`（壳据此清空**刚标过的那些**勾选），并返回**前后行数**
    （把"不改行数"做成**可观测**的 —— 断言另用 SQL 独立复算，⛔ 不靠本接口自证）。
    """
    t = D.normalize_tag(tag)
    ids = [int(i) for i in (contract_ids or ())]
    if not ids:
        return {"ok": False, "kind": "err", "message": "请先勾选要标记的行", "affected_ids": []}
    before = R.count_contracts(s)
    affected = R.set_tags(s, ids, t)
    after = R.count_contracts(s)
    return {"ok": True, "kind": "ok", "tag": t, "affected_ids": affected,
            "count": len(affected), "row_count_before": before, "row_count_after": after,
            "message": f"已把 {len(affected)} 行标记为「{t}」"}


def act_update_contract(s: Session, *, contract_id: int, **cols) -> dict:
    """主表可改列（备注 / 付款方式 / 收发登记三列 / 金额…）—— 判据 `001-12`「可手改并落值」。

    ⚠️ 白名单在 `repository.EDITABLE_COLS`（三态**不在其中** ⇒ 它走 `act_set_tag`）。
    """
    if not R.update_contract(s, contract_id, **cols):
        return {"ok": False, "kind": "err", "message": f"找不到合同 {contract_id}"}
    return {"ok": True, "kind": "ok", "id": int(contract_id), "message": "已保存"}


def act_add_invoice(s: Session, *, contract_id: int, kind: str, date, amount) -> dict:
    """发票子表增行（供应商 / 贸易公司**同款**）—— 校验走 `D.invoice_problem`（判据 `001-05`）。"""
    if str(kind) not in INVOICE_KINDS:
        return {"ok": False, "kind": "err", "message": f"不认识的子表类型：{kind}"}
    bad = D.invoice_problem(date, amount)
    if bad:
        return {"ok": False, "kind": "err", "message": bad}
    row = R.insert_invoice(s, contract_id=contract_id, kind=str(kind),
                           invoice_date=date, amount=D.parse_amount(amount))
    return {"ok": True, "kind": "ok", "id": int(row.id), "message": "已增发票行"}


def act_del_invoice(s: Session, *, invoice_id: int) -> dict:
    """发票子表删行。"""
    if not R.delete_invoice(s, invoice_id):
        return {"ok": False, "kind": "err", "message": f"找不到发票行 {invoice_id}"}
    return {"ok": True, "kind": "ok", "message": "已删除"}


def act_add_payment(s: Session, *, contract_id: int, date, amount,
                    source: str = SRC_MANUAL, notice_id=None) -> dict:
    """付款子表增行 —— **同款**校验（`D.payment_problem`）；引用付款域时先过**全库去重**。

    ⚠️ 去重范围 = **全库、不分合同**（§6.6.2）⇒ 入参是 `R.notice_ids_used(s)` 的全集。
    """
    bad = D.payment_problem(date, amount)
    if bad:
        return {"ok": False, "kind": "err", "message": bad}
    if str(source) == SRC_NOTICE and D.dedup_blocked(
            notice_id=notice_id, existing_notice_ids=R.notice_ids_used(s)):
        return {"ok": False, "kind": "err",
                "message": "该付款通知书已被引用过（全库去重，不分合同）"}
    row = R.insert_payment(s, contract_id=contract_id, pay_date=date,
                           amount=D.parse_amount(amount), source=source, notice_id=notice_id)
    return {"ok": True, "kind": "ok", "id": int(row.id), "message": "已增付款行"}


def act_del_payment(s: Session, *, payment_id: int) -> dict:
    """删除手工付款行；通知书关系由正式解绑入口处理。"""
    row = s.get(JcPayment, int(payment_id))
    if row is not None and row.source == SRC_NOTICE:
        return {"ok": False, "kind": "err", "message": "请到付款通知书页改关联或解绑"}
    if not R.delete_payment(s, payment_id):
        return {"ok": False, "kind": "err", "message": f"找不到付款行 {payment_id}"}
    return {"ok": True, "kind": "ok", "message": "已删除"}


# ---------------------------------------------------------------- 付款域双向引用（`M5-5`）

def act_link_notice(s: Session, *, notice_id: int, contract_id: int) -> dict:
    """**关联**：把这笔集采付款通知书关联到一张集采合同 ⇒ 写合同的**付款子表**（`source=notice`）。

    ⭐ 判据 `ACC-JC-PAY-001/001-01`「两个方向写**同一份**关联记录、**双向可见**」——
       本函数就是那两个方向（`m03` 侧「关联集采合同」与集采侧「从付款域引用 R8」）的**唯一落库口**；
       `m03` 那边的"已关联"态由 `list_view._links_by_notice` **读同一张付款子表**得出 ⇒ 双向可见是**自然结果**。
    ⭐ 判据 `001-03`「一条通知书**只能关联一个合同**（换合同 = **先解绑再写新**）」⇒ 见下面第 1 步。
    ⚠️ **⛔ 不做金额校验**（判据 `001-04`：通知书金额与合同欠款不一致 ⇒ **只提示、不拦**）。
       注意这与"子表**手工录入**金额必须 > 0"**不冲突** —— 那条管的是**录入**，这里是**引用既有付款事实**：
       关联只记录关系；读取时动态取通知书**统计付款金额**，零值保持零，不回退审批金额。
    """
    from app.mod03_notice.models import PaymentNotice
    from app.mod11_jc.models import JcContract

    if s.get(PaymentNotice, int(notice_id)) is None:
        return {"ok": False, "kind": "err", "message": f"找不到付款通知书 {notice_id}"}
    if s.get(JcContract, int(contract_id)) is None:
        return {"ok": False, "kind": "err", "message": f"找不到集采合同 {contract_id}"}

    # 1) **一对一**：换合同 ⇒ 先把旧的那条关联记录摘掉（判据 `001-03`「先解绑再写新」）
    old = R.payment_of_notice(s, notice_id)
    moved_from = None
    if old is not None:
        if int(old.contract_id) == int(contract_id):
            return {"ok": True, "kind": "ok", "contract_id": int(contract_id), "changed": False,
                    "message": f"这行通知书已经关联在集采合同 #{contract_id} 上（未重复关联）"}
        moved_from = int(old.contract_id)
        R.delete_payment(s, old.id)

    # 2) 兜底再判一次**全库去重**（域内核出口；正常在上面已摘干净 ⇒ 这里只在边界上护一道）
    if D.dedup_blocked(notice_id=notice_id, existing_notice_ids=R.notice_ids_used(s)):
        return {"ok": False, "kind": "err",
                "message": "该付款通知书已被引用过（全库去重，不分合同）—— 请刷新后重试"}

    row = R.insert_payment(s, contract_id=int(contract_id), pay_date="",
                           amount=0, source=SRC_NOTICE, notice_id=int(notice_id))
    return {"ok": True, "kind": "ok", "changed": True, "payment_id": int(row.id),
            "contract_id": int(contract_id), "moved_from": moved_from,
            "message": (f"已从集采合同 #{moved_from} 改关联到 #{contract_id}"
                        if moved_from else f"已关联到集采合同 #{contract_id}")}


def act_unlink_notice(s: Session, *, notice_id: int) -> dict:
    """**解绑**：摘掉这条通知书的关联记录（= 删合同的付款子表里那条 `source=notice` 行）。

    ⚠️ 解绑后**两侧同时**变回"未关联"（因为只有一份记录）—— 这正是双向可见的另一面。
    """
    old = R.payment_of_notice(s, notice_id)
    if old is None:
        return {"ok": False, "kind": "err", "message": "这行通知书当前没有关联集采合同"}
    cid = int(old.contract_id)
    R.delete_payment(s, old.id)
    return {"ok": True, "kind": "ok", "contract_id": cid,
            "message": f"已取消与集采合同 #{cid} 的关联（两侧同时解除）"}


# ---------------------------------------------------------------- 导出（`M5-9`）

def export_xlsx(s: Session, *, ids: list[int]) -> bytes:
    """把**页面上当前看到的那些行**导出成一本 xlsx ⇒ 字节。

    ⭐ **为什么收 `ids` 而不是"筛选条件"**：页面的筛选是**前端**算的（还含「合同金额为空/非空」
      这种 `build_list` 里没有的条件）⇒ 传条件就得在后端**再实现一遍** ⇒ **两套口径必打架**。
       传 id ⇒ **行集合就是前端看到的那些**，口径 100% 一致。
    ⚠️ 所以这里先 `build_list(s)`（**不带筛选 = 全量**，拿到派生金额）再**按 id 收窄**：
       多算了一点，但换到的是"导出与屏幕**逐行一致**"——这笔账在本项目永远划算。
    ⚠️ 空 `ids` ⇒ **空表**（不回落全量）：⛔ "我一列都没勾/筛出 0 行，却导出了整本台账" 是最坏的一种意外。
    """
    from app import export_registry as EXP
    jc_export = EXP.get("jc")

    want = {int(x) for x in (ids or ())}
    if not want:
        return jc_export.build_xlsx([])
    data = build_list(s)
    all_rows = data.get("rows") or data.get("items") or []
    rows = [r for r in all_rows if int(r.get("id") or 0) in want]
    return jc_export.build_xlsx(rows)


# ---------------------------------------------------------------- 甲方单位分类（`M5-6b`）

def party_kinds(s: Session) -> dict:
    """甲方单位分类清单 ＋ **每类下的合同条数** —— `M5-6b` 的读出口（页面用）。

    ⚠️ 条数**现场算**（⛔ 不落库）：落库就是第二份真相（本模块一贯口径）。
    ⭐ `unknown` 排在**最前**（`R.list_party_kinds` 保证）—— 那批正是**要人去指定**的。
    """
    from sqlalchemy import select

    from app.mod11_jc.models import KIND_PARTY_UNKNOWN, PARTY_KIND_NAMES, PARTY_KINDS, JcContract

    items = R.list_party_kinds(s)
    by_party: dict[str, int] = {}
    for nm in s.execute(select(JcContract.party_name)).scalars():
        key = str(nm or "").strip()
        if key:
            by_party[key] = by_party.get(key, 0) + 1
    for it in items:
        it["count"] = by_party.get(it["name"], 0)
    # ⚠️ **在册合同里出现过、但分类表里没有**的甲方（理论上不该有 —— 抓取时会 `ensure`）
    #    ⇒ 若真出现（如手工新增 / Excel 导入带进来的甲方名），**列出来**，⛔ 不静默忽略。
    listed = {it["name"] for it in items}
    for nm, cnt in sorted(by_party.items()):
        if nm not in listed:
            items.append({"name": nm, "kind": KIND_PARTY_UNKNOWN,
                          "kind_name": PARTY_KIND_NAMES[KIND_PARTY_UNKNOWN], "count": cnt})
    unknown = sum(1 for it in items if it["kind"] == KIND_PARTY_UNKNOWN)
    return {"ok": True, "items": items, "unknown": unknown,
            "kinds": list(PARTY_KINDS), "kind_names": PARTY_KIND_NAMES}


def act_set_party_kind(s: Session, *, name: str, kind: str) -> dict:
    """指定某甲方单位的类型（`M5-6b`）—— ⛔ 类型非法一律拒（判定**在后端**，前端不自行判）。

    ⚠️ ⚠️ **只改分类，不回头重算已有合同的金额落位** —— 这与 §4.2.2「改规则不重算历史」同款：
       已经落错列的行，改完分类后**由人重抓一次或手改**（页面对这类行会提示）。
       ⛔ 别在这里补一个"顺便重算"—— 那会**静默改动历史金额**，是本项目最忌的一类动作。
    """
    from app.mod11_jc.models import PARTY_KIND_NAMES, PARTY_KINDS

    nm = str(name or "").strip()
    if kind not in PARTY_KINDS:
        return {"ok": False, "kind": "err", "message": f"未知的甲方类型：{kind}"}
    if not nm:
        return {"ok": False, "kind": "err", "message": "甲方单位名不能为空"}
    R.set_party_kind(s, nm, kind)
    return {"ok": True, "kind": "ok", "name": nm, "party_kind": kind,
            "message": f"已把「{nm}」标为「{PARTY_KIND_NAMES.get(kind, kind)}」"}


__all__ = [
    "build_list", "build_detail", "debt_of_ledger",
    "DEFAULT_TAG_ON_CREATE", "act_add_contract", "act_set_tag", "act_batch_tag",
    "act_update_contract", "act_add_invoice", "act_del_invoice",
    "act_add_payment", "act_del_payment",
    "act_link_notice", "act_unlink_notice",
    "party_kinds", "act_set_party_kind",
]
