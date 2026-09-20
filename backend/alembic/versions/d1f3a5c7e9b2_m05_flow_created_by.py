"""MOD-05 · 付款流水补「操作人」（`payment_flow.created_by`）

Revision ID: d1f3a5c7e9b2
Revises: c9e5f1a3b7d2
Create Date: 2026-09-20

## ⭐ 为什么加这一列（不是"顺手补"，是**界面在说谎**）

- `V.m05`「付款流水」表的表头 `FL_THEAD` 里**有一列「操作人」**；
- ⚠️ 而 `PaymentFlow` **根本没有操作人字段** ⇒ `core.js::adaptFlow` 只好拿
  **`created_at`（创建时间）**顶上（`op: x.created_at`）⇒ ⭐ **那一列显示的是时间**。
- ⚠️ 而壳 `index.html` 自己就写着口径：「**付款流水操作人**、调整单操作人、
  留痕「改前人」**统一取当前登录用户**」（§1.5.1 末行）⇒ **明写了要有，只是这张表漏了**。

## ⭐ 为什么是"一张表的事"（不是"一类问题"）

⭐ 用户 2026-09-20 要"分析和最优方案" ⇒ 我做了一次**全仓盘点**，判据是：

> ⭐ **「壳里给用户看的那一列，后端必须真有那个字段」**
> （⛔ 不是"给所有表都加 `created_by`" —— 那会加一堆**没人看的列**）

逐处核完（壳里带「操作人 / 录入人 / 改前人」的地方**全部**）：
- ✅ 付款通知书「录入人」⇒ `PaymentNotice.input_by` **有**
- ✅ 调整单「操作人」⇒ `InvAdjustment.operator` **有**
- ✅ 留痕「改前人」⇒ `ProjectFieldLog` / `NoticeStatLog` / `FlowRevokeLog` 的 `changed_by` **有**
- ⚠️ **付款流水「操作人」⇒ 只有这一处没有** ← 本迁移

⇒ ⭐ 所以**没单开一条尾巴**，直接并进 `MOD-05` 导出这一批做 ✓

## ⚠️ 老行怎么办

`server_default=''` ＋ 非空 ⇒ 老行留**空串**：**如实表示"当时没记这个人"**，
⛔ **不编一个名字**进去（编了就是往历史里塞假数据 —— 本项目最忌的一类）。
⭐ 界面上该列的老行会显示空 —— 那是**对的**（对比"显示一个时间"）。

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1f3a5c7e9b2'
down_revision: Union[str, Sequence[str], None] = 'c9e5f1a3b7d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """加「操作人」列（`server_default=''` —— 非空表加列必须给默认值，否则 upgrade 直接报错）。"""
    op.add_column(
        "payment_flow",
        sa.Column("created_by", sa.String(length=64), server_default="", nullable=False),
    )


def downgrade() -> None:
    """真反演：把列删掉。"""
    op.drop_column("payment_flow", "created_by")
