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

# ---------------------------------------------------------------- 甲方单位分类（`M5-6b`）
#: 甲方单位的三类（用户 **2026-09-20** 口径）—— ⭐ 它决定"**i8 抓来的那个合同价，是谁的价**"。
#:
#: **为什么必须有这个概念**（实测 `CGHT202509270005`）：
#: ```
#: PhidCustomerEnt_EXName = 洛阳维萨工程技术有限公司     ← 甲方 = 贸易公司
#: PhidSupplyEnt_EXName   = 哈密市鑫盛发物资有限责任公司  ← 乙方 = **真供应商**
#: CntSumVat              = 171983.28                  ← ⚠️ 这是【维萨的价】
#:                                                       真供应商的价 i8 里【没有】
#: ```
#: ⇒ 正常甲方 ⇒ i8 的价就是**供应商价** ⇒ 落 `contract_amt`；
#:   贸易公司甲方 ⇒ i8 的价是**贸易公司的价** ⇒ 落 `trade_contract_amt`，
#:   而 `contract_amt`（供应商价）**要人工从 Excel 的供应商线补填**（i8 抓不到）。
#: ⛔ 判错了 = **金额落错列**，而且**不会报错**（数字看着都合理）—— 这是本表存在的唯一理由。
KIND_PARTY_NORMAL = "normal"        # 正常甲方（第四工程公司 / 河南省安装集团…）
KIND_PARTY_TRADE = "trade"          # 贸易公司（洛阳维萨…）—— 是"供应商与我公司之间的桥梁"
KIND_PARTY_UNKNOWN = "unknown"      # **没见过的甲方** ⇒ 抓到时自动登记，等人指定（⛔ 不静默归类）
PARTY_KINDS: tuple[str, ...] = (KIND_PARTY_NORMAL, KIND_PARTY_TRADE, KIND_PARTY_UNKNOWN)
PARTY_KIND_NAMES: dict[str, str] = {
    KIND_PARTY_NORMAL: "正常", KIND_PARTY_TRADE: "贸易公司", KIND_PARTY_UNKNOWN: "未指定",
}


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
    #: ⭐ **i8 单据名原文**（`BillName`，如 `四分晋江污泥项目/主材钢材/业祥/河南安装/27269.82元`）。
    #:   ⚠️⚠️ **2026-09-19 补**：原先**丢了它** —— `_map_record` 的注释写着"整条原样留在 `fields`
    #:   （不丢信息）"，但本表**没有那个列**、`FETCH_COLS` 也没带它 ⇒ **静默丢掉**。
    #:   后果很实在：「拆出来的材料名 / 供应商对不对」**无法回溯**，只能**重抓一次**才能验证（当日实际发生）。
    #:   ⇒ 定位 = **原始凭证**（⛔ 不是给人看的显示列，页面不必展示）：材料名是从它拆的、供应商是拿它对照的。
    #:   ⚠️ 在 `FETCH_COLS` 里 ⇒ 重抓会刷新（它是 i8 的原文，⛔ 不是人的地盘）。
    bill_name: Mapped[str] = mapped_column(String(255), default="")                     # i8 单据名原文
    material_name: Mapped[str] = mapped_column(String(128), index=True, default="")     # 材料名（抓取）
    supplier: Mapped[str] = mapped_column(String(128), index=True, default="")          # 供应商（抓取）
    contract_amt: Mapped[float] = mapped_column(MONEY, default=0)                       # 合同金额（唯一可抓的金额）
    #: ⭐ **甲方单位**（i8 的 `PhidCustomerEnt_EXName`）—— 用户 2026-09-20 口径的**判据列**。
    #:   ⚠️ 它**只在贸易公司合同上决定 `contract_amt` 是谁的价**（见 `KIND_PARTY_*` 那段）。
    #:   ⚠️ 人**不手改**它（i8 的事实）⇒ 在 `FETCH_COLS` 里、重抓刷新。
    #:   ⚠️ 存量行**必须带 `server_default=''`**（已有数据的库加 `NOT NULL` 列会 NotNullViolation —— 2026-09-19 踩过）。
    party_name: Mapped[str] = mapped_column(String(128), default="", server_default="", index=True)
    trade_co: Mapped[str | None] = mapped_column(String(128), nullable=True)            # 贸易公司名（手工 · 可空）
    trade_contract_amt: Mapped[float | None] = mapped_column(MONEY, nullable=True)      # 贸易公司合同金额（可空）
    tag: Mapped[str] = mapped_column(String(8), index=True, default=TAG_PENDING)        # 三态（默认「待确认」）
    arch: Mapped[str] = mapped_column(String(8), default="")                            # 合同存档情况（手工）
    arch_no: Mapped[str] = mapped_column(String(64), default="")                        # 合同存档号（手工）
    ret_date: Mapped[str | None] = mapped_column(String(10), nullable=True)             # 合同寄回日期（可空）
    #: ⚠️⚠️ **2026-09-20 实测从 64 放宽到 512**：用户台账里「详细付款方式」那种**整段付款条款**
    #:    最长 **95 字**（"货到验收合格后，银行承兑付款，货到现场验收合格并开具全额发票后支付 50% 货款…"）
    #:    ⇒ 64 装不下 ⇒ Postgres 直接 `value too long for type character varying(64)`。
    #:    ⚠️ 而这条列**本来就是这个模型头上写着的**「自由文本 ⇒ **列宽给足**」—— 只是当时没给足。
    #:    512 = 实测 95 字的 5 倍余量（付款条款只会更长、不会更短）。
    #:    ⚠️ 判据 `ACC-JC-UI-001/001-12`（三列可手改并落值）也管这一列 ⇒ 装不下就是**落值失败**。
    method: Mapped[str] = mapped_column(String(512), default="")                        # 付款方式（**自由文本**）
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


class JcPartyKind(Base):
    """**甲方单位分类**（`M5-6b`）—— 一张小表，键 = 甲方单位**全名**。

    ⭐ 存在的理由见 `KIND_PARTY_*` 那段注释（决定 i8 的金额落哪一列）。
    ⚠️ **为什么不硬编码"维萨"两个字**：换一家贸易公司就得改代码、发版。名单配在这里，改数据即可。
    ⚠️ **为什么不写"两个名单"**（正常名单 + 贸易公司名单）：名单会**漏** —— 冒出一个没见过的甲方
       ⇒ 落在两个名单**之外** ⇒ 规则**没有出口** ⇒ 只能瞎猜（最坏的一类错）。
       ⇒ 做成**分类表**：没见过的甲方**自动落成 `unknown`**（抓取时 `ensure_party_kinds` 登记）
         ⇒ 页面**列出来等人指定**，⛔ 不静默归类。
    """

    __tablename__ = "jc_party_kind"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)   # 甲方单位全名（i8 的 `PhidCustomerEnt_EXName`）
    kind: Mapped[str] = mapped_column(String(8), index=True, default=KIND_PARTY_UNKNOWN)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


__all__ = [
    "JcContract", "JcInvoice", "JcPayment", "JcPartyKind",
    "TAG_PENDING", "TAG_IN", "TAG_OUT", "TAGS",
    "KIND_SUPPLIER", "KIND_TRADE", "INVOICE_KINDS",
    "SRC_MANUAL", "SRC_NOTICE",
    "KIND_PARTY_NORMAL", "KIND_PARTY_TRADE", "KIND_PARTY_UNKNOWN",
    "PARTY_KINDS", "PARTY_KIND_NAMES",
]
