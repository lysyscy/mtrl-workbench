"""增加审核合同日期保护标记，存量及新记录默认未保护。"""

from alembic import op
import sqlalchemy as sa

revision = "c313261012"
down_revision = "c271261010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jc_contract", sa.Column(
        "contract_date_locked", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))


def downgrade():
    op.drop_column("jc_contract", "contract_date_locked")
