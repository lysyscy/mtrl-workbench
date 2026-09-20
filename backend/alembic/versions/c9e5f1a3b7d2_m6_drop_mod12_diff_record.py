"""M6 跨域 · **撤** MOD-12 差异登记表（`diff_record`）

Revision ID: c9e5f1a3b7d2
Revises: a7b8c9d0e1f2
Create Date: 2026-09-20

## ⭐ 为什么是**新写一条**、而不是改 `b1a2c3d4e5f6`

`b1a2c3d4e5f6`（建表那条）**已经应用到两个库**了 ⇒ ⛔ **改它等于改"已执行"的历史**
（本仓铁律：已应用的迁移只加注释、不动 `upgrade/downgrade`）。
⇒ ⭐ **撤一张表 = 再写一条迁移**，这就是迁移链的正确用法。

## ⚠️ 来龙去脉（同一天内拐了两个弯，记清楚免得下次又翻）

1. `MOD-12`「差异登记」独立成页 —— ⚠️ **后来查明是 AI 擅自加的**，用户 2026-09-20 裁定**撤页**
   （依据 §5.8.3「差异归属恒为「**库存单据**」（**不独立成模块**）」）。
2. 同日稍早的处置是「**表保留但作废**」（理由：空表、留着零成本；且"不改历史"）。
3. ⭐ **2026-09-20 夜 · 用户明确裁定：`drop` 掉** ⇒ 本迁移执行。

## ⚠️ 前置核对（本迁移开跑前已做）

- **两库 `diff_record` 行数都是 0** ⇒ 删表**零数据损失** ✓
- **全仓无任何业务代码引用 `diff_record` / `DiffRecord`**（只有 `b1a2c3d4e5f6` 自己）
  ⇒ ⛔ 不会删出"线上报错" ✓

## ⭐ `downgrade()` 是真反演

按 `b1a2c3d4e5f6` 的原定义**原样建回**（含 4 个索引与唯一约束）——
所以这条迁移**可回滚**，⛔ 不是"单向删除"。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e5f1a3b7d2'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: 与 `b1a2c3d4e5f6` 同值（迁移里不 import 业务代码 ⇒ 就地写死）
OWNER_INV = "库存单据"


def upgrade() -> None:
    """撤表（含它自带的 4 个索引）。"""
    op.drop_index("ix_diff_record_status", table_name="diff_record")
    op.drop_index("ix_diff_record_month", table_name="diff_record")
    op.drop_index("ix_diff_record_code", table_name="diff_record")
    op.drop_index("ix_diff_record_seq", table_name="diff_record")
    op.drop_table("diff_record")


def downgrade() -> None:
    """**真反演**：按 `b1a2c3d4e5f6` 的原定义把表和索引建回来。"""
    op.create_table(
        "diff_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("owner", sa.String(length=16), nullable=False, server_default=OWNER_INV),
        sa.Column("project_name", sa.String(length=256), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("remark", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_diff_record_code"),
    )
    op.create_index("ix_diff_record_seq", "diff_record", ["seq"], unique=False)
    op.create_index("ix_diff_record_code", "diff_record", ["code"], unique=False)
    op.create_index("ix_diff_record_month", "diff_record", ["month"], unique=False)
    op.create_index("ix_diff_record_status", "diff_record", ["status"], unique=False)
