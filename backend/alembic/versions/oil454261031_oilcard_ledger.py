"""Oil recharge, adjustments, linked refunds and confirmed opening balances."""
from alembic import op
import sqlalchemy as sa

revision = 'oil454261031'
down_revision = 'oil453261031'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('oil_entry',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.String(36), unique=True, nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('oil_account.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id'), nullable=False),
        sa.Column('card_id', sa.Integer(), sa.ForeignKey('oil_card.id'), nullable=True),
        sa.Column('date_text', sa.String(128), nullable=False),
        sa.Column('entry_date', sa.Date(), nullable=True),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('remark', sa.Text(), nullable=False),
        sa.Column('related_entry_id', sa.Integer(), sa.ForeignKey('oil_entry.id'), nullable=True),
        sa.Column('version', sa.String(36), nullable=False),
        sa.Column('updated_by', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('recharge', 'adjustment', 'refund')", name='ck_oil_entry_kind'),
        sa.CheckConstraint("(kind = 'recharge' AND amount > 0 AND related_entry_id IS NULL) OR "
            "(kind = 'adjustment' AND related_entry_id IS NULL) OR "
            "(kind = 'refund' AND amount < 0 AND related_entry_id IS NOT NULL)", name='ck_oil_entry_amount'),
        sa.CheckConstraint('related_entry_id IS NULL OR related_entry_id <> id', name='ck_oil_entry_not_self'))
    for field in ('account_id', 'project_id', 'card_id', 'entry_date', 'related_entry_id'):
        op.create_index(f'ix_oil_entry_{field}', 'oil_entry', [field])
    op.create_table('oil_opening_balance',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source_key', sa.String(255), unique=True, nullable=False),
        sa.Column('source_note', sa.Text(), nullable=False),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('oil_account.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id'), nullable=False),
        sa.Column('card_id', sa.Integer(), sa.ForeignKey('oil_card.id'), nullable=True),
        sa.Column('original_date_text', sa.String(128), nullable=False),
        sa.Column('cutoff_ym', sa.String(7), nullable=True),
        sa.Column('confirmed', sa.Boolean(), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('remark', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('NOT confirmed OR cutoff_ym IS NOT NULL', name='ck_oil_opening_cutoff'))
    for field in ('account_id', 'project_id', 'card_id'):
        op.create_index(f'ix_oil_opening_balance_{field}', 'oil_opening_balance', [field])


def downgrade():
    op.drop_table('oil_opening_balance')
    op.drop_table('oil_entry')
