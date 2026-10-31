"""Card archive state and reversible local invoice deletion."""
from alembic import op
import sqlalchemy as sa

revision = 'oil464261031'
down_revision = 'oil463261031'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('oil_card', sa.Column('status', sa.String(16), nullable=False, server_default='active'))
    op.create_check_constraint('ck_oil_card_status', 'oil_card', "status IN ('active', 'archived')")
    op.add_column('oil_invoice', sa.Column('deleted', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM oil_card WHERE status <> 'active')")) or \
            connection.scalar(sa.text('SELECT EXISTS(SELECT 1 FROM oil_invoice WHERE deleted)')):
        raise RuntimeError('Cannot discard card archive state or local invoice deletion')
    op.drop_column('oil_invoice', 'deleted')
    op.drop_constraint('ck_oil_card_status', 'oil_card', type_='check')
    op.drop_column('oil_card', 'status')
