"""Preserve old fee records and create one monthly value per fee item."""
from alembic import op
import sqlalchemy as sa

revision = "feeitem261027"
down_revision = "bmonth261026"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    collision = connection.execute(sa.text("SELECT 1 FROM fee_manual_item WHERE item_name = :name LIMIT 1"),
        {"name": "安全文明施工费（按 CBS 分类）"}).first()
    if collision:
        raise RuntimeError("手填费用项与自动项同名，需先核对；原记录未修改")
    op.create_table("fee_item",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_fee_item_project_id", "fee_item", ["project_id"])
    op.create_index("uq_fee_item_project_name_active", "fee_item", ["project_id", "name"], unique=True, postgresql_where=sa.text("NOT deleted"))
    op.create_table("fee_monthly_amount",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fee_item_id", sa.Integer(), sa.ForeignKey("fee_item.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ym", sa.String(7), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_name", sa.String(128), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("fee_item_id", "ym", name="uq_fee_item_month"))
    for col in ("fee_item_id", "project_id", "ym"):
        op.create_index("ix_fee_monthly_amount_"+col, "fee_monthly_amount", [col])
    connection.execute(sa.text("""INSERT INTO fee_item (project_id, name, created_at, updated_at)
        SELECT project_id, item_name, min(created_at), max(updated_at)
        FROM fee_manual_item GROUP BY project_id, item_name"""))
    connection.execute(sa.text("""INSERT INTO fee_monthly_amount (fee_item_id, ym, project_id, item_name, amount, created_at, updated_at)
        SELECT item.id, old.ym, old.project_id, old.item_name, sum(old.amount), min(old.created_at), max(old.updated_at)
        FROM fee_manual_item old JOIN fee_item item ON item.project_id = old.project_id AND item.name = old.item_name
        GROUP BY item.id, old.ym, old.project_id, old.item_name"""))


def downgrade():
    op.drop_table("fee_monthly_amount")
    op.drop_index("uq_fee_item_project_name_active", table_name="fee_item")
    op.drop_index("ix_fee_item_project_id", table_name="fee_item")
    op.drop_table("fee_item")
