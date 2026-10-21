"""Two usable recharges aggregate in their document month without an opening entry."""
from decimal import Decimal

from app.mod03_notice.models import PaymentNotice, NoticeStatLog
from app.mod03_notice.notice_manual_actions import apply_manual_save
from app.mod05_flow import service
from app.mod05_flow.models import PaymentFlow
from tests.test_ledger_opening_range import project
from tests.test_proc_split_cutoffs import session  # noqa: F401


def test_two_recharges_manual_edit_and_omitted_field_preserve_actual_flows(session):
    p = project(session, '__manual_settlement__')
    original = PaymentNotice(ph_id='__manual_settlement_source__', doc_date='2026-09-01',
        ownership_id=p.id, category='material', amount_approved=20000,
        stat_settle=20000, stat_paid=20000, excluded=False, fields={})
    session.add(original)
    session.flush()
    fields = dict(doc_date='2026-09-15', ownership_id=str(p.id), category='material',
                  amount_approved='20000', stat_settle='20000', stat_paid='20000')
    manual, _ = apply_manual_save(session, entered_by='测试', fields=fields)
    for i, row in enumerate([original, manual]):
        session.add(PaymentFlow(notice_id=row.id, flow_no=f'__manual_settlement_{i}__',
            amount=20000, pay_date='2026-09-15', pay_method='现汇', status='effective'))
    session.flush()
    def month():
        side = next(s for s in service.build_ledger(session, project_id=p.id)['sides'] if s['category']=='material')
        assert side['opening_id'] is None
        return next(r for r in side['rows'] if r['month']=='2026-09')
    row = month()
    assert (row['other_expense'], row['payment'], row['debt']) == ('40000.00', '40000.00', '0.00')
    fields['stat_settle'] = '15000'
    apply_manual_save(session, row_id=str(manual.id), entered_by='测试', fields=fields)
    assert month()['debt'] == '-5000.00'
    fields.pop('stat_settle')
    apply_manual_save(session, row_id=str(manual.id), entered_by='测试', fields=fields)
    assert manual.stat_settle == Decimal('15000')
    logs = session.query(NoticeStatLog).filter_by(notice_id=manual.id, field='stat_settle').all()
    assert len(logs) == 1
    assert sum(f.amount for f in session.query(PaymentFlow).filter(PaymentFlow.notice_id.in_([original.id,manual.id]))) == Decimal('40000')
