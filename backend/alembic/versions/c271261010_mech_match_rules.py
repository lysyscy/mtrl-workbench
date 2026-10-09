"""新增机械报表项目规则，预置全部有仓库键的在建项目。"""

from alembic import op
import sqlalchemy as sa

revision = "c271261010"
down_revision = "c262263e2610"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("proc_mech_match_rule",
                    sa.Column("warehouse_name", sa.String(255), primary_key=True),
                    sa.Column("aliases", sa.JSON(), nullable=False))
    from app.mod06_proc.mech_matching import SEED_ALIASES

    connection = op.get_bind()
    projects = sa.table("project", sa.column("warehouse_name"), sa.column("disp"),
                        sa.column("status"), sa.column("project_type"))
    rules = sa.table("proc_mech_match_rule", sa.column("warehouse_name"), sa.column("aliases", sa.JSON()))
    for row in connection.execute(sa.select(projects).where(
            projects.c.status == "active", projects.c.project_type.in_(["normal", "small"]))):
        if row.warehouse_name:
            connection.execute(rules.insert().values(warehouse_name=row.warehouse_name,
                               aliases=SEED_ALIASES.get(row.disp, [row.disp or row.warehouse_name])))


def downgrade():
    op.drop_table("proc_mech_match_rule")
