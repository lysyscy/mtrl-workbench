"""m15 user credentials（密码列 · 本系统 ＋ i8）

⭐ **用户裁定（2026-09-20，原话「明文」）**：密码**明文存储**。理由与边界：
  - §1.5.1 明写密码「**无格式要求、可为空**（建号与改密同一规则）」—— 它**没有**要求任何强度；
  - 本系统是**科室内部 2 人**用的局域网工具（§1.5.1「账号数 2 人使用」）；
  - ⚠️ **i8 密码在技术上必须可逆**（要原样拿去登录 i8，见 `mod02_i8/login.py::_build_plain`）
    ⇒ 那一档**只能**是可逆存储 ⇒ "明文"是它唯一可行的一档；
  - 明文还使"管理员能读出密码告诉用户"成为可能 —— 这正是选它的理由。

⚠️ 三个新列**都带 `server_default=''`**（非空表加列必须给默认值，否则 upgrade 直接报错）。
⚠️⚠️ **账号名 / 密码一律 `Text`（不限长），⛔ 不是"给个大一点的 varchar"** ——
   §1.5.1 明写账号名「**不限制字符与长度**」、密码「**无长度限制**」，
   而 `varchar(N)` 是**一个真实的上限**（N 只是"你还没撞到而已"）。
   ⭐ 这条**不是我猜的，是断言当场抓出来的**：`001-06` 拿 300 字的密码去打，
      Postgres 直接报 `value too long for type character varying(255)`
      ⇒ 口径写"无限制"、实现却在**静默拒绝** —— 正是判据化要防的那类错。

⚠️ **本迁移是"补第二批"**：片 1 只做账号主体（⛔ 一个密码列都没加），因为当时
   **密码怎么存是没定的口径**；口径定下来后**新增一次迁移**，
   ⛔ **没去改** `d3f7a1c9b2e4`（它已经打到两个库了 —— 改已应用的迁移是经典错误）。

Revision ID: e5b8c2d4f6a1
Revises: d3f7a1c9b2e4
Create Date: 2026-09-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b8c2d4f6a1'
down_revision: Union[str, Sequence[str], None] = 'd3f7a1c9b2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ⚠️ 账号名 64 → **不限长**（§1.5.1「不限制字符与长度」）
    op.alter_column('user_account', 'account',
                    existing_type=sa.String(length=64),
                    type_=sa.Text(),
                    existing_nullable=False)
    # 本系统登录密码（**明文** · 可为空 · **无长度限制**）
    op.add_column('user_account',
                  sa.Column('password', sa.Text(), server_default='', nullable=False))
    # i8 凭证（§7.8：绑定到本系统账号、每人一份）· i8 密码**必须可逆**（⇒ 同样不限长）
    op.add_column('user_account',
                  sa.Column('i8_user', sa.String(length=64), server_default='', nullable=False))
    op.add_column('user_account',
                  sa.Column('i8_password', sa.Text(), server_default='', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_account', 'i8_password')
    op.drop_column('user_account', 'i8_user')
    op.drop_column('user_account', 'password')
    op.alter_column('user_account', 'account',
                    existing_type=sa.Text(),
                    type_=sa.String(length=64),
                    existing_nullable=False)
