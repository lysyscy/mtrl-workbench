"""Separate import cutoffs and preserve formerly displayed mechanical values."""
from datetime import datetime
from decimal import Decimal

from alembic import op
import sqlalchemy as sa

revision = "c262263d2609"
down_revision = "b7c9d1e3f5a7"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("proc_cutoff", "proc_history_batch"):
        op.add_column(table, sa.Column("mechanical_cutoff_ym", sa.String(7), nullable=False, server_default=""))
        op.execute(sa.text(f"UPDATE {table} SET mechanical_cutoff_ym = cutoff_ym"))
    op.add_column("proc_mech_manual", sa.Column("source_batches", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("proc_history_snapshot", sa.Column("material_present", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("proc_mech_import_change",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_no", sa.String(64), nullable=False),
        sa.Column("warehouse_name", sa.String(128), nullable=False),
        sa.Column("ym", sa.String(7), nullable=False),
        sa.Column("column_key", sa.String(16), nullable=False),
        sa.Column("before_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("before_batch", sa.String(64), nullable=False))
    op.create_index("ix_proc_mech_import_change_batch_no", "proc_mech_import_change", ["batch_no"])
    migrate_displayed_mechanics(op.get_bind())


def migrate_displayed_mechanics(connection):
    """Old history segment read active snapshots, regardless of conflicting manual values."""
    meta = sa.MetaData()
    manual = sa.Table("proc_mech_manual", meta, autoload_with=connection)
    history = sa.Table("proc_history_snapshot", meta, autoload_with=connection)
    batch = sa.Table("proc_history_batch", meta, autoload_with=connection)
    cutoff = sa.Table("proc_cutoff", meta, autoload_with=connection)
    limits = {r.warehouse_name: r.cutoff_ym for r in connection.execute(sa.select(cutoff))}
    active = {r.batch_no for r in connection.execute(sa.select(batch)) if r.status == "active"}
    grouped = {}
    for row in connection.execute(sa.select(history)).mappings():
        if row["batch_no"] not in active or row["ym"] > limits.get(row["warehouse_name"], ""):
            continue
        key = (row["warehouse_name"], row["ym"])
        values = grouped.setdefault(key, {f"mech_{i}": Decimal("0.00") for i in range(6)})
        for i in range(6):
            values[f"mech_{i}"] += row[f"mech_{i}"] or Decimal("0.00")
    for (warehouse, ym), values in grouped.items():
        existing = connection.execute(sa.select(manual.c.id).where(
            manual.c.warehouse_name == warehouse, manual.c.ym == ym)).scalar_one_or_none()
        payload = {**values, "source_batches": {}, "updated_at": datetime.now()}
        if existing is not None:
            connection.execute(manual.update().where(manual.c.id == existing).values(**payload))
        else:
            connection.execute(manual.insert().values(warehouse_name=warehouse, ym=ym,
                                                       project_id=None, **payload))


def downgrade():
    op.drop_index("ix_proc_mech_import_change_batch_no", table_name="proc_mech_import_change")
    op.drop_table("proc_mech_import_change")
    op.drop_column("proc_history_snapshot", "material_present")
    op.drop_column("proc_mech_manual", "source_batches")
    for table in ("proc_history_batch", "proc_cutoff"):
        op.drop_column(table, "mechanical_cutoff_ym")
