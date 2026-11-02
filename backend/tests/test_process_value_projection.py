"""过程、欠款与大表共用的机械金额投影保持金额及身份，完整来源仍可读。"""
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import event

from app.core.db import session_scope
from app.mod06_proc import repository as R
from app.mod06_proc.models import ProcMechManual


def test_value_projection_preserves_zero_unknown_and_complete_source(rollback_db):
    warehouse = '__value_projection_' + uuid4().hex
    with session_scope() as session:
        row = ProcMechManual(warehouse_name=warehouse, ym='2026-10',
                             mech_0=Decimal('0.00'), mech_1=None, mech_2=Decimal('12.34'),
                             source_batches={'__detail_sources': {
                                 'mech_0': {'mode': 'detail', 'basis': {'batch': 'confirmed'}}}})
        session.add(row)
        session.flush()
        connection = session.connection()
        statements = []

        def record(_connection, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(connection, 'before_cursor_execute', record)
        try:
            values = next(item for item in R.load_mech(session, with_sources=False)
                          if item['warehouse'] == warehouse)
        finally:
            event.remove(connection, 'before_cursor_execute', record)
        assert values == {'ym': '2026-10', 'warehouse': warehouse, 'project_id': None,
                          'mech_0': Decimal('0.00'), 'mech_1': None, 'mech_2': Decimal('12.34'),
                          'mech_3': None, 'mech_4': None, 'mech_5': None}
        assert statements and all('source_batches' not in statement for statement in statements)
        complete = next(item for item in R.load_mech(session) if item['warehouse'] == warehouse)
        assert complete['sources']['mech_0']['basis'] == {'batch': 'confirmed'}
        assert complete['effective_signature']
        session.rollback()
