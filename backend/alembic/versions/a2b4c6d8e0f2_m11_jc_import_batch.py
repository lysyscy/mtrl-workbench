"""m11_jc 导入批次与回滚点（`TAIL-98`）

Revision ID: a2b4c6d8e0f2
Revises: e1a2b3c4d5e7

⭐ **为什么要有这两张表**：集采导入的落库口径是「按**合同价锚点**匹配 ⇒ **更新已有行**」
   ⇒ 导错了只能一列列手工改回去（付款计划 / 过程资料都有整批回滚，集采没有）。
   ⇒ 一次导入 = 一个**批次**（`jc_import_batch`）＋ **逐行的「改前/改后」回滚点**（`jc_import_undo`）。
⚠️ 迁移纪律：**打到两个库**（`TEST_DATABASE_URL` 给断言 ＋ `DATABASE_URL` 给真机）·
   外键**命名**（⛔ 无名约束会让 `downgrade()` 必失败）· `down_revision` 由 `alembic heads` 取（= `e1a2b3c4d5e7`）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a2b4c6d8e0f2'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4d5e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新建 `jc_import_batch`（批次）＋ `jc_import_undo`（回滚点）。"""
    op.create_table(
        'jc_import_batch',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('batch_no', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('project_key', sa.String(length=128), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('operator', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], name='fk_jc_import_batch_project',
                                ondelete='SET NULL'),
    )
    op.create_index(op.f('ix_jc_import_batch_batch_no'), 'jc_import_batch', ['batch_no'], unique=True)
    op.create_index(op.f('ix_jc_import_batch_project_id'), 'jc_import_batch', ['project_id'], unique=False)
    op.create_index(op.f('ix_jc_import_batch_status'), 'jc_import_batch', ['status'], unique=False)

    op.create_table(
        'jc_import_undo',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('batch_no', sa.String(length=64), nullable=False),
        sa.Column('contract_id', sa.Integer(), nullable=False),
        sa.Column('before_json', sa.Text(), nullable=False),
        sa.Column('after_json', sa.Text(), nullable=False),
        sa.Column('invoice_ids', sa.Text(), nullable=False),
        sa.Column('at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        # ⚠️ `contract_id` **刻意不设外键** —— 见 `models.JcImportUndo` 的注释：合同万一没了，
        #    回滚点要**留下来**才能把它报出来（`CASCADE` 会让它静默消失）。
    )
    op.create_index(op.f('ix_jc_import_undo_batch_no'), 'jc_import_undo', ['batch_no'], unique=False)
    op.create_index(op.f('ix_jc_import_undo_contract_id'), 'jc_import_undo', ['contract_id'], unique=False)


def downgrade() -> None:
    """退回：删两张表（⛔ 批次与回滚点随之丢失 —— 退回前先核"有没有还没回滚的批次"）。"""
    op.drop_index(op.f('ix_jc_import_undo_contract_id'), table_name='jc_import_undo')
    op.drop_index(op.f('ix_jc_import_undo_batch_no'), table_name='jc_import_undo')
    op.drop_table('jc_import_undo')
    op.drop_index(op.f('ix_jc_import_batch_status'), table_name='jc_import_batch')
    op.drop_index(op.f('ix_jc_import_batch_project_id'), table_name='jc_import_batch')
    op.drop_index(op.f('ix_jc_import_batch_batch_no'), table_name='jc_import_batch')
    op.drop_table('jc_import_batch')
