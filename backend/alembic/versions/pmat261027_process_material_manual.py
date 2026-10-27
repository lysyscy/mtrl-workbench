"""Historical process material cell overrides.

Revision ID: pmat261027
Revises: feeitem261027
"""
from alembic import op
import sqlalchemy as sa

revision = 'pmat261027'
down_revision = 'feeitem261027'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('proc_material_manual',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('warehouse_name', sa.String(128), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id', ondelete='SET NULL'), nullable=True),
        sa.Column('ym', sa.String(7), nullable=False),
        sa.Column('column_key', sa.String(64), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=True),
        sa.UniqueConstraint('warehouse_name', 'ym', 'column_key', name='uq_proc_material_cell'))
    op.create_index('ix_proc_material_manual_project_id', 'proc_material_manual', ['project_id'])


def downgrade():
    op.drop_table('proc_material_manual')
