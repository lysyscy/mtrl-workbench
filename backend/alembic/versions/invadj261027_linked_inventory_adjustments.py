"""Extend inventory adjustments without changing any imported source row."""
from alembic import op
import sqlalchemy as sa

revision = 'invadj261027'
down_revision = 'pmat261027'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('inv_adjustment', sa.Column('overrides', sa.JSON(), nullable=True))
    op.add_column('inv_adjustment', sa.Column('before_values', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('inv_adjustment', 'before_values')
    op.drop_column('inv_adjustment', 'overrides')
