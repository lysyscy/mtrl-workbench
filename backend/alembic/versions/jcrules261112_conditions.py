"""扩展集采合同抓取剔除条件。"""
from alembic import op
import sqlalchemy as sa

revision = "jcrules261112"
down_revision = "jcapproval261112"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jc_ignore_project", sa.Column("kind", sa.String(16), nullable=False, server_default="project"))
    op.add_column("jc_ignore_project", sa.Column("contract_no", sa.String(64), nullable=False, server_default=""))
    op.add_column("jc_ignore_project", sa.Column("bill_name_keyword", sa.String(512), nullable=False, server_default=""))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM jc_ignore_project WHERE kind <> 'project' LIMIT 1")).scalar():
        raise RuntimeError("存在按合同编号或单据名剔除的规则，降级会丢失条件。")
    for field in ("bill_name_keyword", "contract_no", "kind"):
        op.drop_column("jc_ignore_project", field)
