"""Keep manually unbound notices out of automatic contract matching."""
from alembic import op
import sqlalchemy as sa

revision = "jcautolink261126"
down_revision = "equipmoney261126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_notice", sa.Column(
        "jc_auto_link_blocked", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))


def downgrade() -> None:
    op.drop_column("payment_notice", "jc_auto_link_blocked")
