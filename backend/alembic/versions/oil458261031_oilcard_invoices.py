"""Invoice identity, immutable PDF evidence and accounting allocations."""
from alembic import op
import sqlalchemy as sa

revision = 'oil458261031'
down_revision = 'oil457261031'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('oil_invoice',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('invoice_no', sa.String(32), unique=True, nullable=True),
        sa.Column('invoice_date', sa.Date(), nullable=True),
        sa.Column('amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('card_no', sa.String(128), nullable=True),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('remark', sa.Text(), nullable=False),
        sa.Column('version', sa.String(36), nullable=False),
        sa.Column('updated_by', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'registered')", name='ck_oil_invoice_status'))
    op.create_table('oil_invoice_original',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sha256', sa.String(64), unique=True, nullable=False),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('oil_invoice.id'), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('byte_size', sa.Integer(), nullable=False),
        sa.Column('outcome', sa.String(16), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('recognized_json', sa.Text(), nullable=False),
        sa.Column('received_by', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("outcome IN ('received', 'duplicate', 'conflict')", name='ck_oil_original_outcome'))
    op.create_index('ix_oil_invoice_original_invoice_id', 'oil_invoice_original', ['invoice_id'])
    op.create_table('oil_invoice_allocation',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('oil_invoice.id'), nullable=False),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('oil_account.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id'), nullable=False),
        sa.Column('card_id', sa.Integer(), sa.ForeignKey('oil_card.id'), nullable=True),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.UniqueConstraint('invoice_id', 'account_id', name='uq_oil_invoice_account'))
    for column in ('invoice_id', 'account_id', 'project_id', 'card_id'):
        op.create_index('ix_oil_invoice_allocation_' + column, 'oil_invoice_allocation', [column])


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM oil_invoice_original')):
        raise RuntimeError('Cannot remove archived invoice originals')
    op.drop_table('oil_invoice_allocation')
    op.drop_table('oil_invoice_original')
    op.drop_table('oil_invoice')
