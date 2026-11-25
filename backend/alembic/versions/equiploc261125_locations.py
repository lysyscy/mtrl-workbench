"""Add the equipment ledger's non-system location dictionary."""
from alembic import op
import sqlalchemy as sa

revision = "equiploc261125"
down_revision = "equipproj261124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "m16_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("default_project_id", sa.Integer(), sa.ForeignKey("project.id", ondelete="SET NULL")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_m16_locations_name"),
    )


def downgrade():
    op.drop_table("m16_locations")
