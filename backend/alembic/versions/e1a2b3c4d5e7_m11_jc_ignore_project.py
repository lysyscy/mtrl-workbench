"""m11_jc 剔除名单表（`TAIL-96`）

Revision ID: e1a2b3c4d5e7
Revises: d1f3a5c7e9b2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e1a2b3c4d5e7'
down_revision: Union[str, Sequence[str], None] = 'd1f3a5c7e9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新建 `jc_ignore_project`（集采剔除名单）。"""
    op.create_table(
        'jc_ignore_project',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name_full', sa.String(length=512), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('operator', sa.String(length=64), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_jc_ignore_project_name_full'), 'jc_ignore_project', ['name_full'], unique=False)
    op.create_index(op.f('ix_jc_ignore_project_active'), 'jc_ignore_project', ['active'], unique=False)


def downgrade() -> None:
    """退回：删表（⛔ 名单内容随之丢失 —— 退回前先导出）。"""
    op.drop_index(op.f('ix_jc_ignore_project_active'), table_name='jc_ignore_project')
    op.drop_index(op.f('ix_jc_ignore_project_name_full'), table_name='jc_ignore_project')
    op.drop_table('jc_ignore_project')
