"""Split historical settlement supplements from cumulative payment reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = "c390261021"
down_revision = "c384261021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("opening_balance", sa.Column("entry_kind", sa.String(16), nullable=False, server_default="legacy"))
    op.add_column("opening_balance", sa.Column("paid_basis", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("opening_balance", sa.Column("settle_basis", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("opening_balance", sa.Column("input_mode", sa.String(8), nullable=False, server_default="paid"))
    connection = op.get_bind()
    old = connection.execute(sa.text("SELECT * FROM opening_balance ORDER BY id FOR UPDATE")).mappings().all()
    # Existing production records were individually confirmed as cumulative totals.
    for row in old:
        if row["category"] != "material":
            raise RuntimeError("机械费旧期初须先核对金额含义，不能自动转换")
        basis = connection.execute(sa.text("""
            SELECT COALESCE(sum(stat_paid), 0) FROM payment_notice
            WHERE ownership_id=:project_id AND category=:category AND excluded=false
              AND (COALESCE(doc_date, '')='' OR substring(doc_date, 1, 7)<=:cutoff_ym)
        """), dict(row)).scalar_one()
        connection.execute(sa.text("""
            INSERT INTO opening_balance
                (category, project_id, cutoff_ym, settle_amount, paid_amount, remark,
                 created_at, entry_kind, paid_basis, settle_basis, input_mode)
            VALUES (:category, :project_id, :cutoff_ym, 0, :paid_amount, :remark,
                    :created_at, 'payment', :basis, :settle_amount, 'paid')
        """), {**dict(row), "basis": basis})
        connection.execute(sa.text("""
            UPDATE opening_balance SET entry_kind='settlement', paid_amount=0 WHERE id=:id
        """), {"id": row["id"]})


def downgrade():
    raise RuntimeError("历史数据已拆分；回退请使用迁移前备份，避免把累计付款误当新增付款")
