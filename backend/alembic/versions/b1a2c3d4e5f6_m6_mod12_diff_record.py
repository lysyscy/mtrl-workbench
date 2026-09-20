"""M6 跨域 · MOD-12 差异登记建表（`diff_record`）

Revision ID: b1a2c3d4e5f6
Revises: cf8e4f1dc7ee
Create Date: 2026-09-20

⚠️ **只建表，不动任何既有表**（差异登记此前**从未有过载体** —— 无 Excel / 纸质 / 系统，
   《说明书》§5.8.3 的 `OPEN-03` 用户口述 2026-09-13 确认）⇒ 本迁移**没有数据搬迁**，
   是纯 `create_table`，**可安全 `downgrade`**。

⭐ 两处值得写下来的列设计：
· `seq` 与 `code` **分两列**：编号要"不撞既有行"，而本页**可以删行** ⇒ 序号取 `max(seq)+1`、
  删行不回退（拿"条数 + 1"会撞号）。`code` 唯一约束是**最后一道闸**。
· `owner` **独立成列**（虽然恒为「库存单据」）：让"它只能取这一个值"这件事在**数据里看得见**，
  ⛔ 而不是靠"反正没人写别的"（判据点 `ACC-DIF-REG-001/001-10`）。

## ⚠️⚠️ 2026-09-20 夜 · 用户裁定：`MOD-12` 差异登**撤页** ⇒ `diff_record` 已无使用方

依据：《说明书》§5.8.3 明写「**机制归属** ✅ **归属「库存单据」**（**不独立成模块**）」——
差异的**载体 = 调整单**（`m08`）、**产出 = 差异表**（`m06`，系统按调整单算），
不存在"另登一份差异"的地方。对应的 `app/mod12_diff/` 包与路由已删除，
`tests/test_wired_m12.py` 已删、判据 `ACC-DIF-REG-001` 已重写（12 条 → 4 条，全指真落点）。

⚠️ **本迁移与这张表都**保留**（⛔ 不删表、不补"删表"的反向迁移）**：
   · 删表要**再写一条迁移**，而它是**空表**、留着零成本；
   · ⚠️ 更重要的是：**迁移是历史** —— 改它等于改别人机器上「已执行」的记录（本仓铁律）。
   ⇒ 唯一后果 = 库里多一张**没人用的空表**，已在计划 §14.4d 的转向记录里登记。

⚠️ 假若**将来又要用**：先回读 §5.8.3 确认口径（它大概率仍写着"不独立成模块"），
   ⛔ 别因为"表还在"就顺手把这一页接回来。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b1a2c3d4e5f6"
down_revision = "cf8e4f1dc7ee"
branch_labels = None
depends_on = None

OWNER_INV = "库存单据"          # 与 `app/mod12_diff/domain.py::OWNER_INV` 同值（迁移里不 import 业务代码）


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_diff_record_status", table_name="diff_record")
    op.drop_index("ix_diff_record_month", table_name="diff_record")
    op.drop_index("ix_diff_record_code", table_name="diff_record")
    op.drop_index("ix_diff_record_seq", table_name="diff_record")
    op.drop_table("diff_record")
