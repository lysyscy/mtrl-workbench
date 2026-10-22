"""Preserve the complete operator identity in execution records."""
from alembic import op
import sqlalchemy as sa

revision = "c400261022"
down_revision = "c391261021"
branch_labels = None
depends_on = None


def upgrade():
    # UserAccount.account is Text; a blank display name falls back to that account.
    op.alter_column("run_record", "triggered_by", existing_type=sa.String(64),
                    type_=sa.Text(), existing_nullable=False)


def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE run_record IN ACCESS EXCLUSIVE MODE"))
    if connection.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM run_record WHERE char_length(triggered_by) > 64)"
    )).scalar_one():
        raise RuntimeError("Run records contain operator identities over 64 characters; refusing to truncate")
    op.alter_column("run_record", "triggered_by", existing_type=sa.Text(),
                    type_=sa.String(64), existing_nullable=False)
