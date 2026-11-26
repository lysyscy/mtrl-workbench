"""设备分布、盘点和月租台账。"""
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.identity import current_operator


class Location(Base):
    __tablename__ = 'm16_locations'
    __table_args__ = (sa.CheckConstraint("btrim(name) <> ''", name='ck_m16_locations_name'),)

    id: Mapped[int] = mapped_column(sa.Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(sa.Text(), unique=True)
    default_project_id: Mapped[int | None] = mapped_column(sa.ForeignKey('project.id', ondelete='SET NULL'))
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.true())
    sort_order: Mapped[int] = mapped_column(sa.Integer(), server_default='0')
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now(), onupdate=datetime.now)


class InventoryItem(Base):
    __tablename__ = 'm16_inventory_items'
    __table_args__ = (
        sa.CheckConstraint("category IN ('tool', 'turnover')", name='ck_m16_inventory_items_category'),
    )

    id: Mapped[int] = mapped_column(sa.Integer(), primary_key=True)
    category: Mapped[str] = mapped_column(sa.Text())
    sort_order: Mapped[int] = mapped_column(sa.Integer(), server_default='0')
    name: Mapped[str] = mapped_column(sa.Text())
    spec: Mapped[str | None] = mapped_column(sa.Text())
    unit: Mapped[str | None] = mapped_column(sa.Text())
    unit_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    book_qty: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4))
    book_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    count_qty: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    count_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    diff_qty: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    diff_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    diff_reason: Mapped[str | None] = mapped_column(sa.Text())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default='true')
    source_row: Mapped[str | None] = mapped_column(sa.Text())
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now(), onupdate=datetime.now)
    created_by: Mapped[str] = mapped_column(sa.Text(), default=current_operator)
    updated_by: Mapped[str] = mapped_column(sa.Text(), default=current_operator)


class EquipmentItem(Base):
    __tablename__ = 'm16_equipment_items'
    __table_args__ = (
        sa.CheckConstraint("item_category IN ('equipment', 'turnover')", name='ck_m16_equipment_items_item_category'),
        sa.CheckConstraint("status IN ('in_use', 'damaged', 'pending_scrap', 'scrapped')", name='ck_m16_equipment_items_status'),
        sa.CheckConstraint("asset_scope IN ('current_asset', 'fixed_asset', 'off_book')", name='ck_m16_equipment_items_asset_scope'),
        sa.CheckConstraint("in_rental IN ('yes', 'no', 'pending')", name='ck_m16_equipment_items_in_rental'),
        sa.CheckConstraint("i8_sync_status IN ('synced', 'pending', 'conflict', 'failed', 'not_applicable')", name='ck_m16_equipment_items_i8_sync_status'),
    )

    id: Mapped[int] = mapped_column(sa.Integer(), primary_key=True)
    code: Mapped[str] = mapped_column(sa.Text(), unique=True)
    item_category: Mapped[str] = mapped_column(sa.Text())
    name: Mapped[str] = mapped_column(sa.Text())
    spec: Mapped[str | None] = mapped_column(sa.Text())
    unit: Mapped[str | None] = mapped_column(sa.Text())
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), server_default='1')
    purchase_date: Mapped[date | None] = mapped_column(sa.Date())
    purchase_date_text: Mapped[str | None] = mapped_column(sa.Text())
    purchase_project: Mapped[str] = mapped_column(sa.Text())
    purchase_project_id: Mapped[int | None] = mapped_column(sa.ForeignKey('project.id', ondelete='SET NULL'))
    purchase_project_custom: Mapped[str | None] = mapped_column(sa.Text())
    purchase_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    current_project: Mapped[str] = mapped_column(sa.Text())
    current_project_id: Mapped[int | None] = mapped_column(sa.ForeignKey('project.id', ondelete='SET NULL'))
    current_project_custom: Mapped[str | None] = mapped_column(sa.Text())
    status: Mapped[str] = mapped_column(sa.Text(), server_default='in_use')
    asset_scope: Mapped[str] = mapped_column(sa.Text(), server_default='current_asset')
    in_rental: Mapped[str] = mapped_column(sa.Text(), server_default='yes')
    remark: Mapped[str | None] = mapped_column(sa.Text())
    i8_sync_status: Mapped[str] = mapped_column(sa.Text(), server_default='pending')
    i8_sync_message: Mapped[str | None] = mapped_column(sa.Text())
    i8_snapshot_json: Mapped[str | None] = mapped_column(sa.Text())
    source_info: Mapped[str | None] = mapped_column(sa.Text())
    rental_source_row: Mapped[str | None] = mapped_column(sa.Text())
    inventory_source_row: Mapped[str | None] = mapped_column(sa.Text())
    source_lists_inventory: Mapped[bool | None] = mapped_column(sa.Boolean())
    inventory_item_id: Mapped[int | None] = mapped_column(sa.Integer(), sa.ForeignKey('m16_inventory_items.id'))
    scrap_date: Mapped[date | None] = mapped_column(sa.Date())
    scrap_reason: Mapped[str | None] = mapped_column(sa.Text())
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now(), onupdate=datetime.now)
    created_by: Mapped[str] = mapped_column(sa.Text(), default=current_operator)
    updated_by: Mapped[str] = mapped_column(sa.Text(), default=current_operator)


class EquipmentTransfer(Base):
    __tablename__ = 'm16_equipment_transfers'
    __table_args__ = (
        sa.CheckConstraint("item_category IN ('equipment', 'turnover')", name='ck_m16_equipment_transfers_item_category'),
        sa.CheckConstraint("i8_sync_status IN ('synced', 'pending', 'conflict', 'failed', 'not_applicable')", name='ck_m16_equipment_transfers_i8_sync_status'),
        sa.CheckConstraint("rental_attribution IN ('pending', 'from_project', 'to_project', 'not_applicable')", name='ck_m16_equipment_transfers_rental_attribution'),
        sa.CheckConstraint("rental_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name='ck_m16_transfer_month'),
    )

    id: Mapped[int] = mapped_column(sa.Integer(), primary_key=True)
    equipment_id: Mapped[int] = mapped_column(sa.Integer(), sa.ForeignKey('m16_equipment_items.id'))
    item_category: Mapped[str] = mapped_column(sa.Text())
    from_project: Mapped[str] = mapped_column(sa.Text())
    from_project_id: Mapped[int | None] = mapped_column(sa.ForeignKey('project.id', ondelete='SET NULL'))
    from_project_custom: Mapped[str | None] = mapped_column(sa.Text())
    to_project: Mapped[str] = mapped_column(sa.Text())
    to_project_id: Mapped[int | None] = mapped_column(sa.ForeignKey('project.id', ondelete='SET NULL'))
    to_project_custom: Mapped[str | None] = mapped_column(sa.Text())
    transfer_date: Mapped[date | None] = mapped_column(sa.Date())
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), server_default='1')
    remark: Mapped[str | None] = mapped_column(sa.Text())
    i8_sync_status: Mapped[str] = mapped_column(sa.Text(), server_default='pending')
    i8_sync_message: Mapped[str | None] = mapped_column(sa.Text())
    i8_conflict_json: Mapped[str | None] = mapped_column(sa.Text())
    rental_month: Mapped[str | None] = mapped_column(sa.Text())
    rental_attribution: Mapped[str] = mapped_column(sa.Text(), server_default='pending')
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now())
    created_by: Mapped[str] = mapped_column(sa.Text(), default=current_operator)


class EquipmentScrap(Base):
    __tablename__ = 'm16_equipment_scraps'
    __table_args__ = (
        sa.CheckConstraint("item_category IN ('equipment', 'turnover')", name='ck_m16_equipment_scraps_item_category'),
        sa.CheckConstraint("rental_stop_status IN ('pending', 'stopped', 'charge_this_month', 'not_applicable')", name='ck_m16_equipment_scraps_rental_stop_status'),
    )

    id: Mapped[int] = mapped_column(sa.Integer(), primary_key=True)
    equipment_id: Mapped[int] = mapped_column(sa.Integer(), sa.ForeignKey('m16_equipment_items.id'), unique=True)
    item_category: Mapped[str] = mapped_column(sa.Text())
    scrap_date: Mapped[date] = mapped_column(sa.Date())
    original_project: Mapped[str] = mapped_column(sa.Text())
    original_project_id: Mapped[int | None] = mapped_column(sa.ForeignKey('project.id', ondelete='SET NULL'))
    original_project_custom: Mapped[str | None] = mapped_column(sa.Text())
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), server_default='1')
    purchase_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    reason: Mapped[str | None] = mapped_column(sa.Text())
    rental_stop_status: Mapped[str] = mapped_column(sa.Text(), server_default='pending')
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now())
    created_by: Mapped[str] = mapped_column(sa.Text(), default=current_operator)


class RentalMonth(Base):
    __tablename__ = 'm16_rental_months'
    __table_args__ = (
        sa.CheckConstraint("status IN ('draft', 'confirmed')", name='ck_m16_rental_months_status'),
        sa.CheckConstraint("month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name='ck_m16_rental_month'),
    )

    id: Mapped[int] = mapped_column(sa.Integer(), primary_key=True)
    month: Mapped[str] = mapped_column(sa.Text(), unique=True)
    status: Mapped[str] = mapped_column(sa.Text(), server_default='draft')
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime())
    confirmed_by: Mapped[str | None] = mapped_column(sa.Text())
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now(), onupdate=datetime.now)


class RentalLine(Base):
    __tablename__ = 'm16_rental_lines'
    __table_args__ = (
        sa.CheckConstraint("billing_status IN ('normal', 'skip_month', 'stopped', 'blank')", name='ck_m16_rental_lines_billing_status'),
        sa.CheckConstraint("pending_action_type IN ('none', 'new_purchase_start', 'transfer_attribution', 'scrap_stop')", name='ck_m16_rental_lines_pending_action_type'),
        sa.UniqueConstraint('month', 'equipment_id', name='uq_m16_rental_equipment_month'),
    )

    id: Mapped[int] = mapped_column(sa.Integer(), primary_key=True)
    month: Mapped[str] = mapped_column(sa.Text(), sa.ForeignKey('m16_rental_months.month'))
    project_name: Mapped[str] = mapped_column(sa.Text())
    project_id: Mapped[int | None] = mapped_column(sa.ForeignKey('project.id', ondelete='SET NULL'))
    project_custom: Mapped[str | None] = mapped_column(sa.Text())
    project_sort_order: Mapped[int] = mapped_column(sa.Integer(), server_default='0')
    row_sort_order: Mapped[int] = mapped_column(sa.Integer(), server_default='0')
    equipment_id: Mapped[int | None] = mapped_column(sa.Integer(), sa.ForeignKey('m16_equipment_items.id'))
    name: Mapped[str] = mapped_column(sa.Text())
    spec: Mapped[str | None] = mapped_column(sa.Text())
    unit: Mapped[str | None] = mapped_column(sa.Text())
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), server_default='1')
    original_value: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    custom_unit_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    unit_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    category_label: Mapped[str] = mapped_column(sa.Text(), server_default='大型工机具')
    distribution_note: Mapped[str | None] = mapped_column(sa.Text())
    billing_status: Mapped[str] = mapped_column(sa.Text(), server_default='normal')
    pending_action_type: Mapped[str] = mapped_column(sa.Text(), server_default='none')
    pending_meta_json: Mapped[str | None] = mapped_column(sa.Text())
    source_row: Mapped[str | None] = mapped_column(sa.Text())
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), server_default=sa.func.now(), onupdate=datetime.now)
