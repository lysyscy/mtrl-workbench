"""Store equipment ledger prices and amounts to the cent."""
from alembic import op
import sqlalchemy as sa

revision = "equipmoney261126"
down_revision = "equipcount261126"
branch_labels = None
depends_on = None

MONEY_COLUMNS = {
    "m16_equipment_items": ("purchase_price",),
    "m16_equipment_scraps": ("purchase_price",),
    "m16_inventory_items": ("unit_price", "book_amount", "count_amount", "diff_amount"),
    "m16_rental_lines": ("original_value", "custom_unit_price", "unit_price", "amount"),
}


def amount_using(amount, quantity, price, new_price, *, when="TRUE"):
    # The old export recognized formula values within half a cent.
    return f"""CASE
        WHEN {when} AND abs({amount} - {quantity} * {price}) <= 0.005
        THEN round({quantity} * ({new_price}), 2)
        ELSE round({amount}, 2)
        END"""


def upgrade():
    op.execute("SELECT pg_advisory_xact_lock(16261123)")
    rental_price = """CASE
        WHEN unit_price = coalesce(custom_unit_price, round(original_value * 0.05, 4))
        THEN coalesce(round(custom_unit_price, 2), round(round(original_value, 2) * 0.05, 2))
        ELSE round(unit_price, 2)
        END"""
    calculated = {
        "m16_inventory_items": {
            f"{prefix}_amount": amount_using(f"{prefix}_amount", f"{prefix}_qty", "unit_price", "round(unit_price, 2)")
            for prefix in ("book", "count", "diff")
        },
        "m16_rental_lines": {
            "unit_price": rental_price,
            "amount": amount_using("amount", "quantity", "unit_price", rental_price, when="billing_status = 'normal'"),
        },
    }
    for table, columns in MONEY_COLUMNS.items():
        # Each USING expression sees the same pre-migration row.
        changes = [
            f"ALTER COLUMN {column} TYPE numeric(18, 2) USING "
            + calculated.get(table, {}).get(column, f"round({column}, 2)")
            for column in columns
        ]
        op.execute(f"ALTER TABLE {table} " + ", ".join(changes))


def downgrade():
    for table, columns in MONEY_COLUMNS.items():
        for column in columns:
            op.alter_column(table, column, existing_type=sa.Numeric(18, 2), type_=sa.Numeric(18, 4))
