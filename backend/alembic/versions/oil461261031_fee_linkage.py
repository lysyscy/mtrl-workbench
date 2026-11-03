"""Explicit fee linkage identity and independent monthly oil customs."""
from alembic import op
import sqlalchemy as sa

revision = 'oil461261031'
down_revision = 'oil459261031'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('oil_fee_custom', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id'), nullable=False),
        sa.Column('ym', sa.String(7), nullable=False), sa.Column('amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('remark', sa.Text(), nullable=False), sa.Column('version', sa.String(36), nullable=False),
        sa.Column('updated_by', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('project_id', 'ym', name='uq_oil_fee_custom_month'))
    op.create_index('ix_oil_fee_custom_project_id', 'oil_fee_custom', ['project_id'])
    op.create_index('ix_oil_fee_custom_ym', 'oil_fee_custom', ['ym'])
    op.create_table('fee_oil_binding', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id'), nullable=False, unique=True),
        sa.Column('fee_item_id', sa.Integer(), sa.ForeignKey('fee_item.id'), nullable=True, unique=True),
        sa.Column('reviewed_json', sa.Text(), nullable=False), sa.Column('source_note', sa.Text(), nullable=False),
        sa.Column('enabled_by', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False))


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM fee_oil_binding')) or op.get_bind().scalar(sa.text('SELECT count(*) FROM oil_fee_custom')):
        raise RuntimeError('Cannot remove oil linkage review evidence or custom amounts')
    op.drop_table('fee_oil_binding')
    op.drop_table('oil_fee_custom')
