"""m15 user theme（主题按用户隔离）

依据：`ACC-UI-THEME-001/001-06`「主题选择**按用户隔离**：A 与 B 各自的选择互不影响；
未设置时回落默认套」。⚠️ 这条一直列在基线的 **A 类「待实现方建断言」** 里，注明
「**属 M6 登录体系**」—— 没有"用户"就没有"A 与 B"⇒ **`m15` 片 3 一落地它就解锁了**。

⚠️ 语义：**空串 = 未设置** ⇒ 回落默认套。
   ⛔ 不在写入时补一个默认值 —— 那样"**没选过**"与"**选了默认套**"就分不出来了：
   前者应当**跟着以后改默认而变**，后者是用户的明确选择、**不该被改**。
⚠️ 加列可空？—— **不**：本列语义是"未设置 = 空串"（非 NULL），
   与 `password` / `deleted_by` 那几列同款（本表一贯用"空串 = 未设置"，⛔ 不混用 NULL）。
   所以带 `server_default=''`，已有行自然是"未设置" ✓

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-09-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('user_account',
                  sa.Column('theme', sa.String(length=32), server_default='', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_account', 'theme')
