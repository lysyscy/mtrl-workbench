"""281的展示与撤销回执；隔离事务和浏览器，不写现场数据。"""

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir
from contextlib import contextmanager
from decimal import Decimal
import json
from pathlib import Path

from app.core.db import session_scope
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_actions import apply_stat_change
from app.mod03_notice.notice_api_router import _api_item
from app.mod05_flow import repository as flows, router as flow_api
from app.mod11_jc import repository as R, service as S, api as jc_api
from tests.test_acc_jc_pay_link import _project


def test_display_and_revoke_receipt(monkeypatch, rollback_db):
    with session_scope() as s:
        @contextmanager
        def borrowed():
            yield s
        monkeypatch.setattr(jc_api, 'session_scope', borrowed)
        monkeypatch.setattr(flow_api, 'session_scope', borrowed)
        p = _project(s, '__自检仓_281__')
        c = R.insert_contract(s, project_id=p.id, material_name='281材料')
        R.insert_invoice(s, contract_id=c.id, kind='supplier', invoice_date='2026-10-01', amount=1000)
        n = PaymentNotice(ph_id='__281__', category='jc', ownership_id=p.id, amount_approved=1000, stat_paid=0)
        s.add(n)
        s.flush()
        assert S.act_link_notice(s, notice_id=n.id, contract_id=c.id)['ok']
        link = R.payment_of_notice(s, n.id)
        assert S.build_detail(s, c.id)['payment_display_rows'] == []
        assert n.id in S.build_list(s)['rows'][-1]['notice_ids']
        assert not S.act_del_payment(s, payment_id=link.id)['ok']
        f1 = flows.create_flow(s, notice_id=n.id, project_id=p.id, amount=300, pay_date='2026-10-02')
        f2 = flows.create_flow(s, notice_id=n.id, project_id=p.id, amount=200, pay_date='2026-10-03')
        rows = jc_api.api_detail(c.id)['data']['payment_display_rows']
        assert [(r['date'], r['amount']) for r in rows] == [('2026-10-02', '300.00'), ('2026-10-03', '200.00')]
        json.dumps(jc_api.api_detail(c.id))
        assert len(R.payments_of(s, c.id)) == 1
        r = flow_api.api_revoke(f2.id, reason='正常撤销', changed_by='测试')
        assert r['jc_effect'] == {'contract_id': c.id, 'before': '500.00', 'after': '300.00', 'protected': False}
        apply_stat_change(s, notice_id=n.id, field='stat_paid', value='450', changed_by='测试')
        d = S.build_detail(s, c.id)
        assert d['pay_sum'] == Decimal('450') and d['debt'] == Decimal('550')
        assert len(d['payment_display_rows']) == 1 and d['payment_display_rows'][0]['amount'] == Decimal('450')
        r = flow_api.api_revoke(f1.id, reason='保护人工值', changed_by='测试', stat_choice='keep')
        assert r['jc_effect'] == {'contract_id': c.id, 'before': '450.00', 'after': '450.00', 'protected': True}
        # 统计0却有实付必须保留差异可见性；全撤销且统计0才隐藏。
        apply_stat_change(s, notice_id=n.id, field='stat_paid', value='0', changed_by='测试')
        flows.create_flow(s, notice_id=n.id, project_id=p.id, amount=100, pay_date='2026-10-04')
        rows = S.build_detail(s, c.id)['payment_display_rows']
        assert len(rows) == 1 and rows[0]['amount'] == 0 and rows[0]['mismatch']
        manual = S.act_add_payment(s, contract_id=c.id, date='2026-10-05', amount='123')
        assert manual['ok']
        mid = next(r['id'] for r in R.payments_of(s, c.id) if r['source'] == 'manual')
        assert S.act_del_payment(s, payment_id=mid)['ok']
        c2 = R.insert_contract(s, project_id=p.id, material_name='281换合同')
        assert S.act_link_notice(s, notice_id=n.id, contract_id=c2.id)['ok']
        assert S.act_unlink_notice(s, notice_id=n.id)['ok']
        assert len(flows.list_flows_of_notice(s, n.id)) == 3


def test_notice_only_revoked_flow():
    from app.mod03_notice.list_view import NoticeRow
    row = NoticeRow(notice_id=1, flows=({'status': 'revoked', 'amount': 10},))
    payload = _api_item({'_row': row})
    assert payload['has_any_flow'] and not payload['has_effective_flow']
