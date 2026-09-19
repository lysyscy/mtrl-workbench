"""M5 切片 5 · 集采台账三张表（`jc_contract` / `jc_invoice` / `jc_payment`）

依据：《说明书》**§6.4.1**（合同主表 19 字段清单 —— 只落库其中 14 个，派生与自动算的不落）·
**§6.4.2**（发票子表：两张同款「发票日期 ＋ 金额」）· **§6.4.3**（付款子表：标明来源 ＋ 通知书 id）·
**§6.6.2**（付款引用**全库去重** ⇒ `uq_jc_payment_notice`）。
表与列的语义、以及"为什么不落库那 5 个字段"，见 `app/mod11_jc/models.py` 的模块 docstring。

⚠️ 三张表都是**新表**（`app/mod11_jc/` 此前只有 `__init__.py`）。
⚠️ 外键**全部命名**（迁移纪律：无名外键会让 `downgrade()` 必失败）。
⚠️ 新增索引一律 `ix_<表>_<列>`（沿用 alembic 默认命名，`op.f()` 包一层防手写漂移）。

Revision ID: b5f2c8d1a903
Revises: a8585df24750
Create Date: 2026-09-19 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5f2c8d1a903'
down_revision: Union[str, Sequence[str], None] = 'a8585df24750'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'jc_contract',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('contract_date', sa.String(length=10), nullable=False),
        sa.Column('material_name', sa.String(length=128), nullable=False),
        sa.Column('supplier', sa.String(length=128), nullable=False),
        sa.Column('contract_amt', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('trade_co', sa.String(length=128), nullable=True),
        sa.Column('trade_contract_amt', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('tag', sa.String(length=8), nullable=False),
        sa.Column('arch', sa.String(length=8), nullable=False),
        sa.Column('arch_no', sa.String(length=64), nullable=False),
        sa.Column('ret_date', sa.String(length=10), nullable=True),
        sa.Column('method', sa.String(length=64), nullable=False),
        sa.Column('remark', sa.String(length=255), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'],
                                name='fk_jc_contract_project', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_jc_contract_contract_date'), 'jc_contract', ['contract_date'], unique=False)
    op.create_index(op.f('ix_jc_contract_material_name'), 'jc_contract', ['material_name'], unique=False)
    op.create_index(op.f('ix_jc_contract_supplier'), 'jc_contract', ['supplier'], unique=False)
    op.create_index(op.f('ix_jc_contract_tag'), 'jc_contract', ['tag'], unique=False)
    op.create_index(op.f('ix_jc_contract_project_id'), 'jc_contract', ['project_id'], unique=False)

    op.create_table(
        'jc_invoice',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('contract_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=8), nullable=False),
        sa.Column('invoice_date', sa.String(length=10), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['contract_id'], ['jc_contract.id'],
                                name='fk_jc_invoice_contract', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_jc_invoice_contract_id'), 'jc_invoice', ['contract_id'], unique=False)
    op.create_index(op.f('ix_jc_invoice_kind'), 'jc_invoice', ['kind'], unique=False)

    op.create_table(
        'jc_payment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('contract_id', sa.Integer(), nullable=False),
        sa.Column('pay_date', sa.String(length=10), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('source', sa.String(length=8), nullable=False),
        sa.Column('notice_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['contract_id'], ['jc_contract.id'],
                                name='fk_jc_payment_contract', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['notice_id'], ['payment_notice.id'],
                                name='fk_jc_payment_notice', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        # ⭐ §6.6.2：同一笔通知书**全库只能被引用一次**（不分合同）
        sa.UniqueConstraint('notice_id', name='uq_jc_payment_notice'),
    )
    op.create_index(op.f('ix_jc_payment_contract_id'), 'jc_payment', ['contract_id'], unique=False)
    op.create_index(op.f('ix_jc_payment_source'), 'jc_payment', ['source'], unique=False)
    op.create_index(op.f('ix_jc_payment_notice_id'), 'jc_payment', ['notice_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_jc_payment_notice_id'), table_name='jc_payment')
    op.drop_index(op.f('ix_jc_payment_source'), table_name='jc_payment')
    op.drop_index(op.f('ix_jc_payment_contract_id'), table_name='jc_payment')
    op.drop_table('jc_payment')
    op.drop_index(op.f('ix_jc_invoice_kind'), table_name='jc_invoice')
    op.drop_index(op.f('ix_jc_invoice_contract_id'), table_name='jc_invoice')
    op.drop_table('jc_invoice')
    op.drop_index(op.f('ix_jc_contract_project_id'), table_name='jc_contract')
    op.drop_index(op.f('ix_jc_contract_tag'), table_name='jc_contract')
    op.drop_index(op.f('ix_jc_contract_supplier'), table_name='jc_contract')
    op.drop_index(op.f('ix_jc_contract_material_name'), table_name='jc_contract')
    op.drop_index(op.f('ix_jc_contract_contract_date'), table_name='jc_contract')
    op.drop_table('jc_contract')
