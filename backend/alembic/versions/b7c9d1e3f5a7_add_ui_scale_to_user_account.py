"""add ui_scale to user_account —— **按用户**的「界面大小」档位

## 为什么加（`TAIL-129` · 用户 2026-09-27 走查）

用户原话：「只有一个**界面字号及界面大小**这个值得做，其他的暂时用处不大」
⇒ 设计方案比过三套（整体 `zoom` / **字号＋行距走 CSS 变量** / 全量 px→rem），
用户选了**方案 B**（`设计-界面大小` 结论记在计划 §15 `TAIL-129`）。

⚠️ 为什么它必须**落库、按用户存**（⛔ 不是 `localStorage`）：本仓的界面偏好一律按用户存
   （`theme` 就是先例），且判据要的是「**A 选了"更大"不妨碍 B 保持标准**」——
   存浏览器就做不到（换个浏览器/清缓存即丢，也不区分"谁的账号"）。

## 本迁移只做一件事

给 `user_account` 加 `ui_scale`（`varchar(16) NOT NULL DEFAULT ''`）—— ⭐ **存档位键**
（`standard` / `large` / `larger` / `largest`），⛔ **不存倍率**：倍率是显示口径，
哪天想调档位不该动历史数据；键↔倍率的映射只有一处真源 = `mod15_user.domain.UI_SCALES`。

⚠️ **非空表加非空列必须给 `server_default`**（否则对已有行直接报错）—— 给空串 =
   "未设置" ⇒ 回落标准档（`effective_ui_scale` 判），与 `theme` 的空串语义**同款**。
⚠️ 模型那侧（`models.UserAccount.ui_scale`）**同批声明了 `server_default=""`** ——
   ⛔ 只加库不加模型 ⇒ `alembic check` 会报 `modify_server_default`（`TAIL-102` 那次就是这么红的）。
⚠️ **不预置、不回填**：谁也没设过 ⇒ 全员标准档（⛔ 不编一个"看起来合理"的默认给别人）。

⚠️ 版本链：本迁移接**当时的真 head** `f3a7c1e5b9d2`。
⚠️ **两个库都要到 head**（开发库 ＋ `.env` 的 `TEST_DATABASE_URL`）—— 漏一个 ⇒
   `test_schema_drift.py`（元数据与测试库 0 差异）会红，那是**对的**。

Revision ID: b7c9d1e3f5a7
Revises: f3a7c1e5b9d2
Create Date: 2026-09-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7c9d1e3f5a7'
down_revision: Union[str, Sequence[str], None] = 'f3a7c1e5b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """加「界面大小档位」列（`varchar(16) NOT NULL DEFAULT ''`；空串 = 未设置 ⇒ 标准档）。"""
    op.add_column(
        "user_account",
        sa.Column("ui_scale", sa.String(length=16), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """真反演：删掉这一列。

    ⚠️ **会丢掉每个人选过的界面大小**（都回到标准档）—— 这是可接受的：
       它是个**显示偏好**，不是业务数据（与 `theme` 同性质）。
    """
    op.drop_column("user_account", "ui_scale")
