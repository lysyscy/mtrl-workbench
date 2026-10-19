"""Mechanical workbench drafts and immutable adoption previews."""
from alembic import op
import sqlalchemy as sa

revision = "c350261019"
down_revision = "c350261015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("mechanical_workbench_record",
                    sa.Column("key", sa.String(512), primary_key=True),
                    sa.Column("revision", sa.Integer(), nullable=False),
                    sa.Column("payload", sa.JSON(), nullable=False),
                    sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_table("mechanical_workbench_preview",
                    sa.Column("id", sa.String(64), primary_key=True),
                    sa.Column("kind", sa.String(32), nullable=False),
                    sa.Column("payload", sa.JSON(), nullable=False),
                    sa.Column("result", sa.JSON(), nullable=True),
                    sa.Column("created_at", sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table("mechanical_workbench_preview")
    op.drop_table("mechanical_workbench_record")
