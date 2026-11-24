"""Link equipment ledger project references to the project archive."""
from alembic import op
import sqlalchemy as sa

revision = "equipproj261124"
down_revision = "equipbase261123"
branch_labels = None
depends_on = None

PROJECTS = (
    ("m16_equipment_items", ("purchase_project", "current_project")),
    ("m16_equipment_transfers", ("from_project", "to_project")),
    ("m16_equipment_scraps", ("original_project",)),
    ("m16_rental_lines", ("project",)),
)


def upgrade():
    for table, prefixes in PROJECTS:
        for prefix in prefixes:
            op.add_column(table, sa.Column(f"{prefix}_id", sa.Integer(), sa.ForeignKey("project.id", ondelete="SET NULL")))
            op.add_column(table, sa.Column(f"{prefix}_custom", sa.Text()))


def downgrade():
    for table, prefixes in reversed(PROJECTS):
        for prefix in reversed(prefixes):
            op.drop_column(table, f"{prefix}_custom")
            op.drop_column(table, f"{prefix}_id")
