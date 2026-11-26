"""Preserve baseline inventory inclusion and keep historical transfers out of the i8 retry queue."""
from alembic import op
import sqlalchemy as sa

revision = "equipbase261123"
down_revision = "equip261123"
branch_labels = None
depends_on = None

TABLE = "m16_equipment_transfers"
CHECK = "ck_m16_equipment_transfers_i8_sync_status"


def upgrade():
    op.add_column("m16_equipment_items", sa.Column("source_lists_inventory", sa.Boolean()))
    op.drop_constraint(CHECK, TABLE, type_="check")
    op.create_check_constraint(CHECK, TABLE, "i8_sync_status IN ('synced','pending','conflict','failed','not_applicable')")


def downgrade():
    # Existing baseline rows require an explicit business decision before downgrading.
    op.drop_constraint(CHECK, TABLE, type_="check")
    op.create_check_constraint(CHECK, TABLE, "i8_sync_status IN ('synced','pending','conflict','failed')")
    op.drop_column("m16_equipment_items", "source_lists_inventory")
