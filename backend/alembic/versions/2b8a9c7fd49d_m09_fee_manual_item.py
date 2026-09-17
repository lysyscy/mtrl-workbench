"""M09 fee_manual_item

`MOD-09` 特殊费用月报表的**手填项**表（口径主人 = 《说明书》§5.5 · `DEV-R-04`）。
⚠️ 唯一自动项（安全文明施工费）**不落库** —— 它由库存单据明细现场派生（`mod09_fee.domain.auto_amount`）。
⚠️ 外键**已命名**（`fk_fee_manual_item_project`）—— autogenerate 默认生成**无名约束**（工程纪律）。

Revision ID: 2b8a9c7fd49d
Revises: d7541cbd2351
Create Date: 2026-09-17 07:50:46.060305

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b8a9c7fd49d'
down_revision: Union[str, Sequence[str], None] = 'd7541cbd2351'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('fee_manual_item',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('ym', sa.String(length=7), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('item_name', sa.String(length=128), nullable=False),
    sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'],
                            name='fk_fee_manual_item_project', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fee_manual_item_project_id'), 'fee_manual_item', ['project_id'], unique=False)
    op.create_index(op.f('ix_fee_manual_item_ym'), 'fee_manual_item', ['ym'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_fee_manual_item_ym'), table_name='fee_manual_item')
    op.drop_index(op.f('ix_fee_manual_item_project_id'), table_name='fee_manual_item')
    op.drop_table('fee_manual_item')
