"""Durable delivery-link receipts and resumable batches."""
from alembic import op
import sqlalchemy as sa

revision = 'oil459261031'
down_revision = 'oil460261031'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('oil_delivery_link', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('link_key', sa.String(64), unique=True, nullable=False), sa.Column('token', sa.String(128), nullable=False),
        sa.Column('state', sa.String(16), nullable=False), sa.Column('message', sa.Text(), nullable=False),
        sa.Column('original_id', sa.Integer(), sa.ForeignKey('oil_invoice_original.id'), nullable=True),
        sa.Column('duplicate', sa.Boolean(), nullable=False), sa.Column('attempt', sa.String(36), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True), sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("state IN ('queued', 'running', 'done', 'failed')", name='ck_oil_delivery_state'))
    op.create_table('oil_delivery_batch', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.String(36), unique=True, nullable=False), sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_table('oil_delivery_item', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('oil_delivery_batch.id'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('link_id', sa.Integer(), sa.ForeignKey('oil_delivery_link.id'), nullable=True),
        sa.Column('reused', sa.Boolean(), nullable=False), sa.Column('error', sa.Text(), nullable=False),
        sa.UniqueConstraint('batch_id', 'position', name='uq_oil_delivery_position'))
    op.create_index('ix_oil_delivery_item_batch_id', 'oil_delivery_item', ['batch_id'])


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM oil_delivery_batch')):
        raise RuntimeError('Cannot remove delivery continuation evidence')
    op.drop_table('oil_delivery_item')
    op.drop_table('oil_delivery_batch')
    op.drop_table('oil_delivery_link')
