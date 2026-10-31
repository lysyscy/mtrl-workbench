"""实体卡、当前用卡账户与关联历程；金额由后续独立账务记录持有。"""
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY


class OilCard(Base):
    __tablename__ = 'oil_card'
    __table_args__ = (
        CheckConstraint("kind IN ('primary', 'secondary')", name='ck_oil_card_kind'),
        CheckConstraint("kind <> 'primary' OR parent_card_id IS NULL", name='ck_oil_card_primary_parent'),
        CheckConstraint('parent_card_id IS NULL OR parent_card_id <> id', name='ck_oil_card_not_self'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    card_no: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    kind: Mapped[str] = mapped_column(String(16), default='secondary')
    parent_card_id: Mapped[int | None] = mapped_column(ForeignKey('oil_card.id'), nullable=True, index=True)
    remark: Mapped[str] = mapped_column(Text, default='')
    version: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    updated_by: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class OilAccount(Base):
    __tablename__ = 'oil_account'
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name='ck_oil_account_status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    project_id: Mapped[int] = mapped_column(ForeignKey('project.id'), index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey('oil_card.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default='active')
    remark: Mapped[str] = mapped_column(Text, default='')
    version: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    updated_by: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class OilAccountAssignment(Base):
    """每次当前关联变更的快照；不作为任何历史账务的动态归属映射。"""
    __tablename__ = 'oil_account_assignment'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('oil_account.id'), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('project.id'), index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey('oil_card.id'), nullable=True, index=True)
    changed_by: Mapped[str] = mapped_column(Text, default='')
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class OilEntry(Base):
    """每笔独立核算归属；date_text保原标记，entry_date仅存明确日期。"""
    __tablename__ = 'oil_entry'
    __table_args__ = (
        CheckConstraint("kind IN ('recharge', 'adjustment', 'refund')", name='ck_oil_entry_kind'),
        CheckConstraint("(kind = 'recharge' AND amount > 0 AND related_entry_id IS NULL) OR "
            "(kind = 'adjustment' AND related_entry_id IS NULL) OR "
            "(kind = 'refund' AND amount < 0 AND related_entry_id IS NOT NULL)", name='ck_oil_entry_amount'),
        CheckConstraint('related_entry_id IS NULL OR related_entry_id <> id', name='ck_oil_entry_not_self'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    kind: Mapped[str] = mapped_column(String(16), default='recharge')
    account_id: Mapped[int] = mapped_column(ForeignKey('oil_account.id'), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('project.id'), index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey('oil_card.id'), nullable=True, index=True)
    date_text: Mapped[str] = mapped_column(String(128), default='')
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    remark: Mapped[str] = mapped_column(Text, default='')
    related_entry_id: Mapped[int | None] = mapped_column(ForeignKey('oil_entry.id'), nullable=True, index=True)
    version: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    updated_by: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class OilOpeningBalance(Base):
    """待核/已确认期初；不伪造明细日期，也不作为某月发生额。"""
    __tablename__ = 'oil_opening_balance'
    __table_args__ = (CheckConstraint('NOT confirmed OR cutoff_ym IS NOT NULL', name='ck_oil_opening_cutoff'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(255), unique=True)
    source_note: Mapped[str] = mapped_column(Text, default='')
    account_id: Mapped[int] = mapped_column(ForeignKey('oil_account.id'), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('project.id'), index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey('oil_card.id'), nullable=True, index=True)
    original_date_text: Mapped[str] = mapped_column(String(128), default='')
    cutoff_ym: Mapped[str | None] = mapped_column(String(7), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    remark: Mapped[str] = mapped_column(Text, default='')
    updated_by: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
