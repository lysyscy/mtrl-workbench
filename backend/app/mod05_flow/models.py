"""付款流水 / 期初占位行 / 台账备注（`MOD-05`）。

依据：《说明书》§4.4.2（付款登记：一次付款一条流水）· §4.4.5（撤销：按流水号 + **必填原因**）
      · §4.5.1（欠款口径）· §4.5.2（期初占位行）· §4.5.4（逐月台账备注：键 = 口径 + 项目 + 月）。

⚠️ 付款状态**只有两态**（已付清 / 未付清，"部分付"已取消，§4.4.2）；状态判定基准 = **审批金额**。
⚠️ 撤销**只回退流水汇总**，不改 i8 源数据、不改两个统计字段（§4.4.5 · §9.3 旁路思路）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY

# 分类（§4.2.3 三类，**没有"其他"类**）
CATEGORY_MATERIAL = "material"     # 辅材
CATEGORY_MECH = "mechanical"       # 机械
CATEGORY_JC = "jc"                 # 集采
CATEGORIES = (CATEGORY_MATERIAL, CATEGORY_MECH, CATEGORY_JC)

# 流水状态
FLOW_EFFECTIVE = "effective"       # 生效
FLOW_REVOKED = "revoked"           # 已撤销

# ⭐ 流水来源（§4.4.6）—— 用于区分「付款动作产生」与「历史 Excel 台账导入」
FLOW_SOURCE_MANUAL = "manual"      # 付款动作产生（§4.4.4）
FLOW_SOURCE_IMPORTED = "imported"  # 历史 Excel 台账导入（§4.4.6）

# 付款状态（**只有两态**，§4.4.2）
PAY_STATUS_PAID = "paid"           # 已付清
PAY_STATUS_UNPAID = "unpaid"       # 未付清

# 实际付款方式（§4.4.2）
PAY_METHODS = ("现汇", "承兑", "供应链", "其他")


class PaymentFlow(Base):
    """付款流水 —— **一次付款一条独立流水**（不做金额累计覆盖，§4.4.2）。"""

    __tablename__ = "payment_flow"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flow_no: Mapped[str] = mapped_column(String(64), index=True, default="")   # 流水号（撤销按它）
    notice_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_notice.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount: Mapped[float] = mapped_column(MONEY, default=0)                    # 实付金额
    pay_date: Mapped[str] = mapped_column(String(32), index=True, default="")
    pay_method: Mapped[str] = mapped_column(String(32), default="现汇")        # 默认兜底「现汇」
    # ⚠️ 历史导入的流水**付款方式可以为空**（事实记录、不得编造，§4.4.6）⇒ 不兜底
    source: Mapped[str] = mapped_column(String(16), index=True, default=FLOW_SOURCE_MANUAL)
    import_batch: Mapped[str] = mapped_column(String(64), index=True, default="")   # 导入批次（§4.4.6）
    remark: Mapped[str] = mapped_column(String(512), default="")                    # Excel E 列备注
    status: Mapped[str] = mapped_column(String(16), index=True, default=FLOW_EFFECTIVE)
    revoke_reason: Mapped[str] = mapped_column(String(512), default="")        # ⚠️ 撤销**必填**
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), default="")            # 防重复提交（§4.4.4）
    #: ⭐ **操作人**（§1.5.1 末行：「留痕的**改前人 / 录入人**一律取**当前登录用户**」）。
    #: ⚠️ **本列是 2026-09-20 补的**（迁移 `d1f3a5c7e9b2`）—— 在此之前页面上那一列
    #:   `FL_THEAD`「操作人」**显示的是 `created_at`（时间）**（当时这张表根本没记人，不是笔误）。
    #: ⭐ **2026-10-11（`TAIL-283`）壳侧已改对**：`core.js::adaptFlow` 的 `op` 现在取**本列**
    #:   （`x.created_by || ''`）⇒ 页面与 Excel 的「操作人」都才是"谁办的"；老行空串**如实留空**。
    #: ⚠️ **取值一律走唯一出口** `core/identity.py::current_operator()`（⛔ 不写死名字）；
    #:   老行为**空串** = **如实表示"当时没记"**（⛔ 不要为它编一个名字）。
    #: ⚠️ `server_default=""` **必须留着**（2026-09-26 · `TAIL-102` 修复）：它是迁移
    #:   `d1f3a5c7e9b2` 加这一列时给的（**非空表加非空列必须给默认值**，否则 upgrade 直接报错），
    #:   而模型原先没声明 ⇒ `alembic check` 永远报 `modify_default`（元数据与库两份说法不一致）。
    #:   ⛔ 别用"写一条迁移把库里的默认值删掉"来对齐：那要动**线上库的列**，且丢掉"裸插入留空串"这层兜底。
    created_by: Mapped[str] = mapped_column(String(64), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class OpeningBalance(Base):
    """历史台账编辑记录；manual为辅材独立行，month为历史月份金额覆盖。"""

    __tablename__ = "opening_balance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(16), index=True, default=CATEGORY_MATERIAL)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cutoff_ym: Mapped[str] = mapped_column(String(7), default="")       # 所属月份，不截断其他行
    settle_amount: Mapped[float] = mapped_column(MONEY, default=0)      # 手填结算
    paid_amount: Mapped[float] = mapped_column(MONEY, default=0)        # 手填付款
    remark: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    entry_kind: Mapped[str] = mapped_column(String(16), default="manual", server_default="manual")


class LedgerRemark(Base):
    """逐月台账备注（**键 = 口径 + 项目 + 月**，§4.5.4）。可写可清。"""

    __tablename__ = "ledger_remark"
    __table_args__ = (
        UniqueConstraint("category", "project_id", "ym", name="uq_ledger_remark_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(16), index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    ym: Mapped[str] = mapped_column(String(7), index=True)
    remark: Mapped[str] = mapped_column(String(512), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class FlowRevokeLog(Base):
    """撤销留痕（§9.3：撤销原因即留痕；**只有撤销动作**进此表）。"""

    __tablename__ = "flow_revoke_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flow_id: Mapped[int] = mapped_column(ForeignKey("payment_flow.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(512), default="")
    changed_by: Mapped[str] = mapped_column(String(64), default="")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
