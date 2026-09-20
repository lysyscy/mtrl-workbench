"""m15 last_login_at（最近登录）

⭐ **口径 2026-09-20 补**：原型的账号列表本来就有一列「最近登录」，而 §1.5.1 当时**没写**这条
   ⇒ 用户裁定「**最近登录口径加上**」。⚠️ 这是"**实现先有、口径后补**"的一处 ——
   记一笔，因为本仓常规是反过来的（先有口径、再落实现）。

⚠️ 语义要写死：`last_login_at` = **登录成功那一刻**写一次。
   ⛔ 不是"每次请求刷新" —— 那是**最后活动时间**，两者用途完全不同
   （登录时间能看出"谁长期没登录"，活动时间一刷新就变、看不出来）。
⚠️ 可空：**为空 = 从未登录过**（新号 / 建号后一直没登）。
   ⛔ 别拿 `created_at` 冒充它 —— 那是假话（"建号"与"登录过"是两件事）。

⚠️ 加列**可空、无 `server_default`**（可空列不需要默认值 ⇒ 不必给所有旧行编一个假时间）。
⚠️ 本迁移**不预置/不推算**任何历史值：**旧行一律留空**（如实 —— 我们确实不知道）。

Revision ID: f1a2b3c4d5e6
Revises: e5b8c2d4f6a1
Create Date: 2026-09-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5b8c2d4f6a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('user_account', sa.Column('last_login_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_account', 'last_login_at')
