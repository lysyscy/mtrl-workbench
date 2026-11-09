"""油卡档案共享排序及账务本地删除。"""
from alembic import op
import sqlalchemy as sa

revision = 'oilpolish261109'
down_revision = 'oil474261109'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('oil_card', 'oil_account'):
        op.add_column(table, sa.Column('display_order', sa.Integer(), server_default='0', nullable=False))
    op.add_column('oil_entry', sa.Column('deleted', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM oil_entry WHERE deleted LIMIT 1')).scalar():
        raise RuntimeError('已有删除的油卡账务，降级会使记录重新计账。请先按已核备份恢复。')
    op.drop_column('oil_entry', 'deleted')
    for table in ('oil_account', 'oil_card'):
        op.drop_column(table, 'display_order')
