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


__all__ = ["build_list", "build_detail"]
