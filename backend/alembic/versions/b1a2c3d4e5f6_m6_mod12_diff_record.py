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

⚠️⚠️ **2026-09-20 夜更新（同一件事拐了第二个弯）**：上面这段原本写的是
「**本迁移与这张表都保留**（空表、留着零成本）」—— ⭐ **用户当夜进一步明确裁定：把表 `drop` 掉**。
→ **已由新的一条迁移删除**（`c9e5f1a3b7d2`，文件名见同目录 —— **它才是"删表"的正确做法**）。
⭐ 本文件**只改注释、⛔ 不碰 `upgrade/downgrade`** —— 因为它**已经应用到两个库**，
   改它 = 改"已执行"的历史（本仓铁律）。
⚠️ 删表前已核：两库该表**行数都是 0**（零数据损失）、全仓**无业务代码引用它**。

⚠️ 假若**将来又要用**：先回读 §5.8.3 确认口径（它大概率仍写着"不独立成模块"）、
   并把 `tools/audit_common.py::CANCELLED` 里 `diff_record` 那条一并想清楚 ——
   ⛔ 别因为"表能建回来"就顺手把这一页接回来。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b1a2c3d4e5f6"
down_revision = "cf8e4f1dc7ee"
branch_labels = None
depends_on = None

#: ⚠️ 原注写「与 `app/mod12_diff/domain.py::OWNER_INV` 同值」—— 那个模块**已取消**
#:   （2026-09-20 用户裁定：`MOD-12` 差异登整页撤掉 ⇒ 见 `tools/audit_common.py::CANCELLED`）。
#: ⚠️ 本迁移**已应用到两个库** ⇒ **⛔ 不得修改它的 upgrade/downgrade**（改已应用的迁移是经典错误）；
#:   本行只改注释。⚠️ 表 `diff_record` 现状 = **保留但已作废、⛔ 不得再读写**
#:   （要不要 drop，待用户裁定 —— 见开发计划待裁定清单）。
OWNER_INV = "库存单据"          # 迁移里不 import 业务代码 ⇒ 值就地写死


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
