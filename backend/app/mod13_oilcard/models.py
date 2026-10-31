"""实体卡、当前用卡账户与关联历程；金额由后续独立账务记录持有。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


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
