"""Track ordinary invoice deletions separately from legacy data."""
import sqlalchemy as sa
from alembic import op

revision = 'oillife261119'
down_revision = 'jcrules261112'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('oil_invoice_retirement',
        sa.Column('invoice_id', sa.Integer(), primary_key=True),
        sa.Column('operation_id', sa.Integer(), nullable=False))
    op.add_column('oil_delivery_item', sa.Column('deleted_version', sa.String(36), nullable=True))


def downgrade():
    op.drop_column('oil_delivery_item', 'deleted_version')
    op.drop_table('oil_invoice_retirement')
