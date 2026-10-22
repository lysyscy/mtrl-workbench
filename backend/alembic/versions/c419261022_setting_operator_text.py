"""Preserve full setting operator identities without truncating existing data."""
from alembic import op
import sqlalchemy as sa

revision = "c419261022"
down_revision = "c400261022"
branch_labels = None
depends_on = None


def upgrade():
    for table, column in (("app_setting", "updated_by"), ("app_setting_log", "operator")):
        op.alter_column(table, column, existing_type=sa.String(64), type_=sa.Text(), existing_nullable=False)


def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE app_setting, app_setting_log IN ACCESS EXCLUSIVE MODE"))
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM app_setting WHERE char_length(updated_by)>64) "
                                  "OR EXISTS (SELECT 1 FROM app_setting_log WHERE char_length(operator)>64)")).scalar_one():
        raise RuntimeError("Setting operator identities exceed 64 characters; refusing to truncate")
    for table, column in (("app_setting", "updated_by"), ("app_setting_log", "operator")):
        op.alter_column(table, column, existing_type=sa.Text(), type_=sa.String(64), existing_nullable=False)
