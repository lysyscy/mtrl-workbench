"""`MOD-09` 特殊费用月报表 · **手填项**表（`ENT-*` 未单列；口径主人 = 《说明书》§5.5）。

⚠️ **只存手填项** —— 唯一自动项（安全文明施工费）**不落库**：它由库存单据明细**现场派生**
   （`domain.auto_amount`）⇒ 落了库就是第二份真相（§5.2.3「材料数据单向流」同理）。

键 = **核算年月 ＋ 项目**（§5.5）：
- 比较 / 筛选一律用**仓库名**（§2.7.4）；
- **写库按档案 id**（§2.7.4 末行）⇒ 本表存 `project_id`（FK，**已命名**），
  仓库名不可人工修改（§9.8-4）⇒ 与「仓库名各存一份」等价，且不产生第二份可漂的键。

取值判据 = `domain.amount_problem`（**只拦非数字，允许 0 与负数**，§5.5 / §8.4 第 ③ 档）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY


class FeeItem(Base):
    """项目下统一命名的手填费用项。"""

    __tablename__ = "fee_item"
    __table_args__ = (Index("uq_fee_item_project_name_active", "project_id", "name", unique=True, postgresql_where=text("NOT deleted")),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class FeeManualItem(Base):
    """费用项在某个核算月的唯一金额。"""

    __tablename__ = "fee_monthly_amount"
    __table_args__ = (UniqueConstraint("fee_item_id", "ym", name="uq_fee_item_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fee_item_id: Mapped[int] = mapped_column(ForeignKey("fee_item.id", ondelete="RESTRICT"), index=True)
    ym: Mapped[str] = mapped_column(String(7), index=True, default="")            # 核算年月（§9.2）
    project_id: Mapped[int] = mapped_column(                                # 档案 id（§2.7.4 写库按 id）
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    item_name: Mapped[str] = mapped_column(String(128), default="")               # 项名（可改、可重名）
    amount: Mapped[float] = mapped_column(MONEY, default=0)                      # 金额（允许 0 与负数）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class LegacyFeeManualItem(Base):
    """迁移前原始费用记录，仅供保留和项目引用检查。"""
    __tablename__ = "fee_manual_item"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ym: Mapped[str] = mapped_column(String(7), index=True, default="")
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    item_name: Mapped[str] = mapped_column(String(128), default="")
    amount: Mapped[float] = mapped_column(MONEY, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


__all__ = ["FeeItem", "FeeManualItem", "LegacyFeeManualItem"]
