"""`MOD-11` 集采台账 · **仓储层**（只做取数 / 落库，不写判定）。

⚠️ **判定一律调 `domain` 出口**（结算 / 欠款 / 子表校验 / 三态）—— 本文件里⛔ 不出现第二个"结算口径"。
⚠️ **项目键 = 仓库名**（§2.7.4）：比较 / 筛选一律用它，**写库仍按档案 id** ⇒ 本层负责把 `project_id`
   翻译成 `warehouse_name`（`select(Project.warehouse_name)`），⛔ 不让上层各自 join 一遍。
⚠️ 派生金额（发票合计 / 付款合计 / 结算 / 欠款）**一律不落库**（§6.4.1 末行）⇒ 本层只回原始子表行。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod01_projects.models import Project
from app.mod11_jc.models import JcContract, JcInvoice, JcPayment


def _project_key(s: Session, project_id: int) -> tuple[str, str]:
    """`project_id` → `(仓库名, 展示名)`（§2.7.4：**键 = 仓库名**，展示名只用于显示）。"""
    p = s.get(Project, int(project_id)) if project_id else None
    if p is None:
        return "", ""
    return str(p.warehouse_name or ""), str(getattr(p, "display_name", "") or p.warehouse_name or "")


def list_contracts(
    s: Session,
    *,
    tags: list[str] | None = None,
    arch: str = "",
    supplier: str = "",
    project_key: str = "",
) -> list[dict]:
    """合同主表行（**语义形状**）—— 筛选口径（`ACC-JC-UI-001/001-02` / `001-14`）：

    - `project_key` = **仓库名**（与集采合同的「项目」字段**同一键空间** ⇒ **直接判等、不做模糊匹配**）；
    - `tags` 三态多值（空 ⇒ 不筛）；`arch` / `supplier` 支持**包含**匹配（供应商是自由文本，取子串）。
    ⚠️ 未给任何筛选 ⇒ **全量**（判据「复位后回到全量」）。
    """
    stmt = select(JcContract, Project.warehouse_name).join(
        Project, Project.id == JcContract.project_id, isouter=True
    )
    if tags:
        stmt = stmt.where(JcContract.tag.in_([str(t) for t in tags]))
    if str(arch or "").strip():
        stmt = stmt.where(JcContract.arch == str(arch).strip())
    if str(supplier or "").strip():
        stmt = stmt.where(JcContract.supplier.contains(str(supplier).strip()))
    if str(project_key or "").strip():
        stmt = stmt.where(Project.warehouse_name == str(project_key).strip())
    stmt = stmt.order_by(JcContract.contract_date.desc(), JcContract.id.desc())

    out: list[dict] = []
    for row, wh in s.execute(stmt).all():
        out.append({
            "id": row.id,
            "date": row.contract_date,
            "material": row.material_name,
            "supplier": row.supplier,
            "contract_amt": row.contract_amt,
            "trade_co": row.trade_co,
            "trade_contract_amt": row.trade_contract_amt,
            "method": row.method,
            "remark": row.remark,
            "tag": row.tag,
            "arch": row.arch,
            "arch_no": row.arch_no,
            "ret_date": row.ret_date,
            "project_key": str(wh or ""),          # ⭐ 筛选键（仓库名）
        })
    return out


def contract_of(s: Session, contract_id: int) -> JcContract | None:
    return s.get(JcContract, int(contract_id))


def invoices_of(s: Session, contract_id: int) -> list[dict]:
    """该合同的**全部**发票子表行（两张同款子表都在这一张表里，靠 `kind` 区分 · §6.4.2）。"""
    stmt = select(JcInvoice).where(JcInvoice.contract_id == int(contract_id)).order_by(JcInvoice.id)
    return [
        {"id": r.id, "kind": r.kind, "date": r.invoice_date, "amount": r.amount}
        for r in s.execute(stmt).scalars().all()
    ]


def payments_of(s: Session, contract_id: int) -> list[dict]:
    """该合同的付款子表行（手工 ＋ 付款域引用 · §6.4.3）。"""
    stmt = select(JcPayment).where(JcPayment.contract_id == int(contract_id)).order_by(JcPayment.id)
    return [
        {"id": r.id, "date": r.pay_date, "amount": r.amount, "source": r.source, "notice_id": r.notice_id}
        for r in s.execute(stmt).scalars().all()
    ]


def invoices_of_many(s: Session, contract_ids: list[int]) -> dict[int, list[dict]]:
    """批量取发票子表（列表页要一次算清所有合同的派生金额 ⇒ ⛔ 别在循环里逐条查库）。"""
    ids = [int(i) for i in contract_ids]
    if not ids:
        return {}
    stmt = select(JcInvoice).where(JcInvoice.contract_id.in_(ids)).order_by(JcInvoice.contract_id, JcInvoice.id)
    out: dict[int, list[dict]] = {i: [] for i in ids}
    for r in s.execute(stmt).scalars().all():
        out.setdefault(r.contract_id, []).append(
            {"id": r.id, "kind": r.kind, "date": r.invoice_date, "amount": r.amount}
        )
    return out


def payments_of_many(s: Session, contract_ids: list[int]) -> dict[int, list[dict]]:
    """批量取付款子表（同上：做一次，别 N 次）。"""
    ids = [int(i) for i in contract_ids]
    if not ids:
        return {}
    stmt = select(JcPayment).where(JcPayment.contract_id.in_(ids)).order_by(JcPayment.contract_id, JcPayment.id)
    out: dict[int, list[dict]] = {i: [] for i in ids}
    for r in s.execute(stmt).scalars().all():
        out.setdefault(r.contract_id, []).append(
            {"id": r.id, "date": r.pay_date, "amount": r.amount, "source": r.source, "notice_id": r.notice_id}
        )
    return out


def notice_ids_used(s: Session) -> set[int]:
    """**全库**已被引用过的通知书 id（§6.6.2「不分合同」的去重范围 · 判据 `ACC-JC-PAY-001/001-02`）。

    ⭐ 这就是 `domain.dedup_blocked` 的**生产入参来源** —— 域层判"重复没重复"，仓储层只负责给全集。
    """
    stmt = select(JcPayment.notice_id).where(JcPayment.notice_id.is_not(None))
    return {int(x) for x in s.execute(stmt).scalars().all() if x is not None}


def project_choices(s: Session) -> list[dict]:
    """「项目」筛选 / 新增合同的候选（键 = 仓库名 · 展示名另给）—— 同 `MOD-09` 的口径：**唯一出口**。"""
    stmt = select(Project).order_by(Project.ord, Project.id)
    return [
        {"key": str(p.warehouse_name or ""), "display": str(getattr(p, "display_name", "") or p.warehouse_name or "")}
        for p in s.execute(stmt).scalars().all()
    ]


__all__ = [
    "list_contracts", "contract_of", "invoices_of", "payments_of",
    "invoices_of_many", "payments_of_many", "notice_ids_used", "project_choices",
]
