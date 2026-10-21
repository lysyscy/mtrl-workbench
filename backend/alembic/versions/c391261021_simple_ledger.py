"""Replace cumulative reconciliation with directly editable historical rows."""
from alembic import op
import sqlalchemy as sa

revision = "c391261021"
down_revision = "c390261021"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    records = [dict(r) for r in connection.execute(sa.text(
        "SELECT * FROM opening_balance ORDER BY cutoff_ym,id FOR UPDATE")).mappings()]
    # 生产仅两组已逐条确认的结算/付款配对；其他形态先停，不能猜含义或月份。
    if any(r["category"] != "material" or r["cutoff_ym"] > "2025-11"
           or r["entry_kind"] not in ("settlement", "payment") for r in records):
        raise RuntimeError("发现未经确认的历史记录，请先核对再迁移")
    latest = {}
    for row in records:
        if row["entry_kind"] == "payment":
            latest[(row["project_id"], row["category"])] = row["id"]
    for row in records:
        if row["entry_kind"] != "payment":
            continue
        paid = row["paid_amount"] - row["paid_basis"] if latest[(row["project_id"], row["category"])] == row["id"] else 0
        matches = [r for r in records if r["entry_kind"] == "settlement"
                   and (r["project_id"], r["category"], r["cutoff_ym"], r["remark"])
                       == (row["project_id"], row["category"], row["cutoff_ym"], row["remark"])]
        if len(matches) != 1 or matches[0]["paid_amount"] != 0:
            raise RuntimeError("历史结算与付款不能唯一配对，请先核对再迁移")
        connection.execute(sa.text("UPDATE opening_balance SET paid_amount=:paid WHERE id=:id"),
                           {"id": matches[0]["id"], "paid": paid})
        matches[0]["paid_amount"] = paid
        connection.execute(sa.text("DELETE FROM opening_balance WHERE id=:id"), {"id": row["id"]})
    connection.execute(sa.text("UPDATE opening_balance SET entry_kind='manual'"))
    op.alter_column("opening_balance", "entry_kind", server_default="manual")
    for column in ("paid_basis", "settle_basis", "input_mode"):
        op.drop_column("opening_balance", column)


def downgrade():
    raise RuntimeError("历史台账已简化；回退请使用迁移前备份，避免重建出错误的累计记录")
