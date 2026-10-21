"""Persist per-account reversible operations and unsupported-operation boundaries."""
from alembic import op
import sqlalchemy as sa

revision = 'c384261021'
down_revision = 'c350261019'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('operation_history',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('actor', sa.String(128), nullable=False),
                    sa.Column('label', sa.String(128), nullable=False),
                    sa.Column('state', sa.String(16), nullable=False),
                    sa.Column('changes', sa.JSON(), nullable=False),
                    sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_operation_history_actor', 'operation_history', ['actor'])
    op.create_index('ix_operation_history_state', 'operation_history', ['state'])


def downgrade():
    op.drop_table('operation_history')
