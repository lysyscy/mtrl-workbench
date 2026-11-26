"""Preserve uncounted inventory quantities."""
from alembic import op
import sqlalchemy as sa

revision = "equipcount261126"
down_revision = "equiploc261125"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("m16_inventory_items", "count_qty", existing_type=sa.Numeric(18, 4), nullable=True)


def downgrade():
    op.alter_column("m16_inventory_items", "count_qty", existing_type=sa.Numeric(18, 4), nullable=False)
