"""设备三账。"""
from alembic import op
import sqlalchemy as sa

revision = 'equip261123'
down_revision = 'oillife261119'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'm16_inventory_items',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('spec', sa.Text(), nullable=True),
        sa.Column('unit', sa.Text(), nullable=True),
        sa.Column('unit_price', sa.Numeric(18, 4), nullable=True),
        sa.Column('book_qty', sa.Numeric(18, 4), nullable=False),
        sa.Column('book_amount', sa.Numeric(18, 4), nullable=True),
        sa.Column('count_qty', sa.Numeric(18, 4), nullable=False),
        sa.Column('count_amount', sa.Numeric(18, 4), nullable=True),
        sa.Column('diff_qty', sa.Numeric(18, 4), nullable=True),
        sa.Column('diff_amount', sa.Numeric(18, 4), nullable=True),
        sa.Column('diff_reason', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('source_row', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.Text(), nullable=False),
        sa.CheckConstraint("category IN ('tool', 'turnover')", name='ck_m16_inventory_items_category'),
    )
    op.create_table(
        'm16_equipment_items',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('code', sa.Text(), unique=True, nullable=False),
        sa.Column('item_category', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('spec', sa.Text(), nullable=True),
        sa.Column('unit', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Numeric(18, 4), server_default='1', nullable=False),
        sa.Column('purchase_date', sa.Date(), nullable=True),
        sa.Column('purchase_date_text', sa.Text(), nullable=True),
        sa.Column('purchase_project', sa.Text(), nullable=False),
        sa.Column('purchase_price', sa.Numeric(18, 4), nullable=True),
        sa.Column('current_project', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), server_default='in_use', nullable=False),
        sa.Column('asset_scope', sa.Text(), server_default='current_asset', nullable=False),
        sa.Column('in_rental', sa.Text(), server_default='yes', nullable=False),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('i8_sync_status', sa.Text(), server_default='pending', nullable=False),
        sa.Column('i8_sync_message', sa.Text(), nullable=True),
        sa.Column('i8_snapshot_json', sa.Text(), nullable=True),
        sa.Column('source_info', sa.Text(), nullable=True),
        sa.Column('rental_source_row', sa.Text(), nullable=True),
        sa.Column('inventory_source_row', sa.Text(), nullable=True),
        sa.Column('inventory_item_id', sa.Integer(), sa.ForeignKey('m16_inventory_items.id'), nullable=True),
        sa.Column('scrap_date', sa.Date(), nullable=True),
        sa.Column('scrap_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.Text(), nullable=False),
        sa.CheckConstraint("item_category IN ('equipment', 'turnover')", name='ck_m16_equipment_items_item_category'),
        sa.CheckConstraint("status IN ('in_use', 'damaged', 'pending_scrap', 'scrapped')", name='ck_m16_equipment_items_status'),
        sa.CheckConstraint("asset_scope IN ('current_asset', 'fixed_asset', 'off_book')", name='ck_m16_equipment_items_asset_scope'),
        sa.CheckConstraint("in_rental IN ('yes', 'no', 'pending')", name='ck_m16_equipment_items_in_rental'),
        sa.CheckConstraint("i8_sync_status IN ('synced', 'pending', 'conflict', 'failed', 'not_applicable')", name='ck_m16_equipment_items_i8_sync_status'),
    )
    op.create_table(
        'm16_equipment_transfers',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('equipment_id', sa.Integer(), sa.ForeignKey('m16_equipment_items.id'), nullable=False),
        sa.Column('item_category', sa.Text(), nullable=False),
        sa.Column('from_project', sa.Text(), nullable=False),
        sa.Column('to_project', sa.Text(), nullable=False),
        sa.Column('transfer_date', sa.Date(), nullable=True),
        sa.Column('quantity', sa.Numeric(18, 4), server_default='1', nullable=False),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('i8_sync_status', sa.Text(), server_default='pending', nullable=False),
        sa.Column('i8_sync_message', sa.Text(), nullable=True),
        sa.Column('i8_conflict_json', sa.Text(), nullable=True),
        sa.Column('rental_month', sa.Text(), nullable=True),
        sa.Column('rental_attribution', sa.Text(), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=False),
        sa.CheckConstraint("item_category IN ('equipment', 'turnover')", name='ck_m16_equipment_transfers_item_category'),
        sa.CheckConstraint("i8_sync_status IN ('synced', 'pending', 'conflict', 'failed')", name='ck_m16_equipment_transfers_i8_sync_status'),
        sa.CheckConstraint("rental_attribution IN ('pending', 'from_project', 'to_project', 'not_applicable')", name='ck_m16_equipment_transfers_rental_attribution'),
        sa.CheckConstraint("rental_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name='ck_m16_transfer_month'),
    )
    op.create_table(
        'm16_equipment_scraps',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('equipment_id', sa.Integer(), sa.ForeignKey('m16_equipment_items.id'), unique=True, nullable=False),
        sa.Column('item_category', sa.Text(), nullable=False),
        sa.Column('scrap_date', sa.Date(), nullable=False),
        sa.Column('original_project', sa.Text(), nullable=False),
        sa.Column('quantity', sa.Numeric(18, 4), server_default='1', nullable=False),
        sa.Column('purchase_price', sa.Numeric(18, 4), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('rental_stop_status', sa.Text(), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=False),
        sa.CheckConstraint("item_category IN ('equipment', 'turnover')", name='ck_m16_equipment_scraps_item_category'),
        sa.CheckConstraint("rental_stop_status IN ('pending', 'stopped', 'charge_this_month', 'not_applicable')", name='ck_m16_equipment_scraps_rental_stop_status'),
    )
    op.create_table(
        'm16_rental_months',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('month', sa.Text(), unique=True, nullable=False),
        sa.Column('status', sa.Text(), server_default='draft', nullable=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_by', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'confirmed')", name='ck_m16_rental_months_status'),
        sa.CheckConstraint("month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name='ck_m16_rental_month'),
    )
    op.create_table(
        'm16_rental_lines',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('month', sa.Text(), sa.ForeignKey('m16_rental_months.month'), nullable=False),
        sa.Column('project_name', sa.Text(), nullable=False),
        sa.Column('project_sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('row_sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('equipment_id', sa.Integer(), sa.ForeignKey('m16_equipment_items.id'), nullable=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('spec', sa.Text(), nullable=True),
        sa.Column('unit', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Numeric(18, 4), server_default='1', nullable=False),
        sa.Column('original_value', sa.Numeric(18, 4), nullable=True),
        sa.Column('custom_unit_price', sa.Numeric(18, 4), nullable=True),
        sa.Column('unit_price', sa.Numeric(18, 4), nullable=True),
        sa.Column('amount', sa.Numeric(18, 4), nullable=True),
        sa.Column('category_label', sa.Text(), server_default='大型工机具', nullable=False),
        sa.Column('distribution_note', sa.Text(), nullable=True),
        sa.Column('billing_status', sa.Text(), server_default='normal', nullable=False),
        sa.Column('pending_action_type', sa.Text(), server_default='none', nullable=False),
        sa.Column('pending_meta_json', sa.Text(), nullable=True),
        sa.Column('source_row', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("billing_status IN ('normal', 'skip_month', 'stopped', 'blank')", name='ck_m16_rental_lines_billing_status'),
        sa.CheckConstraint("pending_action_type IN ('none', 'new_purchase_start', 'transfer_attribution', 'scrap_stop')", name='ck_m16_rental_lines_pending_action_type'),
        sa.UniqueConstraint('month', 'equipment_id', name='uq_m16_rental_equipment_month'),
    )


def downgrade():
    op.drop_table('m16_rental_lines')
    op.drop_table('m16_rental_months')
    op.drop_table('m16_equipment_scraps')
    op.drop_table('m16_equipment_transfers')
    op.drop_table('m16_equipment_items')
    op.drop_table('m16_inventory_items')
