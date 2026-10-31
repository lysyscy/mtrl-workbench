"""Invoice corrections, historical number identities and local credit/void state."""
from alembic import op
import sqlalchemy as sa

revision = 'oil460261031'
down_revision = 'oil458261031'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ck_oil_invoice_status', 'oil_invoice', type_='check')
    op.create_check_constraint('ck_oil_invoice_status', 'oil_invoice', "status IN ('pending', 'registered', 'voided')")
    op.add_column('oil_invoice', sa.Column('kind', sa.String(16), nullable=False, server_default='normal'))
    op.add_column('oil_invoice', sa.Column('related_invoice_id', sa.Integer(), sa.ForeignKey('oil_invoice.id'), nullable=True))
    op.create_index('ix_oil_invoice_related_invoice_id', 'oil_invoice', ['related_invoice_id'])
    op.add_column('oil_invoice', sa.Column('review_json', sa.Text(), nullable=False, server_default='{}'))
    op.add_column('oil_invoice', sa.Column('change_note', sa.Text(), nullable=False, server_default=''))
    op.add_column('oil_invoice', sa.Column('void_date', sa.Date(), nullable=True))
    op.create_check_constraint('ck_oil_invoice_kind', 'oil_invoice', "kind IN ('normal', 'credit')")
    op.create_table('oil_invoice_number', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('oil_invoice.id'), nullable=False),
        sa.Column('number', sa.String(32), unique=True, nullable=False))
    op.create_index('ix_oil_invoice_number_invoice_id', 'oil_invoice_number', ['invoice_id'])
    op.execute("INSERT INTO oil_invoice_number(invoice_id, number) SELECT id, invoice_no FROM oil_invoice WHERE invoice_no IS NOT NULL")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM oil_invoice WHERE kind <> 'normal' OR status='voided' OR review_json <> '{}' OR change_note <> ''")):
        raise RuntimeError('Cannot remove confirmed invoice correction evidence')
    op.drop_table('oil_invoice_number')
    op.drop_constraint('ck_oil_invoice_kind', 'oil_invoice', type_='check')
    for column in ('void_date', 'change_note', 'review_json', 'related_invoice_id', 'kind'):
        op.drop_column('oil_invoice', column)
    op.drop_constraint('ck_oil_invoice_status', 'oil_invoice', type_='check')
    op.create_check_constraint('ck_oil_invoice_status', 'oil_invoice', "status IN ('pending', 'registered')")
