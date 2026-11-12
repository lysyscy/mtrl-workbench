"""集采合同记录最近一次从 i8 抓到的审批状态。"""
from alembic import op
import sqlalchemy as sa

revision = "jcapproval261112"
down_revision = "oilpolish261109"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jc_contract", sa.Column("approve_status", sa.String(8), nullable=True))


def downgrade():
    op.drop_column("jc_contract", "approve_status")
