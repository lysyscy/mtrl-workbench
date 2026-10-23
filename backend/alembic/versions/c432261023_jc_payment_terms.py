"""Add independent contract payment terms and method; preserve existing business values."""
from alembic import op
import sqlalchemy as sa

revision = "c432261023"
down_revision = "c391261021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jc_contract", sa.Column("payment_term", sa.String(32), nullable=False, server_default=""))
    op.add_column("jc_contract", sa.Column("payment_method", sa.String(16), nullable=False, server_default=""))


def downgrade():
    op.drop_column("jc_contract", "payment_method")
    op.drop_column("jc_contract", "payment_term")
