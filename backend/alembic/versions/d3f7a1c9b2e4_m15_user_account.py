"""m15 user_account

`MOD-15` 用户管理的**账号主体**表（《说明书》§1.5.1 ＋ §7.5）。

⚠️ 全部 NOT NULL 列**都带 `server_default`**（迁移约定：否则非空表 upgrade 直接报错）。
⚠️ `account` 上的唯一约束 **不过滤软删行** —— §1.5.1 说删除 = **软删除、账号名保留**
   （历史留痕里的人名要认得出来、必要时可恢复）⇒ 那个名字**还在占用**，
   ⛔ 别"顺手"改成部分唯一索引（那样"恢复"时会撞名）。
⚠️ **预置 1 行**：系统**首个管理员** —— 不预置就没人能登录、也没人能建号（**死锁**）。
   ⛔ 不预置"第二个人"：§1.5.1 说「2 人使用」是**使用现状**、同时说账号「可增删（数量不写死）」,
   第二个账号由用户在页面上自建；⛔ 也**不把业务人名写进迁移**（那是第二份真相）。
⚠️ **本表不含任何密码列** —— §1.5.1 只说密码「无格式要求、可为空」（对输入的要求），
   **没说存储方式**；而 §7.8 又要求账号要装 i8 的账号与密码（i8 密码**必须可逆**）⇒ 属口径待定。
   按「口径没定就不动实现」先把主体做完，密码列等口径定下来**再补一次迁移**。

⚠️⚠️ **`down_revision` 必须接"真 head"，⛔ 别自己拿正则去手算**：本仓曾有 26 个迁移文件，
   我第一版按 `down_revision` 字段扫出来的 head 是 `cf8e4f1dc7ee` —— **漏了一个**
   （`b1a2c3d4e5f6` = `MOD-12` 差异登记建表，它的 `down_revision` 写法没被我那条正则吃到）
   ⇒ 结果**分了叉、两个 head**，`alembic upgrade head` 当场报 `Multiple head revisions`。
   ⇒ ⭐ 正确做法：用 **alembic 自己的 API** 算（`ScriptDirectory.from_config(cfg).get_heads()`），
     或直接 `alembic heads`。**别用文本正则去推断迁移图。**

Revision ID: d3f7a1c9b2e4
Revises: b1a2c3d4e5f6
Create Date: 2026-09-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3f7a1c9b2e4'
down_revision: Union[str, Sequence[str], None] = 'b1a2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: 预置的首个管理员（与 `mod15_user.repository.SEED_ACCOUNT / SEED_NAME` 一致）
_SEED = ("admin", "管理员", "admin", "在用")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'user_account',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account', sa.String(length=64), server_default='', nullable=False),
        sa.Column('name', sa.String(length=64), server_default='', nullable=False),
        sa.Column('role', sa.String(length=16), server_default='user', nullable=False),
        sa.Column('status', sa.String(length=16), server_default='在用', nullable=False),
        # 软删：非空 = 已删除（§1.5.1「删除 = 软删除，账号名保留…必要时可恢复」）
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.String(length=64), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        # ⚠️ 唯一约束**不过滤软删**（见模块头）—— 别改成 partial index
        sa.UniqueConstraint('account', name='uq_user_account'),
    )
    # 预置系统首个管理员（⛔ 不预置就没人能建号 —— 死锁）
    op.execute(
        sa.text(
            "INSERT INTO user_account (account, name, role, status, deleted_by, created_at, updated_at) "
            "VALUES (:a, :n, :r, :s, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ).bindparams(a=_SEED[0], n=_SEED[1], r=_SEED[2], s=_SEED[3])
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('user_account')
