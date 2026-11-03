"""Oil card and account archives, independent from accounting entries."""
from alembic import op
import sqlalchemy as sa

revision = 'oil453261031'
down_revision = 'mechauto261028'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('oil_card',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.String(36), nullable=False, unique=True),
        sa.Column('card_no', sa.String(128), nullable=True, unique=True),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('parent_card_id', sa.Integer(), sa.ForeignKey('oil_card.id'), nullable=True),
        sa.Column('remark', sa.Text(), nullable=False),
        sa.Column('version', sa.String(36), nullable=False),
        sa.Column('updated_by', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('primary', 'secondary')", name='ck_oil_card_kind'),
        sa.CheckConstraint("kind <> 'primary' OR parent_card_id IS NULL", name='ck_oil_card_primary_parent'),
        sa.CheckConstraint('parent_card_id IS NULL OR parent_card_id <> id', name='ck_oil_card_not_self'))
    op.create_index('ix_oil_card_parent_card_id', 'oil_card', ['parent_card_id'])
    op.create_table('oil_account',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.String(36), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id'), nullable=False),
        sa.Column('card_id', sa.Integer(), sa.ForeignKey('oil_card.id'), nullable=True),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('remark', sa.Text(), nullable=False),
        sa.Column('version', sa.String(36), nullable=False),
        sa.Column('updated_by', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name='ck_oil_account_status'))
    op.create_index('ix_oil_account_project_id', 'oil_account', ['project_id'])
    op.create_index('ix_oil_account_card_id', 'oil_account', ['card_id'])
    op.create_table('oil_account_assignment',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('oil_account.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id'), nullable=False),
        sa.Column('card_id', sa.Integer(), sa.ForeignKey('oil_card.id'), nullable=True),
        sa.Column('changed_by', sa.Text(), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=False))
    for field in ('account_id', 'project_id', 'card_id'):
        op.create_index(f'ix_oil_account_assignment_{field}', 'oil_account_assignment', [field])


def downgrade():
    op.drop_table('oil_account_assignment')
    op.drop_table('oil_account')
    op.drop_table('oil_card')
