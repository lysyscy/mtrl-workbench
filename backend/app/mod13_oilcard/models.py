"""实体卡、当前用卡账户与关联历程；金额由后续独立账务记录持有。"""
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
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
    __table_args__ = (
        CheckConstraint("change_kind IN ('assignment', 'replacement')", name='ck_oil_assignment_kind'),
        UniqueConstraint('request_id', name='uq_oil_assignment_request'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('oil_account.id'), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('project.id'), index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey('oil_card.id'), nullable=True, index=True)
    previous_card_id: Mapped[int | None] = mapped_column(ForeignKey('oil_card.id', name='oil_account_assignment_previous_card_id_fkey'), nullable=True)
    change_kind: Mapped[str] = mapped_column(String(16), default='assignment', server_default='assignment')
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changed_by: Mapped[str] = mapped_column(Text, default='')
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class OilEntry(Base):
    """每笔独立核算归属；date_text保原标记，entry_date仅存明确日期。"""
    __tablename__ = 'oil_entry'
    __table_args__ = (
        CheckConstraint("kind IN ('recharge', 'adjustment', 'refund', 'transfer_out', 'transfer_in')", name='ck_oil_entry_kind'),
        CheckConstraint("(kind = 'recharge' AND amount > 0 AND related_entry_id IS NULL AND transfer_id IS NULL) OR "
            "(kind = 'adjustment' AND related_entry_id IS NULL AND transfer_id IS NULL) OR "
            "(kind = 'refund' AND amount < 0 AND related_entry_id IS NOT NULL AND transfer_id IS NULL) OR "
            "(kind = 'transfer_out' AND amount < 0 AND related_entry_id IS NULL AND transfer_id IS NOT NULL) OR "
            "(kind = 'transfer_in' AND amount > 0 AND related_entry_id IS NULL AND transfer_id IS NOT NULL)", name='ck_oil_entry_amount'),
        CheckConstraint('related_entry_id IS NULL OR related_entry_id <> id', name='ck_oil_entry_not_self'),
        UniqueConstraint('transfer_id', 'kind', name='uq_oil_entry_transfer_direction'),
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
    transfer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
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


class OilFeeCustom(Base):
    """项目/月发生的特殊费用补充额；不存派生充值或完整报表总额。"""
    __tablename__ = 'oil_fee_custom'
    __table_args__ = (UniqueConstraint('project_id', 'ym', name='uq_oil_fee_custom_month'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('project.id'), index=True)
    ym: Mapped[str] = mapped_column(String(7), index=True)
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    remark: Mapped[str] = mapped_column(Text, default='')
    version: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    updated_by: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class OilBigCustom(Base):
    """大表截至月额外值与独立备注的同笔快照；0终止沿用。"""
    __tablename__ = 'oil_big_custom'
    __table_args__ = (UniqueConstraint('project_id', 'ym', name='uq_oil_big_custom_month'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('project.id'), index=True)
    ym: Mapped[str] = mapped_column(String(7), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    remark: Mapped[str] = mapped_column(Text, default='')
    version: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    updated_by: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class OilInvoice(Base):
    """票据索引与人工确认结果；原件身份独立，不能经更正或撤销删除。"""
    __tablename__ = 'oil_invoice'
    __table_args__ = (CheckConstraint("status IN ('pending', 'registered', 'voided')", name='ck_oil_invoice_status'),
        CheckConstraint("kind IN ('normal', 'credit')", name='ck_oil_invoice_kind'))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_no: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    card_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default='pending')
    kind: Mapped[str] = mapped_column(String(16), default='normal', server_default='normal')
    related_invoice_id: Mapped[int | None] = mapped_column(ForeignKey('oil_invoice.id'), nullable=True, index=True)
    review_json: Mapped[str] = mapped_column(Text, default='{}', server_default='{}')
    change_note: Mapped[str] = mapped_column(Text, default='', server_default='')
    void_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default='')
    remark: Mapped[str] = mapped_column(Text, default='')
    version: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    updated_by: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class OilInvoiceOriginal(Base):
    """不可变接收依据。bytea随现有pg_dump一起备份，不属于可删除的操作历史。"""
    __tablename__ = 'oil_invoice_original'
    __table_args__ = (CheckConstraint("outcome IN ('received', 'duplicate', 'conflict')", name='ck_oil_original_outcome'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey('oil_invoice.id'), index=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    byte_size: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text, default='')
    recognized_json: Mapped[str] = mapped_column(Text)
    received_by: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class OilInvoiceAllocation(Base):
    __tablename__ = 'oil_invoice_allocation'
    __table_args__ = (UniqueConstraint('invoice_id', 'account_id', name='uq_oil_invoice_account'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey('oil_invoice.id'), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('oil_account.id'), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('project.id'), index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey('oil_card.id'), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)


class OilInvoiceNumber(Base):
    """Historical recognized/corrected numbers keep cross-receipt identity."""
    __tablename__ = 'oil_invoice_number'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey('oil_invoice.id'), index=True)
    number: Mapped[str] = mapped_column(String(32), unique=True)


class OilDeliveryLink(Base):
    """Private provider token and durable receipt identity; never returned to the UI."""
    __tablename__ = 'oil_delivery_link'
    __table_args__ = (CheckConstraint("state IN ('queued', 'running', 'done', 'failed')", name='ck_oil_delivery_state'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    link_key: Mapped[str] = mapped_column(String(64), unique=True)
    token: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(16), default='queued')
    message: Mapped[str] = mapped_column(Text, default='')
    original_id: Mapped[int | None] = mapped_column(ForeignKey('oil_invoice_original.id'), nullable=True)
    duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    attempt: Mapped[str | None] = mapped_column(String(36), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class OilDeliveryBatch(Base):
    __tablename__ = 'oil_delivery_batch'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class OilDeliveryItem(Base):
    __tablename__ = 'oil_delivery_item'
    __table_args__ = (UniqueConstraint('batch_id', 'position', name='uq_oil_delivery_position'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('oil_delivery_batch.id'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    link_id: Mapped[int | None] = mapped_column(ForeignKey('oil_delivery_link.id'), nullable=True)
    reused: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str] = mapped_column(Text, default='')
