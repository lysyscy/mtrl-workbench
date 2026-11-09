"""油卡发票手工登记及历史日期依据。"""
from alembic import op
import sqlalchemy as sa

revision = 'oil474261109'
down_revision = 'oilmerge261103'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('oil_invoice', sa.Column('manual_request_id', sa.String(36), nullable=True))
    op.add_column('oil_invoice', sa.Column('manual_date_text', sa.Text(), nullable=True))
    op.add_column('oil_invoice', sa.Column('manual_cutoff_ym', sa.String(7), nullable=True))
    op.create_unique_constraint('uq_oil_invoice_manual_request_id', 'oil_invoice', ['manual_request_id'])


def downgrade():
    op.drop_constraint('uq_oil_invoice_manual_request_id', 'oil_invoice', type_='unique')
    op.drop_column('oil_invoice', 'manual_cutoff_ym')
    op.drop_column('oil_invoice', 'manual_date_text')
    op.drop_column('oil_invoice', 'manual_request_id')
