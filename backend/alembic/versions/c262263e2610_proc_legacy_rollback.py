"""Attach rollback ownership to legacy mechanics without changing effective amounts.

Follow-up for c262263d2609, applied before any new production mechanical writes.
Only unchanged, unowned legacy-derived records are eligible.
"""
from decimal import Decimal

from alembic import op
import sqlalchemy as sa

revision = "c262263e2610"
down_revision = "c262263d2609"
branch_labels = None
depends_on = None


def attach_legacy_rollback(connection):
    meta = sa.MetaData()
    manual = sa.Table("proc_mech_manual", meta, autoload_with=connection)
    history = sa.Table("proc_history_snapshot", meta, autoload_with=connection)
    batches = sa.Table("proc_history_batch", meta, autoload_with=connection)
    changes = sa.Table("proc_mech_import_change", meta, autoload_with=connection)
    cutoff = sa.Table("proc_cutoff", meta, autoload_with=connection)
    limits = {r.warehouse_name: r.cutoff_ym for r in connection.execute(sa.select(cutoff))}
    active = {r.batch_no: r for r in connection.execute(sa.select(batches)) if r.status == "active"}
    grouped = {}
    for row in connection.execute(sa.select(history)).mappings():
        if row["batch_no"] not in active or row["ym"] > limits.get(row["warehouse_name"], ""):
            continue
        key = (row["warehouse_name"], row["ym"])
        by_batch = grouped.setdefault(key, {})
        values = by_batch.setdefault(row["batch_no"], {f"mech_{i}": Decimal("0.00") for i in range(6)})
        for column in values:
            values[column] += row[column] or Decimal("0.00")
    existing_changes = {(r.warehouse_name, r.ym) for r in connection.execute(sa.select(changes))}
    for row in connection.execute(sa.select(manual)).mappings():
        key = (row["warehouse_name"], row["ym"])
        if row["source_batches"] or key in existing_changes or key not in grouped:
            continue
        by_batch = grouped[key]
        combined = {f"mech_{i}": sum((values[f"mech_{i}"] for values in by_batch.values()), Decimal("0.00"))
                    for i in range(6)}
        if any(row[column] != amount for column, amount in combined.items()):
            continue
        previous = {f"mech_{i}": Decimal("0.00") for i in range(6)}
        owner = ""
        for batch_no in sorted(by_batch, key=lambda b: active[b].id):
            for column, amount in by_batch[batch_no].items():
                connection.execute(changes.insert().values(batch_no=batch_no,
                    warehouse_name=row["warehouse_name"], ym=row["ym"], column_key=column,
                    before_amount=previous[column], before_batch=owner))
                previous[column] += amount
            owner = batch_no
        connection.execute(manual.update().where(manual.c.id == row["id"]).values(
            source_batches={column: owner for column in combined}))


def upgrade():
    attach_legacy_rollback(op.get_bind())


def downgrade():
    # Ownership is durable business provenance; leave it intact when reverting this data-only revision.
    pass
