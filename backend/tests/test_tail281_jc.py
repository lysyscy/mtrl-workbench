"""281的展示与撤销回执；隔离事务和浏览器，不写现场数据。"""
from contextlib import contextmanager
from decimal import Decimal
import json

from app.core.db import session_scope
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_actions import apply_stat_change
from app.mod03_notice.notice_api_router import _api_item
from app.mod05_flow import repository as flows, router as flow_api
from app.mod11_jc import repository as R, service as S, api as jc_api
from tests.test_acc_jc_pay_link import _project
from tests.test_shell_ui_workflow import ui_page  # noqa: F401
from tests.acc_plugin import acc


@acc()
def test_display_and_revoke_receipt(monkeypatch):
    with session_scope() as s:
        @contextmanager
        def borrowed():
            yield s
        monkeypatch.setattr(jc_api, 'session_scope', borrowed)
        monkeypatch.setattr(flow_api, 'session_scope', borrowed)
        p = _project(s, '__自检仓_281__')
        c = R.insert_contract(s, project_id=p.id, material_name='281材料')
        R.insert_invoice(s, contract_id=c.id, kind='supplier', invoice_date='2026-10-01', amount=1000)
        n = PaymentNotice(ph_id='__281__', category='jc', amount_approved=1000, stat_paid=0)
        s.add(n)
        s.flush()
        S.act_link_notice(s, notice_id=n.id, contract_id=c.id)
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
        r = flow_api.api_revoke(f1.id, reason='保护人工值', changed_by='测试')
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
        s.rollback()


@acc()
def test_notice_only_revoked_flow():
    from app.mod03_notice.list_view import NoticeRow
    row = NoticeRow(notice_id=1, flows=({'status': 'revoked', 'amount': 10},))
    payload = _api_item({'_row': row})
    assert payload['has_any_flow'] and not payload['has_effective_flow']


@acc()
def test_browser_flow_dialogs_and_virtual_jump(ui_page):
    p = ui_page
    from app.mod03_notice.page import render_theme
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate('''() => {
      window.flowReads=0;
      API.flows=async()=>{flowReads++;return {rows:[{id:31,notice_id:101,pay_date:'2026-10-02',amount:'300',status:'effective',pay_method:'现汇'},
        {id:32,notice_id:101,pay_date:'2026-10-03',amount:'200',status:'revoked',revoke_reason:'误付'}]};};
      API.m11List=async()=>({rows:[{id:11,date:'2026-10-01',material:'281材料',supplier:'供应商',project_key:'测试仓库',
        contract_amt:'1000',settle:'800',pay_sum:'450',debt:'350',method:'现汇',arch:'已存档',remark:'合同备注',notice_ids:[101]}]});
      NO[0].hasAnyFlow=true;render();
    }''')
    assert p.locator('[data-act="ntFlows"]').count() == 1
    p.click('[data-act="ntFlows"]')
    p.wait_for_selector('.mask')
    assert '误付' in p.inner_text('.mask') and '集采合同' not in p.inner_text('.mask')
    p.screenshot(path='.codebuddy/work/00-scratch/tmp-20261011-281-flows.png')
    table = p.locator('.mask table').inner_html()
    p.click('[data-act="closeModal"]')
    p.evaluate("ACT.ntTrace({dataset:{id:'101'}})")
    p.wait_for_selector('.mask')
    assert '合同备注' in p.inner_text('.mask') and '450.00' in p.inner_text('.mask')
    assert p.locator('.mask table.dt').last.inner_html() == table
    p.evaluate("document.documentElement.style.setProperty('--fscale','1.25')")
    p.screenshot(path='.codebuddy/work/00-scratch/tmp-20261011-281-contract.png')
    p.evaluate("document.documentElement.style.setProperty('--fscale','1')")
    p.click('[data-act="closeModal"]')
    p.evaluate('''() => {
      const saved=NO; NO=[];window.noticeReads=0;
      reloadNotices=async()=>{noticeReads++;NO=saved;render();};
      API.m11Detail=async()=>({ok:true,data:{payment_display_rows:[{id:55,source:'notice',notice_id:101,date:'2026-10-02',amount:'450',display_kind:'stat',mismatch:true}]}});
    }''')
    p.evaluate("ACT.jcPayDlg({dataset:{id:'11'}})")
    p.wait_for_selector('.jc-pay-ref')
    assert p.evaluate('noticeReads') == 1
    assert 'DOC-101' in p.inner_text('.mask')
    p.click('[data-act="closeModal"]')
    p.evaluate('''() => {
      const base=NO[0]; NO=Array.from({length:550},(_,i)=>({...base,id:String(1000+i),code:'DOC-'+i,hasAnyFlow:false}));
      reloadNotices=async()=>{}; fNt.month='全部';fNt.stat='全部';fNt.q=''; VIEW='m03';render();
      window.sourceWasVirtual=VS_TS.length>0;
      fNt.month='2020-01';fNt.stat='未付清';fNt.q='找不到';
      API.m11Detail=async()=>({ok:true,data:{supplier_invoices:[],trade_invoices:[],payments:[],
        payment_display_rows:[{id:55,source:'notice',notice_id:1520,date:'2026-10-02',amount:'450',display_kind:'stat',mismatch:true}]}});
      VIEW='m11';render();
    }''')
    p.evaluate("ACT.jcPayDlg({dataset:{id:'11'}})")
    p.wait_for_selector('.jc-pay-ref')
    assert p.evaluate('sourceWasVirtual')
    assert '与实付不一致' in p.inner_text('.mask')
    assert p.locator('.mask [data-act="jcPayDel"]').count() == 0
    p.click('.jc-pay-ref [data-act="jcPayNotice"]')
    p.wait_for_timeout(500)
    assert p.locator('tr.nt-focus').count(), p.evaluate("({view:VIEW,focus:ntFocusId,vs:VS_TS.length,body:document.body.innerText.slice(-1000)})")
    assert p.evaluate('VIEW') == 'm03'
    assert p.locator('tr.nt-focus').get_attribute('data-notice-id') == '1520'
    assert p.evaluate('fNt.q') == 'DOC-520'
    assert p.evaluate('ntHit(fNt).length') == 1
    box = p.locator('tr.nt-focus').bounding_box()
    assert box and 0 <= box['y'] <= 1000
    p.screenshot(path='.codebuddy/work/00-scratch/tmp-20261011-281-jump.png')
    p.evaluate('''() => {
      FLs=[{id:'31',nid:'1520',date:'2026-10-02',amt:300,method:'现汇',voided:false}];
      reloadM05=async()=>{throw {message:'付款域刷新失败'};};
      API.flowRevoke=async()=>({flow_id:31,status:'revoked',jc_effect:{contract_id:11,before:'450.00',after:'450.00',protected:true}});
      ACT.revDlg({dataset:{fid:'31'}});
    }''')
    p.fill('#rReason', '撤销测试')
    p.click('[data-act="revOk"]')
    p.wait_for_function("document.body.innerText.includes('本次保留人工值')")
    p.wait_for_function("document.body.innerText.includes('部分页面刷新失败')")
    assert '450.00 → 450.00' in p.inner_text('body')
    assert '没能改成' not in p.inner_text('body')
