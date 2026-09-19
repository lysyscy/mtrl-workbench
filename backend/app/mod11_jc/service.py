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
from app.mod11_jc.models import INVOICE_KINDS, SRC_MANUAL, SRC_NOTICE, TAG_IN


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
        **amounts,
    }


# ============================================================ 写动作（`M5-4`）
# ⚠️ 判定（三态归一 / 子表校验 / 去重）一律调 `domain` 出口；本层只做**编排 ＋ 回执**。
# ⚠️ 回执统一形状 `{"ok", "kind", "message", ...}`（同 `m09` 手写动作的口径）；⛔ 不抛业务异常。

#: 手工新增 / Excel 导入的**三态默认值** = 「纳入台账」。
#: 依据：判据 `ACC-JC-FETCH-001/001-07` **原文**就是「三态默认值 = 纳入台账」；
#:   用户 2026-09-19「分来源默认」定案：**抓取 = 待确认** · **手工新增 / 导入 = 纳入台账**。
#:   ⚠️ 所以这里的默认值**不同于** `models.JcContract.tag` 的列默认（那是"新抓取"那条路）——
#:   两条路各有主人，⛔ 别把 `TAG_PENDING` 当唯一默认。
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
    """付款子表删行。"""
    if not R.delete_payment(s, payment_id):
        return {"ok": False, "kind": "err", "message": f"找不到付款行 {payment_id}"}
    return {"ok": True, "kind": "ok", "message": "已删除"}


__all__ = [
    "build_list", "build_detail",
    "DEFAULT_TAG_ON_CREATE", "act_add_contract", "act_set_tag", "act_batch_tag",
    "act_update_contract", "act_add_invoice", "act_del_invoice",
    "act_add_payment", "act_del_payment",
]
