"""Pair internal transfers in the existing ledger."""
from alembic import op
import sqlalchemy as sa

revision = 'oil456261031'
down_revision = 'oil454261031'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('oil_entry', sa.Column('transfer_id', sa.String(36), nullable=True))
    op.create_index('ix_oil_entry_transfer_id', 'oil_entry', ['transfer_id'])
    op.create_unique_constraint('uq_oil_entry_transfer_direction', 'oil_entry', ['transfer_id', 'kind'])
    op.drop_constraint('ck_oil_entry_kind', 'oil_entry', type_='check')
    op.drop_constraint('ck_oil_entry_amount', 'oil_entry', type_='check')
    op.create_check_constraint('ck_oil_entry_kind', 'oil_entry', "kind IN ('recharge', 'adjustment', 'refund', 'transfer_out', 'transfer_in')")
    op.create_check_constraint('ck_oil_entry_amount', 'oil_entry',
        "(kind = 'recharge' AND amount > 0 AND related_entry_id IS NULL AND transfer_id IS NULL) OR "
        "(kind = 'adjustment' AND related_entry_id IS NULL AND transfer_id IS NULL) OR "
        "(kind = 'refund' AND amount < 0 AND related_entry_id IS NOT NULL AND transfer_id IS NULL) OR "
        "(kind = 'transfer_out' AND amount < 0 AND related_entry_id IS NULL AND transfer_id IS NOT NULL) OR "
        "(kind = 'transfer_in' AND amount > 0 AND related_entry_id IS NULL AND transfer_id IS NOT NULL)")


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM oil_entry WHERE transfer_id IS NOT NULL')):
        raise RuntimeError('Cannot remove transfer structure while transfer records exist')
    op.drop_constraint('ck_oil_entry_amount', 'oil_entry', type_='check')
    op.drop_constraint('ck_oil_entry_kind', 'oil_entry', type_='check')
    op.drop_constraint('uq_oil_entry_transfer_direction', 'oil_entry', type_='unique')
    op.drop_index('ix_oil_entry_transfer_id', table_name='oil_entry')
    op.drop_column('oil_entry', 'transfer_id')
    op.create_check_constraint('ck_oil_entry_kind', 'oil_entry', "kind IN ('recharge', 'adjustment', 'refund')")
    op.create_check_constraint('ck_oil_entry_amount', 'oil_entry',
        "(kind = 'recharge' AND amount > 0 AND related_entry_id IS NULL) OR "
        "(kind = 'adjustment' AND related_entry_id IS NULL) OR "
        "(kind = 'refund' AND amount < 0 AND related_entry_id IS NOT NULL)")
