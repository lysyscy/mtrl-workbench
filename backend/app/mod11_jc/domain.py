"""`MOD-11` 集采台账 · **域内核**（纯函数：不连库、不写路由）。

口径主人（**只引用、不复述取值**）：
- 《说明书》**§6.4.1** —— 合同主表 **19 字段**清单（其中 3 个 = 子表合计、2 个 = 系统自动算 ⇒ **不落库**）；
- **§6.4.2** —— 发票子表：两张**同款同规则**（供应商 / 贸易公司），字段 = **「发票日期 ＋ 金额」**；
  日期**必填**（发票要能对上所属期）· 金额**必须 > 0、不设上限**；
- **§6.4.3** —— 付款子表：0/1/N · 每条**标明来源**（手工 / 付款域引用）；
- **§6.4.4** —— **欠款 = 结算 − 付款** · **合同级实时、不拆月度**；
- **§6.5.3** —— **两态**（`纳入台账` / `不纳入`）· ⭐ **抓来即「纳入台账」**（`TAIL-97` 2026-09-25 取消
  「待确认」）· ⛔ **人工标记不被抓取覆盖**（"标了不纳入就不许改回来"这条铁律**保留**）；
- **§6.6.2** —— 付款引用：**全库去重** · **一对一** · ⚠️ **不做金额校验**（不一致**只提示、不拦截**）；
- **§2.7.4** —— 项目**候选键 = 仓库名**（比较 / 筛选一律用它）。

[用户2026-10-14] 集采付款方式独立列已取消，统一填写备注；付款域的实际付款方式不受影响。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.money import amount_text            # ⭐ `TAIL-63`：金额洗净的唯一出口
from app.mod11_jc.models import (
    KIND_SUPPLIER,
    KIND_TRADE,
    TAG_IN,
    TAG_OUT,
    TAGS,
)

ZERO = Decimal("0.00")

MSG_BAD_AMOUNT = "金额不合法：必须是大于 0 的数字（不设上限），已保留原值"
MSG_NEED_DATE = "日期必填：发票要能对上所属期（默认取系统当日，可改）"

#: 集采台账**表头**（19 列）—— ⭐ **列的唯一主人**（`TAIL-298`）：屏幕表头 / 屏幕行为表（隐藏·钉列）
#:   与 Excel 导出**一律从它派生**，⛔ 壳里不再另写一份列字面量、导出也不另写一份列清单。
#  ⚠️ 顺序即口径（`ACC-JC-UI-001/001-12` 钉着"三列紧贴操作列左侧"），别按"好看"重排。
#: ⭐ `key` = 列的**稳定身份**：壳的屏幕行为表按它定位（`web/shell/pages-b.js` 的
#:   `JC_HIDE_IDS` / `JC_PIN_IDS` —— 隐藏与钉列**各一条 id 清单**），⛔ 不按列号 ——
#:   加一列 / 调列序**不该**改行为，列号那套正是 `TAIL-298` 要治的静默错位。
#:   ⇒ 行为表里写错的 id 在这里找不到 ⇒ 判据当场红（`tests/test_ux_pages.py::001-61`）。
#: ⭐ `export_label`（可选）= **Excel 表头的字**（缺省 = `label`）：屏幕上带「（自动）」「（自由文本）」
#:   这类**屏内注解**，导出**不带**（Excel 里那是噪声）—— 见 `report_export/jc_export.py`。
JC_COLUMNS: tuple[dict[str, Any], ...] = (
    {"key": "project_seq", "label": "序号", "type": "text"},   # 项目内动态号（TAIL-290）＝行字典 / 导出的同名键
    {"key": "date", "label": "合同日期", "type": "date"},
    {"key": "material", "label": "材料名", "type": "text"},
    {"key": "contract_no", "label": "合同编号", "type": "text"},
    {"key": "supplier", "label": "供应商", "type": "text"},
    {"key": "contract_amt", "label": "合同金额", "type": "num"},
    {"key": "inv_sum", "label": "发票金额", "type": "num"},          # = 供应商发票子表合计（派生）
    {"key": "trade_co", "label": "贸易公司名", "type": "text"},
    {"key": "trade_contract_amt", "label": "贸易公司合同金额", "type": "num"},
    {"key": "trade_inv_sum", "label": "贸易公司发票金额", "type": "num"},  # = 贸易发票子表合计（派生）
    {"key": "settle", "label": "结算金额（自动）", "export_label": "结算金额", "type": "num"},    # 系统自动算
    {"key": "pay_sum", "label": "付款金额", "type": "num"},           # = 付款子表合计（派生）
    {"key": "debt", "label": "欠款金额（自动）", "export_label": "欠款金额", "type": "num"},      # 系统自动算
    {"key": "remark", "label": "备注", "type": "text"},
    {"key": "tag", "label": "三态", "type": "tag"},
    {"key": "arch", "label": "合同存档情况", "type": "tag"},
    {"key": "arch_no", "label": "存档号", "type": "text"},
    {"key": "ret_date", "label": "寄回日期", "type": "date"},
    {"key": "ops", "label": "操作", "type": "text"},
)

#: 子表表头（两张发票子表**共用** · §6.4.2「同款同规则」）—— 「发票日期 ＋ 金额」两列
#: ⚠️ `TAIL-298` **同批核对**：这两张子表的「序号」是弹窗里按**行序**现生成的行号（壳 `i+1`），
#:   行字典（`R.invoices_of`）里**没有**这个键、也**没有导出**（`JCINV_THEAD` 那列是 `#`）
#:   ⇒ 它**不是**「元数据 / 行字典 / 导出三者同名」那一类（主表「序号」才是，见 `JC_COLUMNS`）。
#:   ⇒ ⛔ 别拿 `idx` 去 `row.get(...)` 取值（会静默拿到空）。
INV_COLUMNS: tuple[dict[str, Any], ...] = (
    {"key": "idx", "label": "序号", "type": "text"},
    {"key": "date", "label": "发票日期", "type": "date"},
    {"key": "amount", "label": "金额", "type": "num"},
)

#: 付款子表表头（日期 ＋ 金额 ＋ **来源** · §6.4.3「每条标明来源」）
#: ⚠️ 「序号」同上（`TAIL-298` 同批核对）；`source` 是真键（`R.payments_of` 给 `manual` / `notice`）。
PAY_COLUMNS: tuple[dict[str, Any], ...] = (
    {"key": "idx", "label": "序号", "type": "text"},
    {"key": "date", "label": "付款日期", "type": "date"},
    {"key": "amount", "label": "金额", "type": "num"},
    {"key": "source", "label": "来源", "type": "text"},
)

#: 「操作」列（按钮 / 表单 HTML）**只在页面上成立** ⇒ `/api/*` 导出必须剔除
PAGE_ONLY_KEYS: tuple[str, ...] = ("ops",)

#: ⭐ **主表金额列一律只读汇总**（§6.4.1 末行 · 判据 `001-09`：「录入只走子表」）
#  ⇒ 它们**不是**录入项：本元组同时是"这些列不许出现在任何写端点入参里"的唯一清单。
DERIVED_MONEY_KEYS: tuple[str, ...] = ("inv_sum", "settle", "trade_inv_sum", "pay_sum", "debt")

#: 合计行要求和的金额列（其余列不求和）
SUM_KEYS: tuple[str, ...] = ("contract_amt", "inv_sum", "trade_contract_amt", "trade_inv_sum",
                             "settle", "pay_sum", "debt")


# ---------------------------------------------------------------- 金额 / 日期（纯函数）


def parse_amount(raw) -> Decimal:
    """子表金额（§6.4.2）：**必须 > 0**，**不设上限**（可超合同金额）⇒ 只走"是否为正"这一个出口。

    ⚠️ 与 `MOD-09` 手填项的口径**刻意不同**（那边允许 0 与负数）—— 别把两套搅在一起。
    """
    text = amount_text(raw)
    if not text:
        raise ValueError(MSG_BAD_AMOUNT)
    try:
        value = Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ArithmeticError, ValueError) as exc:
        raise ValueError(MSG_BAD_AMOUNT) from exc
    if value <= 0:
        raise ValueError(MSG_BAD_AMOUNT)
    return value


def _date_text(raw) -> str:
    return str(raw if raw is not None else "").strip()


def invoice_problem(date, amount) -> str | None:
    """发票子表校验出口（§6.4.2）：日期**必填** ＋ 金额 **> 0 不设上限** ⇒ `None` = 可落库。

    ⚠️ 判据 `001-05` 钉的是「**只填金额不填日期 ⇒ 不得落库**」—— 本函数非空时**调用方必须拒写**。
    """
    if not _date_text(date):
        return MSG_NEED_DATE
    try:
        parse_amount(amount)
    except ValueError as exc:
        return str(exc)
    return None


def payment_problem(date, amount) -> str | None:
    """付款子表校验出口（§6.4.3 / §6.4.2 **同款**）：与发票**同一套**规则（`001-05`：「发票与付款同款」）。

    ⚠️ 付款日期由**壳侧默认取系统当日**（`001-07`）—— 那是录入便利，不是"可以不填"。
    """
    return invoice_problem(date, amount)


# ---------------------------------------------------------------- 结算 / 欠款（唯一出口）


def _sum(rows: list[dict] | None, key: str = "amount") -> Decimal:
    total = ZERO
    for r in rows or ():
        total += Decimal(str(r.get(key) or 0))
    return total.quantize(Decimal("0.01"))


def supplier_invoice_sum(invoices: list[dict] | None) -> Decimal:
    """供应商发票子表合计（只看 `kind = supplier` 的行）。"""
    return _sum([r for r in (invoices or ()) if str(r.get("kind") or KIND_SUPPLIER) == KIND_SUPPLIER])


def trade_invoice_sum(invoices: list[dict] | None) -> Decimal:
    """贸易公司发票子表合计（只看 `kind = trade` 的行）。"""
    return _sum([r for r in (invoices or ()) if str(r.get("kind") or "") == KIND_TRADE])


def pay_sum(payments: list[dict] | None) -> Decimal:
    """付款子表合计（手工 ＋ 付款域引用**一起算** —— 都是付款事实）。"""
    return _sum(payments)


def settle_amount(*, trade_co, invoices: list[dict] | None) -> Decimal:
    """**结算金额**（§6.4.4 / 判据 `001-10`）：**有**贸易公司 → 贸易发票合计；**无** → 供应商发票合计。

    ⭐ **两条路互不串用**（判据原文）：有贸易公司时，供应商发票子表里有多少钱**都不影响**结算。
    """
    if str(trade_co or "").strip():
        return trade_invoice_sum(invoices)
    return supplier_invoice_sum(invoices)


def debt_amount(*, settle, pay) -> Decimal:
    """**欠款 = 结算 − 付款**（§6.4.4）· **合同级实时、不拆月度**（⇒ 签名里**没有年月**，这是刻意的）。"""
    return (Decimal(str(settle or 0)) - Decimal(str(pay or 0))).quantize(Decimal("0.01"))


def contract_amounts(*, trade_co, invoices: list[dict] | None, payments: list[dict] | None) -> dict:
    """主表那 5 个金额列的**派生值**（⛔ 一律现场算，不落库 —— §6.4.1 末行）。

    ⭐ 判据 `001-09`「主表金额列 = 只读汇总，**改子表即改欠款**」就是靠**每次现算**满足的：
      子表一变，这个函数的返回值立刻变 ⇒ 不存在"主表存了一份、忘了同步"。
    """
    inv = supplier_invoice_sum(invoices)
    tinv = trade_invoice_sum(invoices)
    pay = pay_sum(payments)
    settle = settle_amount(trade_co=trade_co, invoices=invoices)
    return {
        "inv_sum": inv,
        "trade_inv_sum": tinv,
        "pay_sum": pay,
        "settle": settle,
        "debt": debt_amount(settle=settle, pay=pay),
    }


# ---------------------------------------------------------------- 三态（§6.5.3）


def normalize_tag(raw) -> str:
    """**两态**取值归一：认不出的**一律回落到「纳入台账」**（`TAIL-97`：抓来即纳入 ⇒ 默认值就是它）。

    ⚠️ 改前是「回落**待确认**」＋ 理由"⛔ 不猜成纳入（不替用户拍板）" ——
       那条理由随用户 2026-09-25 的裁定**失效**：现在「纳入台账」**就是**系统默认值，
       认不出的值回落到它才是自洽的（回落方向与"抓来即纳入"一致）。
    """
    v = str(raw if raw is not None else "").strip()
    return v if v in TAGS else TAG_IN


def tag_after_fetch(current) -> str:
    """**抓取（含全量重抓）之后该行保留的两态**（§6.5.3 · `TAIL-97`）。

    ⭐ 规则只有一条：**已人工标记的「不纳入」持久保留**；其余（含新抓的行）一律「纳入台账」。
    ⚠️⛔ 这条**铁律在"取消待确认"之后必须保留**：人工标了「不纳入」⇒ 抓取**不许**改回来
       （依据 = 判据 `ACC-JC-FETCH-001/001-10` 的延伸；⛔ 别把它当成"顺手简化掉"的分支）。
    """
    v = str(current if current is not None else "").strip()
    if v == TAG_OUT:
        return v
    return TAG_IN


# ---------------------------------------------------------------- 付款引用（§6.6.2）


def link_hint(*, notice_amount, contract_debt) -> str | None:
    """关联时的**金额提示**（§6.6.2 / 判据 `001-04`）：**只提示、⛔ 不拦截**。

    ⚠️ 本函数**只返回文本**（或 `None` = 金额一致）—— 它**没有**"拒绝"这个返回值，
       因为口径就是"不一致也照样能关联"（事实优先）。把返回值当"能不能提交"用 = 读错了口径。
    """
    a = Decimal(str(notice_amount or 0))
    d = Decimal(str(contract_debt or 0))
    if a == d:
        return None
    return (f"⚠️ 该通知书金额 {a:,.2f} 与合同当前欠款 {d:,.2f} 不一致 —— 关联仍可进行（§6.6.2 不做金额校验），"
            f"请自行确认是否为同一笔业务")


def dedup_blocked(*, notice_id, existing_notice_ids) -> bool:
    """**全库去重**判定（§6.6.2 / 判据 `ACC-JC-PAY-001/001-02`）：该通知书**是否已被引用过**。

    ⚠️ 去重范围 = **全库、不分合同**（判据原文）⇒ 入参是"全库已引用过的通知书 id 集合"，
       **不是**"本合同的"。—— 落库侧还有一条唯一键兜底（`uq_jc_payment_notice`），两层都要在。
    """
    return notice_id is not None and int(notice_id) in {int(x) for x in (existing_notice_ids or ())}


def pick_candidates(*, contracts, project_key, supplier, current_id=None) -> list[dict]:
    """关联弹窗的**候选范围**（§6.6.2 / 判据 `001-05`）：本项目 ＋ 已匹配供应商下的合同。

    ⭐ 两条细节（判据原文）：
    ① 项目键 = **仓库名**，与集采合同的「项目」字段**同一键空间** ⇒ **直接判等、不做模糊匹配**；
    ② **当前已关联的那张无条件保留**（否则「改 / 解绑」时看起来像从没关联过）。
    ⚠️ `supplier` 为空（还没匹配到）⇒ 候选**只剩当前那张** ⇒ 调用方要按"候选为空给提示、不许提交"处理（`001-06`）。
    """
    key = str(project_key or "").strip()
    sup = str(supplier or "").strip()
    out: list[dict] = []
    for c in contracts or ():
        if current_id is not None and int(c.get("id") or 0) == int(current_id):
            out.append(c)                                    # ② 当前那张无条件保留
            continue
        if str(c.get("project_key") or "").strip() != key:
            continue
        if sup and str(c.get("supplier") or "").strip() != sup:
            continue
        out.append(c)
    return out


__all__ = [
    "ZERO", "MSG_BAD_AMOUNT", "MSG_NEED_DATE",
    "JC_COLUMNS", "INV_COLUMNS", "PAY_COLUMNS", "PAGE_ONLY_KEYS",
    "DERIVED_MONEY_KEYS", "SUM_KEYS",
    "parse_amount", "invoice_problem", "payment_problem",
    "supplier_invoice_sum", "trade_invoice_sum", "pay_sum",
    "settle_amount", "debt_amount", "contract_amounts",
    "normalize_tag", "tag_after_fetch",
    "link_hint", "dedup_blocked", "pick_candidates",
]


def project_sequences(rows: list[dict]) -> dict[int, int]:
    """全项目纳入合同的动态号；调用方筛选与返回行序不参与编号。"""
    counts: dict[str, int] = {}
    result: dict[int, int] = {}
    included = [r for r in rows if r["tag"] == TAG_IN]
    for row in sorted(included, key=lambda r: (not bool(r["date"]), r["date"] or "", r["id"])):
        key = row["project_key"]
        counts[key] = counts.get(key, 0) + 1
        result[row["id"]] = counts[key]
    return result
