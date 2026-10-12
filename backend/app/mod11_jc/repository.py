"""`MOD-11` 集采台账 · **仓储层**（只做取数 / 落库，不写判定）。

⚠️ **判定一律调 `domain` 出口**（结算 / 欠款 / 子表校验 / 两态）—— 本文件里⛔ 不出现第二个"结算口径"。
⚠️ **项目键 = 仓库名**（§2.7.4）：比较 / 筛选一律用它，**写库仍按档案 id** ⇒ 本层负责把 `project_id`
   经项目出口翻译成 `warehouse_name`，⛔ 不让上层各自 join 一遍。
⚠️ 派生金额（发票合计 / 付款合计 / 结算 / 欠款）**一律不落库**（§6.4.1 末行）⇒ 本层只回原始子表行。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import MustReportError   # `TAIL-96` 补：`add_ignored` 空名要抛它（拆件漏 import ⇒ 运行时 NameError）
from app.mod01_projects import service as PS
from app.mod11_jc import domain as D          # ⚠️ 只**调**它的出口（三态归一 / 判定），⛔ 不在本层复写逻辑
from app.mod11_jc.models import (
    KIND_PARTY_TRADE,
    KIND_PARTY_UNKNOWN,
    PARTY_KIND_NAMES,
    SRC_MANUAL,
    SRC_NOTICE,
    TAG_IN,
    JcContract,
    JcInvoice,
    JcPartyKind,
    JcPayment,
)


def _project_key(s: Session, project_id: int) -> tuple[str, str]:
    """`project_id` → `(仓库名, 展示名)`（§2.7.4：**键 = 仓库名**，展示名只用于显示）。"""
    p = next((p for p in PS.all_projects(s) if p.id == int(project_id)), None) if project_id else None
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
    projects = PS.warehouse_index(s)
    wh_by_id = {int(p.id): str(p.warehouse_name) for p in projects.values()}
    stmt = select(JcContract)
    if tags:
        stmt = stmt.where(JcContract.tag.in_([str(t) for t in tags]))
    if str(arch or "").strip():
        stmt = stmt.where(JcContract.arch == str(arch).strip())
    if str(supplier or "").strip():
        stmt = stmt.where(JcContract.supplier.contains(str(supplier).strip()))
    if str(project_key or "").strip():
        project = projects.get(str(project_key).strip())
        stmt = stmt.where(JcContract.project_id == project.id) if project else stmt.where(False)
    stmt = stmt.order_by(JcContract.contract_date.desc(), JcContract.id.desc())

    out: list[dict] = []
    for row in s.execute(stmt).scalars().all():
        wh = wh_by_id.get(row.project_id, "")
        out.append({
            "id": row.id,
            "contract_no": row.contract_no,
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
    return payments_of_many(s, [contract_id]).get(int(contract_id), [])


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
    from app.mod03_notice import service as notices
    from app.mod05_flow import service as flows

    rows = list(s.execute(select(JcPayment).where(
        JcPayment.contract_id.in_(ids)
    ).order_by(JcPayment.contract_id, JcPayment.id)).scalars().all())
    notice_ids = sorted({int(r.notice_id) for r in rows if r.notice_id is not None})
    # 两个主人各批量读取一次，调用次数不随合同/通知书数量增长。
    stats = notices.stat_paid_of_many(s, notice_ids)
    dates = flows.latest_effective_dates(s, notice_ids)
    out: dict[int, list[dict]] = {i: [] for i in ids}
    for r in rows:
        stat_paid = stats.get(r.notice_id)
        actual_date = dates.get(r.notice_id)
        linked = r.source == SRC_NOTICE
        out.setdefault(r.contract_id, []).append({
            "id": r.id, "date": (actual_date or "") if linked else r.pay_date,
            "amount": Decimal(str(stat_paid or 0)) if linked else r.amount,
            "source": r.source, "notice_id": r.notice_id,
        })
    return out


def notice_ids_used(s: Session) -> set[int]:
    """**全库**已被引用过的通知书 id（§6.6.2「不分合同」的去重范围 · 判据 `ACC-JC-PAY-001/001-02`）。

    ⭐ 这就是 `domain.dedup_blocked` 的**生产入参来源** —— 域层判"重复没重复"，仓储层只负责给全集。
    """
    stmt = select(JcPayment.notice_id).where(JcPayment.notice_id.is_not(None))
    return {int(x) for x in s.execute(stmt).scalars().all() if x is not None}


def project_id_by_key(s: Session, project_key: str) -> int | None:
    """**仓库名 → 档案 id**（写动作要 id，而前后端之间「项目」一律以**仓库名**为键 · §2.7.4）。

    ⚠️ 这是"键 → 内部 id"的**唯一**翻译口；返回 `None` = 查不到（调用方必须**显式报错**，⛔ 不静默）。
    """
    key = str(project_key or "").strip()
    if not key:
        return None
    project = PS.warehouse_index(s).get(key)
    return project.id if project else None


def project_choices(s: Session) -> list[dict]:
    """「项目」筛选 / 新增合同的候选（键 = 仓库名 · 展示名另给）—— 同 `MOD-09` 的口径：**唯一出口**。"""
    # 保留本视图原有ord/id顺序和全部档案（含无仓库行）。
    rows = sorted(PS.all_projects(s), key=lambda p: (p.ord, p.id))
    return [
        {"key": str(p.warehouse_name or ""), "display": str(getattr(p, "display_name", "") or p.warehouse_name or "")}
        for p in rows
    ]


# ============================================================ 写动作（`M5-4`）
# ⚠️ 本层只落库、**不写判定**：三态归一走 `domain.normalize_tag`、子表校验走
#   `domain.invoice_problem` / `payment_problem`（调用方 = `service`）⇒ ⛔ 别在这里再判一遍。
# ⚠️ 白名单之外的列**一律不改**（`EDITABLE_COLS`）—— 防"顺手改了金额 / 三态"绕过各自出口。

#: 可手改列的白名单（判据 `001-12`「三列 ＋ 备注可手改并落值」）。
#: ⭐⭐ **2026-09-26 用户裁定收窄**（他的原话："实际集采台账上能被手改的很少"）：只留**界面上
#:   真给了入口的列** = "Excel 的地盘"这 6 列（材料名 / 付款方式 / 备注 / 存档三列，与台账页那几格一一对应）。
#:   ⛔ **i8 的事实列**（合同日期 / 供应商 / 甲方单位）不在其中：界面上本来**没有入口**，而放行它
#:      = 任何一条接口调用都能改 i8 的事实。TAIL-313已审核日期通过专项事务保护，界面仍无手改入口。
#:   ⛔ **合同金额 / 贸易公司两列**也不在其中：它们的写入口归**抓取**（按甲方类型分叉）与
#:      **导入**（`fill_contract_amt_if_blank` · 只对贸易公司合同 · **空才填**）—— ⛔ 不是人手改。
#:      ⚠️ 2026-09-19 曾把它放进来（"合同金额可能不对"）——现按 2026-09-26 的口径移出：
#:        界面上没有那一格可填，留着它只会让人误以为"能改"。
#: ⚠️ **三态不在其中** —— 它有专门出口 `set_tag` / `set_tags`（标记与编辑分开，免得互相绕过）。
#: ⚠️ 与 `import_service.EXCEL_COLS` 是**同一份口径**（`tests/test_acc_jc_import.py` 钉着包含关系）
#:    ⇒ 改一边必须改另一边，⛔ 别只改这里。
EDITABLE_COLS: tuple[str, ...] = (
    "material_name", "method", "remark", "arch", "arch_no", "ret_date",
)


def insert_contract(s: Session, *, project_id: int, contract_date: str = "",
                    material_name: str = "", supplier: str = "", contract_amt=0,
                    trade_co=None, trade_contract_amt=None, tag: str = TAG_IN,
                    method: str = "", remark: str = "") -> JcContract:
    """手工新增合同 ⇒ **真的建档**（判据 `ACC-JC-UI-001/001-13`）。

    ⚠️ 三态由**调用方**给（`service.act_add_contract` 按"手工新增 ⇒ 纳入台账"填，见判据 `001-07`）
    —— 本层⛔ 不替业务拍默认值。
    """
    row = JcContract(
        project_id=int(project_id),
        contract_date=str(contract_date or "")[:10],
        material_name=str(material_name or "")[:128],
        supplier=str(supplier or "")[:128],
        contract_amt=Decimal(str(contract_amt or 0)),
        trade_co=(str(trade_co) if trade_co not in (None, "") else None),
        trade_contract_amt=(Decimal(str(trade_contract_amt))
                            if trade_contract_amt not in (None, "") else None),
        tag=str(tag or TAG_IN),
        method=str(method or "")[:64],
        remark=str(remark or "")[:255],
    )
    s.add(row)
    s.flush()
    return row


def set_tag(s: Session, contract_id: int, tag: str) -> int:
    """单条三态标记 ⇒ 受影响行数（`0` = 没这条合同）。判据 `ACC-JC-FETCH-001/001-03`。"""
    row = s.get(JcContract, int(contract_id))
    if row is None:
        return 0
    row.tag = str(tag)
    s.flush()
    return 1


def set_tags(s: Session, contract_ids, tag: str) -> list[int]:
    """**批量**三态标记 ⇒ **实际改到的 id 列表**（判据 `001-05`）。

    ⭐ 那条判据的三件事都由本函数保证：
    ① **只作用于给定 id**（`WHERE id IN (...)`）；
    ② **不新建 / 不删除**任何行（只改 `tag`）⇒ **行数不变**；
    ③ 返回 `affected` ⇒ **壳拿它清空勾选**（⛔ 不是"清空所有勾选"，是清掉刚标过的那些）。
    """
    ids = [int(i) for i in (contract_ids or ())]
    if not ids:
        return []
    rows = list(s.execute(select(JcContract).where(JcContract.id.in_(ids))).scalars())
    for r in rows:
        r.tag = str(tag)
    s.flush()
    return [int(r.id) for r in rows]


def update_contract(s: Session, contract_id: int, **cols) -> int:
    """按**白名单**改主表列（判据 `001-12`「三列 ＋ 备注可手改并落值」）⇒ 受影响行数。

    ⛔ 非白名单键一律忽略（含三态 —— 它走 `set_tag`）；⚠️ **传了空串 = 清空**（与"没传"不同：
    没传的键**不动**）⇒ 调用方只传要改的列。
    """
    row = s.get(JcContract, int(contract_id))
    if row is None:
        return 0
    for key, val in (cols or {}).items():
        if key not in EDITABLE_COLS:
            continue
        if key in ("contract_amt", "trade_contract_amt"):
            if val in (None, ""):
                val = None if key == "trade_contract_amt" else Decimal("0")
            else:
                val = Decimal(str(val))
        setattr(row, key, val)
    s.flush()
    return 1


def contract_amt_is_fillable(row: JcContract | None, value) -> bool:
    """「**合同金额空才填**」的**唯一判据**（`fill_contract_amt_if_blank` 与**导入预览**共用一份）。

    ⚠️ 为什么抽出来（2026-09-26 · `TAIL-106`）：预览要**只读**地说"这一行会把供应商价填进空的那格"，
       而判据一旦在预览里**另写一份**，就会出现"预览说会填、落库没填"（或反过来）——
       那正是本仓最忌的「同一口径两个主人」。⇒ 判据只此一处，读写两侧都调它。
    """
    if row is None or float(row.contract_amt or 0) != 0:
        return False
    return Decimal(str(value or 0)) > 0


def fill_contract_amt_if_blank(s: Session, contract_id: int, value) -> bool:
    """**只在「合同金额」为空时**写它 —— **Excel 供应商线专用**（2026-09-26 用户裁定 · 方案②）。

    ⭐ 为什么单开一个出口、⛔ 不走 `update_contract`：「合同金额」对**正常合同**是 i8 的事实
      （人工改不了、Excel 也不许覆盖）；只有**贸易公司合同**它才是**空的**、等 Excel 的供应商线补
      （i8 里根本没有这个数 —— 见 `upsert_fetched_contracts` 的"按甲方类型分叉"那段）
      ⇒ 两条口径不同 ⇒ 出口分开；`EDITABLE_COLS` 里**刻意不放它**（放了 = 人能改 i8 的事实）。
    ⚠️ **空才填**：已有非 0 值（上一次导入填的）一个字不改 —— 与 §9.3「人工改过的不被覆盖」同款。
    ⚠️ 传空 / 0 **不写**（免得把"还没补"写成 0 —— "0"与"空"在台账上是两件事）。
    返回 `True` = 真写了。⚠️ 判据本体在 `contract_amt_is_fillable`（预览也调它，⛔ 别在这里再写一遍）。
    """
    row = s.get(JcContract, int(contract_id))
    if not contract_amt_is_fillable(row, value):
        return False
    row.contract_amt = Decimal(str(value or 0))
    s.flush()
    return True


def insert_invoice(s: Session, *, contract_id: int, kind: str, invoice_date: str, amount) -> JcInvoice:
    """发票子表增行（供应商 / 贸易公司**同款**）—— 校验在 `domain.invoice_problem`（调用方先判）。"""
    row = JcInvoice(contract_id=int(contract_id), kind=str(kind),
                    invoice_date=str(invoice_date or "")[:10], amount=Decimal(str(amount or 0)))
    s.add(row)
    s.flush()
    return row


def delete_invoice(s: Session, invoice_id: int) -> int:
    """发票子表删行 ⇒ 受影响行数（`0` = 没有这条）。"""
    row = s.get(JcInvoice, int(invoice_id))
    if row is None:
        return 0
    s.delete(row)
    s.flush()
    return 1


def insert_payment(s: Session, *, contract_id: int, pay_date: str, amount,
                   source: str = SRC_MANUAL, notice_id=None) -> JcPayment:
    """付款子表增行（手工录入 / 引用付款域）。

    ⚠️ `notice_id` 带**全库唯一键**（`uq_jc_payment_notice`）⇒ 真重复了数据库会直接拒；
    域层 `dedup_blocked` 只是**提前给一句好话**（⛔ 不是唯一防线）。
    """
    row = JcPayment(contract_id=int(contract_id), pay_date=str(pay_date or "")[:10],
                    amount=Decimal(str(amount or 0)), source=str(source),
                    notice_id=(int(notice_id) if notice_id not in (None, "") else None))
    s.add(row)
    s.flush()
    return row


def delete_payment(s: Session, payment_id: int) -> int:
    """付款子表删行 ⇒ 受影响行数。"""
    row = s.get(JcPayment, int(payment_id))
    if row is None:
        return 0
    s.delete(row)
    s.flush()
    return 1


def count_contracts(s: Session) -> int:
    """全表合同行数 —— 判据 `001-05`「**不改行数**」要**独立复算**时用它（⛔ 不靠接口自证）。"""
    return int(s.execute(select(func.count()).select_from(JcContract)).scalar_one())


# ============================================================ 抓取落库（`M5-6`）

#: 「**抓取会刷新**」的列 —— i8 的事实；已审核锁定的合同日期除外（TAIL-313）。
#: ⛔ 人工字段（三态 / 存档三列 / 备注 / 付款方式）**不在其中**：那是人的地盘，重抓不许动
#:   （判据 `ACC-JC-FETCH-001/001-09`「再次导入**不覆盖旁路字段**」）。
#: ⭐ `bill_name`（i8 单据名原文）**在列里**：它是 i8 的原文、不是人的地盘 ⇒ 重抓要刷新它。
#:   ⚠️ 2026-09-19 补 —— 原先没带上它 ⇒ 落库时**静默丢掉原文**（材料名/供应商从此无法回溯）。
#: ⭐ 2026-09-20（`M5-6b`）补 `party_name`（甲方单位）—— 它是"金额落哪一列"的判据（见下）。
FETCH_COLS: tuple[str, ...] = ("contract_date", "supplier", "bill_name", "party_name")

#: ⭐⭐ 「**空才填**」的列（`M5-6b` · 用户 2026-09-20 口径）—— 人工可改，**已有值就绝不覆盖**：
#:   - `material_name`：i8 的 `ItemName` **有错**（实测确有 `g'c` / `hong's模板` 这种），用户会**逐一手改**
#:     ⇒ 重抓把它覆盖掉 = 抹掉人工劳动（这就是用户那句"**已经不为空就不要被覆盖**"）。
FETCH_ONLY_WHEN_BLANK: tuple[str, ...] = ("material_name",)

#: ⭐⭐ 「**按甲方类型分叉**」的列（`M5-6b`）—— 它们的刷法**取决于这张合同的甲方是不是贸易公司**，
#:   判据在 `upsert_fetched_contracts` 里（⛔ 不能像 `FETCH_COLS` 那样无脑刷）。
#:   | 列 | 正常甲方 | 贸易公司甲方 |
#:   |---|---|---|
#:   | `contract_amt`（**锚点** · 供应商价） | i8 刷新 | ⛔ **绝不自动动**（人工从 Excel 供应商线补） |
#:   | `trade_contract_amt`（贸易公司的价） | 空 | **首次写** i8 的值（那正是贸易公司价），之后不动 |
#:   | `trade_co`（贸易公司名） | 空 | **首次写**（= 甲方单位名） |
FETCH_BY_PARTY_COLS: tuple[str, ...] = ("contract_amt", "trade_contract_amt", "trade_co")


def payment_of_notice(s: Session, notice_id: int) -> JcPayment | None:
    """按**通知书 id** 取那条**关联记录**（`source=notice` 的付款子表行）—— 「一对一」与「解绑」的定位口。

    ⭐ 关联关系**不另建表**：它就在这张付款子表里 ⇒ 这是"两个方向写同一份记录"的机器化落点。
    ⚠️ 全库唯一键 `uq_jc_payment_notice` 保证**最多一条** ⇒ `first()` 不是"随便挑一条"。
    """
    nid = int(notice_id) if notice_id not in (None, "") else None
    if nid is None:
        return None
    return s.execute(select(JcPayment).where(JcPayment.notice_id == nid)).scalars().first()


def existing_contract_nos(s: Session, nos: list[str]) -> set[str]:
    """给定一批合同编号 ⇒ **库里已存在的**那些（`set`）—— `M5-6` 增量补材料名用。

    ⚠️ **一次查完**（⛔ 不逐条 `one_by_no` = N+1）：抓取时动辄几百条，逐条查会把"省下来的时间"还回去。
    ⚠️ 空串 / 空白编号**不参与**（它们本来就不落库，见 `upsert_fetched_contracts`）。
    """
    wanted = [str(n or "").strip() for n in (nos or ())]
    wanted = [n for n in wanted if n]
    if not wanted:
        return set()
    stmt = select(JcContract.contract_no).where(JcContract.contract_no.in_(wanted))
    return {str(x) for x in s.execute(stmt).scalars() if x}


def one_by_no(s: Session, contract_no: str, *, for_update: bool = False) -> JcContract | None:
    """按**合同编号**取一行（`M5-6` 的**幂等键**）。空编号 ⇒ `None`（不参与幂等）。"""
    no = str(contract_no or "").strip()
    if not no:
        return None
    stmt = select(JcContract).where(JcContract.contract_no == no)
    if for_update:
        # 与日期修正串行，并刷新当前 Session 已缓存的旧日期/保护状态。
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return s.execute(stmt).scalars().first()


def upsert_fetched_contracts(s: Session, *, project_id: int, rows: list[dict]) -> dict:
    """抓取结果 → **增量落库**（`M5-6`）⇒ `{"inserted", "refreshed", "skipped"}`。

    ⭐ 幂等键 = **`contract_no`**（i8 的 `BillNo`）：

    - 没编号 ⇒ **跳过并计数**（⛔ 静默丢弃 —— 与 `API-04` 取数层同一口径）；
    - **不存在** ⇒ 新增，两态 = 「**纳入台账**」（`TAIL-97`：抓来即纳入，与手工新增**同一个默认值**）；
    - **已存在** ⇒ 只刷 `FETCH_COLS` ＋ 按 `domain.tag_after_fetch` 归一
      ⇒ 已审核锁定的日期保留，其余日期含空值仍以 i8 为准；其他字段正常同步。
      ⇒ ⛔ **不碰**存档三列 / 备注 / 付款方式 / 贸易公司（人的地盘），
        ⛔ 也**不许**把人工标的「不纳入」改回来（判据 `001-10` 的铁律）。
    """
    inserted = refreshed = skipped = 0
    for row in rows or ():
        no = str(row.get("contract_no") or "").strip()
        if not no:
            skipped += 1
            continue
        cur = one_by_no(s, no, for_update=True)
        _amt = Decimal(str(row.get("contract_amt") or 0))
        _party = str(row.get("party_kind") or KIND_PARTY_UNKNOWN)
        _is_trade = _party == KIND_PARTY_TRADE
        _party_name = str(row.get("party_name") or "")[:128]
        if cur is None:
            s.add(JcContract(
                contract_no=no,
                project_id=int(project_id),
                contract_date=str(row.get("sign_date") or "")[:10],
                material_name=str(row.get("material_name") or "")[:128],
                supplier=str(row.get("supplier_name") or "")[:128],
                party_name=_party_name,                # ⭐ i8 的甲方单位（判据列）
                # ⭐⭐ **金额落位**（`M5-6b`）：贸易公司合同 ⇒ i8 这个价是**贸易公司的价**
                #    ⇒ 落 `trade_contract_amt`，而 `contract_amt`（**锚点** · 真供应商价）
                #    **留 0 等人从 Excel 供应商线补**（i8 里根本没有那个数）。
                contract_amt=Decimal("0") if _is_trade else _amt,
                trade_co=(_party_name or None) if _is_trade else None,
                trade_contract_amt=(_amt if _is_trade else None),
                bill_name=str(row.get("bill_name") or "")[:255],   # ⭐ i8 原文（可回溯）
                tag=TAG_IN,                            # ⭐ `TAIL-97`：新抓的默认「纳入台账」
                remark=str(row.get("remark") or "")[:255],
            ))
            inserted += 1
        else:
            # ① 已审核锁定的日期保留；其他事实列与未锁定日期沿用原刷新策略（含空值）。
            for key, val in (("contract_date", str(row.get("sign_date") or "")[:10]),
                             ("supplier", str(row.get("supplier_name") or "")[:128]),
                             ("bill_name", str(row.get("bill_name") or "")[:255]),
                             ("party_name", _party_name)):
                if key in FETCH_COLS:
                    if key == "contract_date" and cur.contract_date_locked:
                        continue
                    setattr(cur, key, val)
            # ② **空才填**的列：有人工值就留住（用户手改过 i8 的错材料名）
            _mat = str(row.get("material_name") or "")[:128]
            if _mat and not str(cur.material_name or "").strip():
                cur.material_name = _mat
            # ③ ⭐⭐ **按甲方类型分叉**（这一支写错 = 金额落错列**且不报错**）：
            if _is_trade:
                # 贸易公司合同：i8 这个价 ⇒ `trade_contract_amt`（**首次**写；之后不动，那是人的地盘）；
                # ⛔⛔ **绝不碰 `contract_amt`** —— 那是用户从 Excel 供应商线补的**真供应商价**，
                #      被覆盖 = 把人工劳动抹掉，而且**下次抓取才发现**（典型静默出错）。
                if not str(cur.trade_co or "").strip():
                    cur.trade_co = _party_name or cur.trade_co
                if cur.trade_contract_amt is None:
                    cur.trade_contract_amt = _amt
            else:
                # 正常甲方 **以及 `unknown`**（未指定）⇒ 金额落 `contract_amt`。
                # ⚠️ 为什么 `unknown` 也按"正常"走：这个选择是**可逆**的（金额就在正常合同的落点，
                #    用户指定成贸易公司后一眼能看见、也好还原）；反之若按贸易公司落
                #    ⇒ 会把供应商价塞进 `trade_contract_amt`，更难发现也更难还原。
                #    ⇒ 但 `unknown` **必须在回执/页面里报出来**（见 `fetch_service` 与分类页）。
                cur.contract_amt = _amt
            # ⭐ 判据 `001-10`「抓取**不覆盖已人工标记的行**」= 这里只做"归一"：
            #    人工标的「不纳入」⇒ 原样保留；其余（含新抓的）一律「纳入台账」。
            cur.tag = D.tag_after_fetch(cur.tag)
            refreshed += 1
    s.flush()
    return {"inserted": inserted, "refreshed": refreshed, "skipped": skipped}


# ============================================================ 甲方单位分类（`M5-6b`）

def list_party_kinds(s: Session) -> list[dict]:
    """全部甲方分类（未指定排前面 —— 那批是**要人去指定**的）—— 页面用。"""
    rows = s.execute(select(JcPartyKind)).scalars().all()
    out = [{"name": str(r.name), "kind": str(r.kind),
            "kind_name": PARTY_KIND_NAMES.get(str(r.kind), str(r.kind))} for r in rows]
    out.sort(key=lambda d: (d["kind"] != KIND_PARTY_UNKNOWN, d["name"]))
    return out


def party_kind_map(s: Session) -> dict[str, str]:
    """`甲方全名 -> 类型` —— ⚠️ **一次查完**（⛔ 不逐条查 = N+1；抓取时几百条都要问）。"""
    return {str(r.name): str(r.kind) for r in s.execute(select(JcPartyKind)).scalars()}


def ensure_party_kinds(s: Session, names: list[str]) -> list[str]:
    """把**没见过的**甲方登记成 `unknown` ⇒ 返回**新登记的**名字（供回执报出，⛔ 禁静默）。

    ⭐ 这是"**未知甲方自动露头**"的机器化落点：抓取遇到新甲方 ⇒ 先落一行 `unknown`
      ⇒ 分类页列出来**等人指定**；⛔ 绝不静默当成"正常"（那会把贸易公司的价落错列）。
    """
    known = {str(x) for x in s.execute(select(JcPartyKind.name)).scalars()}
    added: list[str] = []
    for raw in names or ():
        nm = str(raw or "").strip()
        if not nm or nm in known:
            continue
        s.add(JcPartyKind(name=nm[:128], kind=KIND_PARTY_UNKNOWN))
        known.add(nm)
        added.append(nm)
    if added:
        s.flush()
    return added


def set_party_kind(s: Session, name: str, kind: str) -> bool:
    """指定某甲方的类型（不存在就建）⇒ 是否落库。⛔ 类型合法性由调用方（`service`）先判。"""
    nm = str(name or "").strip()
    if not nm:
        return False
    row = s.get(JcPartyKind, nm[:128])
    if row is None:
        s.add(JcPartyKind(name=nm[:128], kind=kind))
    else:
        row.kind = kind
    s.flush()
    return True


__all__ = [
    "list_contracts", "contract_of", "invoices_of", "payments_of",
    "invoices_of_many", "payments_of_many", "notice_ids_used", "project_choices",
    "project_id_by_key",
    "EDITABLE_COLS", "insert_contract", "set_tag", "set_tags", "update_contract",
    "contract_amt_is_fillable", "fill_contract_amt_if_blank",
    "insert_invoice", "delete_invoice", "insert_payment", "delete_payment", "count_contracts",
    "FETCH_COLS", "FETCH_ONLY_WHEN_BLANK", "FETCH_BY_PARTY_COLS",
    "one_by_no", "existing_contract_nos", "upsert_fetched_contracts", "payment_of_notice",
    "list_party_kinds", "party_kind_map", "ensure_party_kinds", "set_party_kind",
]


# ==================================================== TAIL-93 · 抓取记录的标记 ＋ 未走完读回


#: 集采抓取运行记录的标记（读侧靠它认「最近一次集采抓取」）—— 口径同 `mod03_notice.repository.FETCH_MARK`
JC_FETCH_MARK = "jc_fetch"

#: 找"最近一次集采抓取"时**最多回看**多少条运行记录（技术台账，量很小；够用即可）
LOOKBACK = 50


def fetch_detail(**extra) -> dict:
    """集采抓取**每条运行记录**的 `detail`（**写侧唯一出口**）：一律带标记 ＋ 本次的附加字段。

    ⚠️ **三种结局都必须写**（i8 取数/同步失败 · 抓取成功但有未走完 · 全走完）—— 漏掉任何一条，
       "最近一次"就指不住，读侧会掉回**更早**的记录 ⇒ 那正是付款侧 `TAIL-41` 踩过的坑：
       **抓取成功之后仍摆着上一次的未命中清单**，用户对着已解决的清单白干。
    """
    return {JC_FETCH_MARK: True, **extra}


def latest_unsettled(session: Session) -> list[dict]:
    """**最近一次集采抓取**带的「归属未走完」清单（`TAIL-93` 弹窗的数据源）。

    ⚠️⚠️ **只认最近一次**（与付款侧 `mod03_notice.repository.latest_unresolved` **同一条口径**）：
       只认「最近一条带 `JC_FETCH_MARK` 标记的记录」—— 它没带清单 ⇒ **返回空**，⛔ **不回溯更早的记录**。
    ⚠️ 清单里存的是**当时的判定** ⇒ 调用方必须按**当前档案现算**（`mod03_notice.domain.still_unsettled`）。
    ⛔ 这里**不暂存任何合同数据**（口径同付款侧：补完词**再抓一次**，库里不留半成品）。
    """
    from app.mod02_i8 import service as records
    recs = records.recent_records(session, run_type="fetch", limit=LOOKBACK)
    # ⚠️ 离线桩不处理 `order_by` ⇒ 再显式按 id 倒序一次（真库本来有序 ⇒ 语义不变）
    for r in sorted(recs, key=lambda x: getattr(x, "id", 0) or 0, reverse=True):
        detail = getattr(r, "detail", None) or {}
        if not isinstance(detail, dict) or not detail.get(JC_FETCH_MARK):
            continue                       # 不是集采抓取的记录（材料侧 / 付款侧）⇒ 跳过
        return list(detail.get("jc_unsettled") or [])
    return []


__all__ = ["JC_FETCH_MARK", "LOOKBACK", "fetch_detail", "latest_unsettled"]


# ─────────────── `TAIL-96` 集采剔除名单（不要的项目 · 抓取时先剔除）───────────────
def ignored_names(s: Session) -> set:
    """**在用的**剔除名单全名（归一化后）—— 抓取过滤的唯一入口。

    ⚠️ 归一化必须与 `resolve_ownership` **同一个函数**，否则"名单写了却不生效"这类静默错必现。
    """
    from app.mod01_projects.domain import norm_full_name
    from app.mod11_jc.models import JcIgnoreProject
    out = set()
    for row in s.execute(select(JcIgnoreProject).where(JcIgnoreProject.active.is_(True))).scalars():
        k = norm_full_name(str(row.name_full or ""))
        if k:
            out.add(k)
    return out


def list_ignored(s: Session) -> list:
    """名单（含停用）—— 给人看的清单。"""
    from app.mod11_jc.models import JcIgnoreProject
    rows = s.execute(select(JcIgnoreProject).order_by(JcIgnoreProject.id.desc())).scalars()
    return [{"id": int(x.id), "name_full": str(x.name_full or ""), "reason": str(x.reason or ""),
             "operator": str(x.operator or ""), "active": bool(x.active),
             "created_at": x.created_at.strftime("%Y-%m-%d %H:%M") if x.created_at else ""} for x in rows]


def add_ignored(s: Session, *, name_full: str, reason: str = "", operator: str = "") -> dict:
    """加一条（⭐ **同名幂等**：已有同名的在用行 ⇒ 直接返回它，⛔ 不重复插）。"""
    from app.mod01_projects.domain import norm_full_name
    from app.mod11_jc.models import JcIgnoreProject
    name = str(name_full or "").strip()
    if not name:
        raise MustReportError("项目全名不能为空")
    key = norm_full_name(name)
    for row in s.execute(select(JcIgnoreProject)).scalars():
        if norm_full_name(str(row.name_full or "")) == key:
            if not row.active:
                row.active = True
                s.flush()
                return {"id": int(row.id), "reused": True, "reactivated": True}
            return {"id": int(row.id), "reused": True, "reactivated": False}
    obj = JcIgnoreProject(name_full=name, reason=str(reason or ""), operator=str(operator or ""), active=True)
    s.add(obj)
    s.flush()
    return {"id": int(obj.id), "reused": False, "reactivated": False}


def set_ignored_active(s: Session, *, ignore_id: int, active: bool) -> int:
    """停用/启用（⛔ 不物理删）。"""
    from app.mod11_jc.models import JcIgnoreProject
    row = s.get(JcIgnoreProject, int(ignore_id))
    if row is None:
        return 0
    row.active = bool(active)
    s.flush()
    return 1


def links_by_notice(session, notice_ids: list[int] | None = None) -> dict[int, list[int]]:
    """一次读取通知书到合同关联；None 全量，空集合不查询。"""
    if notice_ids is not None and not notice_ids:
        return {}
    grouped: dict[int, list[int]] = {}
    stmt = select(JcPayment.notice_id, JcPayment.contract_id).where(JcPayment.notice_id.is_not(None))
    if notice_ids is not None:
        stmt = stmt.where(JcPayment.notice_id.in_(notice_ids))
    for nid, cid in session.execute(stmt).all():
        if nid is not None:
            grouped.setdefault(int(nid), []).append(int(cid))
    return grouped
