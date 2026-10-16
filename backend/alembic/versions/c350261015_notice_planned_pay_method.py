"""Add the confirmed planned payment method to notices."""

from alembic import op
import sqlalchemy as sa

revision = "c350261015"
down_revision = "c313261012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_notice", sa.Column(
        "planned_pay_method", sa.String(32), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("payment_notice", "planned_pay_method")
