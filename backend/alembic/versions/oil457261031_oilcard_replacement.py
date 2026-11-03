"""Keep explicit replacement events alongside current assignment snapshots."""
from alembic import op
import sqlalchemy as sa

revision = 'oil457261031'
down_revision = 'oil456261031'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('oil_account_assignment', sa.Column('previous_card_id', sa.Integer(), sa.ForeignKey('oil_card.id', name='oil_account_assignment_previous_card_id_fkey'), nullable=True))
    op.add_column('oil_account_assignment', sa.Column('change_kind', sa.String(16), nullable=False, server_default='assignment'))
    op.add_column('oil_account_assignment', sa.Column('request_id', sa.String(36), nullable=True))
    op.add_column('oil_account_assignment', sa.Column('request_fingerprint', sa.String(64), nullable=True))
    op.create_unique_constraint('uq_oil_assignment_request', 'oil_account_assignment', ['request_id'])
    op.create_check_constraint('ck_oil_assignment_kind', 'oil_account_assignment', "change_kind IN ('assignment', 'replacement')")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM oil_account_assignment WHERE change_kind = 'replacement'")):
        raise RuntimeError('Cannot remove replacement evidence while replacement events exist')
    op.drop_constraint('ck_oil_assignment_kind', 'oil_account_assignment', type_='check')
    op.drop_constraint('uq_oil_assignment_request', 'oil_account_assignment', type_='unique')
    op.drop_column('oil_account_assignment', 'request_fingerprint')
    op.drop_column('oil_account_assignment', 'request_id')
    op.drop_column('oil_account_assignment', 'change_kind')
    op.drop_constraint('oil_account_assignment_previous_card_id_fkey', 'oil_account_assignment', type_='foreignkey')
    op.drop_column('oil_account_assignment', 'previous_card_id')
