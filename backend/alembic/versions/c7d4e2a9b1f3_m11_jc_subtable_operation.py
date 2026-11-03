"""m11_jc 子表操作回执（局部可靠保存 / 恢复）

Revision ID: c7d4e2a9b1f3
Revises: mechauto261028

⭐ **为什么只加这一张表**：集采子表（发票 / 付款）的增删原先**没有稳定操作标识** ⇒ 页面刷新后
   浏览器只知道"这次可能没存成功"，服务端却说不出"那一次到底成了没有" ⇒ 只能逼用户
   「重读明细 → 自行比对 → 已核对」才能恢复。用户明确不要这个流程（2026-11-03）。
   ⇒ 给四个子表写口加**可选** `request_id`，用它落一张**轻量回执**：
   带标识的重复请求回放原回执（⛔ 不重复产生 / 删除事实）；同标识换动作 / 换参数 ⇒ 明确拒绝。
⚠️ 回执**只增不删**：删行之后重复请求仍要能拿到"已删除" ⇒ 它不能是业务行的从属列。
⚠️ 回执**不进** `history_bindings` 白名单（不参与撤销）⇒ 撤销语义不受影响。
⚠️ 迁移纪律：**只加代码文件、⛔ 不升级生产库**（本次任务范围）；打到已核专用测试库用于断言；
   `down_revision` 取自 `alembic heads` 的唯一 head（= `mechauto261028`）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c7d4e2a9b1f3'
down_revision: Union[str, Sequence[str], None] = 'mechauto261028'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新建 `jc_subtable_operation`（子表操作回执 · 幂等键 = `request_id`）。"""
    op.create_table(
        'jc_subtable_operation',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('request_id', sa.String(length=160), nullable=False),
        sa.Column('account', sa.String(length=128), nullable=False),
        sa.Column('action', sa.String(length=16), nullable=False),
        sa.Column('contract_id', sa.Integer(), nullable=False),
        sa.Column('row_id', sa.Integer(), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        # ⚠️ `contract_id` / `row_id` **刻意不设外键** —— 回执要活过业务行被删（删行重放仍要回"已删除"）；
        #    真设了 `CASCADE`，删子表行会把回执一起带走，那正是这张表要避免的静默丢失。
    )
    # ⭐ `request_id` 唯一 —— "同一次操作只有一个事实"的数据库侧兜底（服务层另有 advisory lock 串行化）。
    op.create_index(op.f('ix_jc_subtable_operation_request_id'),
                    'jc_subtable_operation', ['request_id'], unique=True)
    op.create_index(op.f('ix_jc_subtable_operation_action'),
                    'jc_subtable_operation', ['action'], unique=False)


def downgrade() -> None:
    """退回：删这张回执表（⛔ 回执随之丢失 —— 退回前先确认没有前端还押着未完成的标识）。"""
    op.drop_index(op.f('ix_jc_subtable_operation_action'), table_name='jc_subtable_operation')
    op.drop_index(op.f('ix_jc_subtable_operation_request_id'), table_name='jc_subtable_operation')
    op.drop_table('jc_subtable_operation')
