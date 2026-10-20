"""历史汇总沿用集采出口，关联付款动态取统计金额、日期取实际流水。"""
from decimal import Decimal
from io import BytesIO
from contextlib import contextmanager
import base64

from openpyxl import load_workbook
from sqlalchemy import event

from app.core.db import session_scope
from app.mod01_projects import repository as projects
from app.mod01_projects import router as project_api
from app.mod01_projects.schemas import CreateProjectRequest, ProjectExportIn
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_actions import apply_stat_change
from app.mod05_flow import repository as flows
from app.mod05_flow import service as flow_service
from app.mod11_jc import repository as R, service as S
from tests.ui_helpers import ui_page  # noqa: F401


def test_history_summary_and_dynamic_stat_payment(monkeypatch):
    with session_scope() as s:
        @contextmanager
        def borrowed_session():
            yield s
        monkeypatch.setattr(project_api, 'session_scope', borrowed_session)
        created = project_api.create_project(CreateProjectRequest(
            project_type='normal', name_full='历史项目测试', disp='历史项目测试'))
        p = projects.get_project(s, created.id)
        assert p.warehouse_name.startswith('未建仓-')
        assert any(x.key == p.warehouse_name and x.display == p.disp
                   for x in project_api.candidates(include_archived=True))
        exported = project_api.export_projects(ProjectExportIn(ids=[p.id]))
        project_book = load_workbook(BytesIO(base64.b64decode(exported['content_b64'])), data_only=True)
        assert exported['rows'] == 1 and p.name_full in str(list(project_book.active.values))
        c = R.insert_contract(s, project_id=p.id, material_name=p.name_full,
                              remark='历史未结金额；核对截至日：2026-09-30；')
        R.insert_invoice(s, contract_id=c.id, kind='supplier', invoice_date='2026-09-30', amount=100000)
        baseline = S.debt_of_ledger(s)
        n = PaymentNotice(ph_id='__tail276_dynamic__', ownership_id=p.id, category='jc',
                          amount_approved=80000, stat_paid=0, doc_date='2026-09-10')
        s.add(n)
        s.flush()
        assert S.act_link_notice(s, notice_id=n.id, contract_id=c.id)['ok']
        link = R.payment_of_notice(s, n.id)
        assert link.amount == 0 and link.pay_date == ''
        # 存量旧值也不能重新成为计算来源。
        link.amount = Decimal('80000')
        link.pay_date = '2026-09-10'
        s.flush()
        assert S.build_detail(s, c.id)['debt'] == Decimal('100000')
        assert R.payments_of(s, c.id)[0]['date'] == ''
        f1 = flows.create_flow(s, notice_id=n.id, project_id=p.id, amount=30000, pay_date='2026-10-03')
        assert S.build_detail(s, c.id)['debt'] == Decimal('70000')
        f2 = flows.create_flow(s, notice_id=n.id, project_id=p.id, amount=20000, pay_date='2026-10-05')
        assert S.build_detail(s, c.id)['pay_sum'] == Decimal('50000')
        assert R.payments_of(s, c.id)[0]['date'] == '2026-10-05'
        flows.revoke(s, f2, reason='测试撤销')
        s.flush()
        assert S.build_detail(s, c.id)['debt'] == Decimal('70000')
        assert R.payments_of(s, c.id)[0]['date'] == '2026-10-03'
        apply_stat_change(s, notice_id=n.id, field='stat_paid', value='45000', changed_by='测试')
        assert flows.effective_total_of(s, n.id) == Decimal('30000')
        assert S.build_detail(s, c.id)['debt'] == Decimal('55000')
        assert S.debt_of_ledger(s) == baseline - Decimal('45000')
        # MOD-05仍通过MOD-11注入，不产生第二份计算。
        assert flow_service.build_debt_live(s) == flow_service.build_debt(s, jc_debt=S.debt_of_ledger(s))
        c2 = R.insert_contract(s, project_id=p.id, material_name='普通合同', contract_date='2026-10-01')
        S.act_link_notice(s, notice_id=n.id, contract_id=c2.id)
        assert R.payments_of(s, c.id) == []
        assert R.payments_of(s, c2.id)[0]['amount'] == Decimal('45000')
        S.act_unlink_notice(s, notice_id=n.id)
        assert s.get(type(f1), f1.id).status == 'effective'
        manual = R.insert_payment(s, contract_id=c.id, pay_date='2026-10-08', amount=123)
        assert R.payments_of(s, c.id)[0]['amount'] == Decimal('123')
        assert R.payments_of(s, c.id)[0]['date'] == manual.pay_date
        queries = []
        def count(*args):
            queries.append(args[2])
        event.listen(s.bind, 'before_cursor_execute', count)
        try:
            R.payments_of_many(s, [c.id, c2.id])
            assert len(queries) == 1
        finally:
            event.remove(s.bind, 'before_cursor_execute', count)
        book = load_workbook(BytesIO(S.export_xlsx(s, ids=[c.id])), data_only=True)
        assert '历史项目测试' in str(list(book.active.values))
        s.rollback()


def test_shell_create_history_and_dates(ui_page):
    ui_page.evaluate("""() => {
      window.created=null; window.reloads=0;
      API.pjCreate=async b=>{window.created=b;return {id:2};};
      API.projects=async()=>{window.reloads++;return [{id:2,project_type:'normal',name_full:'历史测试全名',disp:'历史测试全名',warehouse_name:'未建仓-9',status:'active',ord:2}];};
      API.trails=async()=>[]; reloadPending=async()=>{};
      VIEW='m01'; render();
    }""")
    ui_page.locator('[data-act="pjCreateOpen"]').click()
    ui_page.locator('#pjCreateFull').fill('历史测试全名')
    ui_page.locator('[data-act="pjCreateSave"]').click()
    ui_page.wait_for_function('window.reloads===1 && document.querySelector("#view").textContent.includes("无仓库（历史项目）")')
    assert ui_page.evaluate('window.created') == {'project_type': 'normal', 'name_full': '历史测试全名', 'disp': '历史测试全名'}
    assert '无仓库（历史项目）' in ui_page.locator('#view').inner_text()
    ui_page.evaluate("VIEW='m11';fJc.projs=['未建仓-9'];render();ACT.jcAdd();")
    ui_page.locator('[data-act="jcNHistory"]').check()
    assert ui_page.locator('#jcNMaterial').input_value() == '历史测试全名'
    assert ui_page.locator('#jcNDate').input_value() == ''
    ui_page.locator('#jcNCutoff').fill('2026-09-30')
    ui_page.evaluate("""() => {
      API.m11Add=async b=>{window.added=b;return {ok:true,id:9,tag:'纳入台账'};};
      API.m11List=async()=>({rows:[{id:9,project_key:'未建仓-9',material:'历史测试全名',remark:JC_HISTORY_PREFIX+'2026-09-30；',tag:'纳入台账',inv_sum:'100000',pay_sum:'30000',settle:'100000',debt:'70000'}]});
    }""")
    ui_page.locator('[data-act="jcRowSave"]').click()
    ui_page.wait_for_function('window.added && !jcNewOn')
    added = ui_page.evaluate('window.added')
    assert added['contract_date'] == '' and added['supplier'] == '' and added['trade_co'] is None
    assert added['remark'] == '历史未结金额；核对截至日：2026-09-30；'
    ui_page.evaluate("""async () => {
      API.m11Detail=async()=>({data:{supplier_invoices:[{id:1,date:'2026-09-30',amount:'100000'}],payments:[{id:2,date:'2026-10-03',amount:'30000',source:'notice',notice_id:101}],payment_display_rows:[{id:2,date:'2026-10-03',amount:'30000',source:'notice',notice_id:101,display_kind:'flow'}]}});
      await ACT.jcInvDlg({dataset:{id:'9'}});
    }""")
    assert '核对截至日' in ui_page.locator('#modalRoot').inner_text()
    assert ui_page.locator('#modalRoot tbody tr').first.locator('td').nth(1).inner_text() == '2026-09-30'
    ui_page.evaluate("ACT.jcPayDlg({dataset:{id:'9'}})")
    assert '2026-10-03' in ui_page.locator('#modalRoot').inner_text()
    assert '付款流水 · 通知书 DOC-101' in ui_page.locator('#modalRoot').inner_text()
    assert ui_page.locator('#modalRoot [data-act="jcPayDel"]').count() == 0


def test_warehouse_project_can_choose_history_or_normal_contract(ui_page):
    ui_page.evaluate("VIEW='m11';fJc.projs=['测试仓库'];render();ACT.jcAdd();")
    history = ui_page.locator('[data-act="jcNHistory"]')
    assert not history.is_checked()
    assert ui_page.locator('#jcNDate').input_value() == ui_page.evaluate('SYS_TODAY')
    history.check()
    assert ui_page.locator('#jcNMaterial').input_value() == '测试项目全名'
    assert ui_page.locator('#jcNDate').input_value() == ''
    assert ui_page.locator('#jcNSupplier').is_disabled()
    history.uncheck()
    assert ui_page.locator('#jcNDate').input_value() == ui_page.evaluate('SYS_TODAY')
    assert ui_page.locator('#jcNSupplier').is_enabled()
    history.check()
    ui_page.locator('#jcNCutoff').fill('2026-09-30')
    ui_page.evaluate("""() => {
      API.m11Add=async b=>{window.warehouseAdded=b;return {ok:true,id:9,tag:'纳入台账'};};
      API.m11List=async()=>({rows:[]});
    }""")
    ui_page.locator('[data-act="jcRowSave"]').click()
    ui_page.wait_for_function('window.warehouseAdded && !jcNewOn')
    added = ui_page.evaluate('window.warehouseAdded')
    assert added['project_key'] == '测试仓库'
    assert added['material_name'] == '测试项目全名'
    assert added['contract_date'] == '' and added['supplier'] == ''
    assert added['remark'] == '历史未结金额；核对截至日：2026-09-30；'
