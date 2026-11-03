"""Immutable first-continuation manifest and explicit confirmation receipts."""
from alembic import op
import sqlalchemy as sa

revision = 'oil463261031'
down_revision = 'oil462261031'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('oil_continuation_source',
        sa.Column('source_id', sa.String(128), primary_key=True),
        sa.Column('fingerprint', sa.String(64), nullable=False, unique=True),
        sa.Column('manifest_json', sa.Text(), nullable=False),
        sa.Column('confirmations_json', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM oil_continuation_source')):
        raise RuntimeError('Cannot remove first-continuation evidence')
    op.drop_table('oil_continuation_source')
