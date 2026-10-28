"""Keep missing or cleared mechanical amounts distinct from explicit zero."""
from alembic import op
import sqlalchemy as sa

revision = 'mechauto261028'
down_revision = 'invadj261027'
branch_labels = None
depends_on = None


def upgrade():
    for index in range(6):
        op.alter_column('proc_mech_manual', f'mech_{index}', existing_type=sa.Numeric(18, 2),
                        nullable=True, server_default=None)


def downgrade():
    # Never manufacture zero amounts merely to satisfy the old schema.
    columns = ' OR '.join(f'mech_{index} IS NULL' for index in range(6))
    if op.get_bind().execute(sa.text(f'SELECT 1 FROM proc_mech_manual WHERE {columns} LIMIT 1')).first():
        raise RuntimeError('机械金额仍有空值，不能降级为强制非空结构')
    for index in range(6):
        op.alter_column('proc_mech_manual', f'mech_{index}', existing_type=sa.Numeric(18, 2),
                        nullable=False)
