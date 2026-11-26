"""Persist payment notice fetch jobs and their receipts."""
from alembic import op
import sqlalchemy as sa

revision = "noticejobs261126"
down_revision = "jcautolink261126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notice_fetch_job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account", sa.String(64), nullable=False),
        sa.Column("year_month", sa.String(7), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(24), nullable=False),
        sa.Column("stage_label", sa.String(64), nullable=False),
        sa.Column("boot_id", sa.String(32), nullable=False),
        sa.Column("result_json", sa.JSON(none_as_null=True)),
        sa.Column("error_message", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("acknowledged_at", sa.DateTime()),
    )
    op.create_index("uq_notice_fetch_job_running", "notice_fetch_job", ["account", "year_month"],
                    unique=True, postgresql_where=sa.text("status = 'running'"))
    op.create_index("ix_notice_fetch_job_unacknowledged", "notice_fetch_job", ["account", "id"],
                    postgresql_where=sa.text("acknowledged_at IS NULL"))


def downgrade() -> None:
    op.drop_table("notice_fetch_job")
