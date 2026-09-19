"""`MOD-11` 集采台账 · **三张落库表**（合同主表 ＋ 发票子表 ＋ 付款子表）。

依据：《说明书》**§6.4.1**（合同主表 **19 字段** —— 用户确认「无遗漏、无需删除」）·
**§6.4.2**（发票子表：两张同款「发票日期 ＋ 金额」· 一合同 1..N 张）· **§6.4.3**（付款子表：0/1/N ·
每条标明**来源**、引用付款域时记通知书 id 用于**去重**）· **§6.4.4**（欠款 = 结算 − 付款 ·
**合同级实时、不拆月度**）· **§6.5.3**（三态标记）· **§6.6.2**（付款引用：全库去重 · 一对一）。

⭐ **§6.4.1 的 19 个字段里只有 14 个落库** —— 其余按口径**一律现场算**（落库就是第二份真相）：

| 不落库 | 为什么不落 |
|---|---|
| 发票金额 · 贸易公司发票金额 · 付款金额 | = **各自子表的合计**（§6.4.1 末行：「派生显示、不单独存储」，录入一律走子表） |
| 结算金额 · 欠款金额 | **系统自动算**（§6.4.1 / §6.4.4） |

⚠️ 派生与自动算的**唯一出口 = `domain.py`**（⛔ 别在仓储层再写一份 —— 两套数必打架）。

⚠️ **两张发票子表合成一张表**（`kind = supplier | trade`）：§6.4.2 明确「两张子表**同款同规则**」
   ⇒ 一张表 ＋ `kind` 列**天然保证两侧同一套逻辑**；⛔ 别拆成两张表（那样同一套规则要写、要判两遍）。

⚠️ **付款子表的 `notice_id` 带全库唯一键**：§6.6.2「同一笔付款通知书**只能被引用一次**（**不分合同、全库去重**）」
   ⇒ 那条口径的**机器化落点就是 `uq_jc_payment_notice`**；⚠️ SQLite / PG 都允许多个 `NULL`
   （手工录入的付款没有通知书 id ⇒ 不参与去重）。

⚠️ **`method`（付款方式）是自由文本**（§6.4.1 注：例「60±7天承兑」；与付款域的枚举**刻意不同**，
   `DEV-J-03`）⇒ 列宽给足、**不做枚举约束**。⛔ 别"顺手"在这里加校验。

⚠️ **`project_id` 必有**：§6.4.1「合同**必有**项目（抓取回来的必带）⇒ **不存在"为空"**」
   ⇒ `nullable=False` ＋ **命名外键**（迁移纪律：无名外键会让 `downgrade()` 必失败）。

⚠️ 本文件**只放表与取值域常量** —— 判定（结算 / 欠款 / 三态流转 / 子表校验）一律在 `domain.py`。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY

#: 三态标记（§6.5.3）：**新抓取的默认「待确认」**；人工标记**不被后续抓取覆盖**（域层保证）
TAG_PENDING = "待确认"
TAG_IN = "纳入台账"
TAG_OUT = "不纳入"
TAGS: tuple[str, ...] = (TAG_PENDING, TAG_IN, TAG_OUT)

#: 发票子表的两种 `kind`（§6.4.2）：供应商发票 / 贸易公司发票（后者仅"有贸易公司"时启用）
KIND_SUPPLIER = "supplier"
KIND_TRADE = "trade"
INVOICE_KINDS: tuple[str, ...] = (KIND_SUPPLIER, KIND_TRADE)

#: 付款子表的来源（§6.4.3）：手工录入 / 从付款域引用
SRC_MANUAL = "manual"
SRC_NOTICE = "notice"


class JcContract(Base):
    """集采**合同主表**一行（= §6.4.1 的 19 字段里落库的那 14 个）。"""

    __tablename__ = "jc_contract"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)      # 序号（系统）
    # ⭐ **合同编号**（= i8 的 `BillNo`，如 `CGHT2026090188`）—— **抓取的幂等键**。
    #    ⚠️ §6.4.1 的 19 字段清单里**没有这一列**，是 `M5-6` 抓取落库时才发现的**真缺口**：
    #    没有它就无法"重抓同一批不重复插"，也没法判断"这张合同上次人工标记过没有"。
    #    ⇒ 定位 = **内部幂等键**（⛔ 不是给人看的业务列，页面不必展示）；人工新增的可以不填（空串）。
    #    ⚠️ **不设唯一约束**：手工新增 / Excel 导入的行可能是**空编号**，一加唯一键第二条就冲突
    #    （与 `jc_payment.notice_id` 的多 `NULL` 同理）⇒ 去重在**落库时按值判**，⛔ 不靠数据库拦。
    contract_no: Mapped[str] = mapped_column(String(64), index=True, default="")         # 合同编号（i8）
    contract_date: Mapped[str] = mapped_column(String(10), index=True, default="")      # 合同日期（抓取）
    material_name: Mapped[str] = mapped_column(String(128), index=True, default="")     # 材料名（抓取）
    supplier: Mapped[str] = mapped_column(String(128), index=True, default="")          # 供应商（抓取）
    contract_amt: Mapped[float] = mapped_column(MONEY, default=0)                       # 合同金额（唯一可抓的金额）
    trade_co: Mapped[str | None] = mapped_column(String(128), nullable=True)            # 贸易公司名（手工 · 可空）
    trade_contract_amt: Mapped[float | None] = mapped_column(MONEY, nullable=True)      # 贸易公司合同金额（可空）
    tag: Mapped[str] = mapped_column(String(8), index=True, default=TAG_PENDING)        # 三态（默认「待确认」）
    arch: Mapped[str] = mapped_column(String(8), default="")                            # 合同存档情况（手工）
    arch_no: Mapped[str] = mapped_column(String(64), default="")                        # 合同存档号（手工）
    ret_date: Mapped[str | None] = mapped_column(String(10), nullable=True)             # 合同寄回日期（可空）
    method: Mapped[str] = mapped_column(String(64), default="")                         # 付款方式（**自由文本**）
    remark: Mapped[str] = mapped_column(String(255), default="")                        # 备注（手工）
    project_id: Mapped[int] = mapped_column(
        # ⚠️ 外键**必须命名**（迁移纪律）；⛔ 不随项目级联删：合同是业务事实，
        #    要删项目得先处置合同（RESTRICT）—— 避免"删个项目把台账悄悄带走了"。
        ForeignKey("project.id", ondelete="RESTRICT", name="fk_jc_contract_project"),
        index=True,
    )                                                                                  # 项目（键 = 仓库名 · §2.7.4）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class JcInvoice(Base):
    """集采**发票子表**一行（供应商发票 / 贸易公司发票，**同款同规则** · §6.4.2）。

    ⚠️ 只记「**发票日期 ＋ 金额**」两列 —— 票号 / 税率业务上不需要（§6.4.2 的设计含义）。
    ⚠️ 校验在域层：**日期必填**（发票要能对上所属期）· **金额必须 > 0、不设上限**（2026-09-13 用户口径）。
    """

    __tablename__ = "jc_invoice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("jc_contract.id", ondelete="CASCADE", name="fk_jc_invoice_contract"), index=True
    )
    kind: Mapped[str] = mapped_column(String(8), index=True, default=KIND_SUPPLIER)      # supplier | trade
    invoice_date: Mapped[str] = mapped_column(String(10), default="")                    # 发票日期（必填 · 域层校验）
    amount: Mapped[float] = mapped_column(MONEY, default=0)                              # 金额（> 0 · 不设上限）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class JcPayment(Base):
    """集采**付款子表**一行（手工录入 / 从付款域引用 · §6.4.3）。

    ⭐ **全库去重**（§6.6.2）：同一笔付款通知书只能被引用一次 ⇒ `uq_jc_payment_notice`。
       ⚠️ 注意它**不分合同** —— 去重范围是全库，不是"同一张合同内"。
    ⚠️ 关联是**一对一**（一条通知书只关联一个合同；换合同 = 先解绑旧的再写新的）—— 由域层保证；
       本表靠唯一键把"重复引用"从**数据层**就挡掉（⛔ 不指望调用方自觉）。
    """

    __tablename__ = "jc_payment"
    __table_args__ = (
        UniqueConstraint("notice_id", name="uq_jc_payment_notice"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("jc_contract.id", ondelete="CASCADE", name="fk_jc_payment_contract"), index=True
    )
    pay_date: Mapped[str] = mapped_column(String(10), default="")                        # 付款日期
    amount: Mapped[float] = mapped_column(MONEY, default=0)                              # 付款金额
    source: Mapped[str] = mapped_column(String(8), index=True, default=SRC_MANUAL)       # manual | notice
    notice_id: Mapped[int | None] = mapped_column(
        # ⚠️ 命名外键；通知书被删 ⇒ 置空（但保留这条付款事实，⛔ 不跟着删）
        ForeignKey("payment_notice.id", ondelete="SET NULL", name="fk_jc_payment_notice"),
        nullable=True, index=True,
    )                                                                                    # 引用的通知书 id（去重键）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


__all__ = [
    "JcContract", "JcInvoice", "JcPayment",
    "TAG_PENDING", "TAG_IN", "TAG_OUT", "TAGS",
    "KIND_SUPPLIER", "KIND_TRADE", "INVOICE_KINDS",
    "SRC_MANUAL", "SRC_NOTICE",
]
