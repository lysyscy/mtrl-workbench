"""290 项目内序号、合同编号及所见导出；测试库回滚和隔离浏览器。"""
from pathlib import Path
from io import BytesIO
import openpyxl
from app.core.db import session_scope
from app.mod11_jc import repository as R, service as S, domain as D
from tests.test_acc_jc_pay_link import _project
from tests.test_shell_ui_workflow import ui_page  # noqa: F401
from tests.acc_plugin import acc


def dataset():
    with session_scope() as s:
        a=_project(s,'__自检仓_290_A__'); b=_project(s,'__自检仓_290_B__')
        aa=[R.insert_contract(s,project_id=a.id,contract_date=dt,material_name='材料'+str(i),supplier='供应商'+str(i),contract_amt=10+i) for i,dt in enumerate(['2026-01-01','2026-01-01','2026-03-01',''])]
        bb=[R.insert_contract(s,project_id=b.id,contract_date='2026-01-01',material_name='乙材料') for _ in range(2)]
        aa[2].contract_no='00CGHT前导';s.flush()
        def read(): return {r['id']:r for r in S.build_list(s)['rows']}
        rows=read()
        assert [rows[c.id]['project_seq'] for c in aa]==[1,2,3,4]
        assert [rows[c.id]['project_seq'] for c in bb]==[1,2]
        assert S.build_list(s,supplier='供应商2',project_key=a.warehouse_name)['rows'][0]['project_seq']==3
        R.set_tag(s,aa[1].id,'不纳入');rows=read()
        assert [rows[c.id]['project_seq'] for c in aa]==[1,None,2,3]
        R.set_tag(s,aa[1].id,'纳入台账');rows=read()
        assert [rows[c.id]['project_seq'] for c in aa]==[1,2,3,4]
        ws=openpyxl.load_workbook(BytesIO(S.export_xlsx(s,ids=[aa[2].id,aa[0].id]))).active
        assert [c.value for c in ws[1]][:7]==['序号','合同日期','材料名','合同编号','供应商','合同金额','发票金额']
        assert ws['A2'].value==3 and ws['D2'].value=='00CGHT前导' and ws['A3'].value==1
        assert ws['D3'].value=='—'
        assert ws['F2'].value==12 and ws['F3'].value==10 and ws['F4'].value==22
        assert ws['F2'].number_format=='General' and ws['F2'].data_type=='n'
        assert ws.max_column==18
        filtered=S.build_list(s,supplier='供应商2',project_key=a.warehouse_name)['rows']
        data=[{k:(str(v) if k in D.SUM_KEYS else v) for k,v in rows[c.id].items()} for c in aa+bb]
        print('DB/xlsx PASS: A=1,2,3,4 B=1,2; excluded=None; filter=3; cells/order/19columns/format/total=22')
        s.rollback()
        return data


@acc()
def test_project_sequence_and_xlsx():
    dataset()


@acc()
def test_browser_sequence_columns_and_export(ui_page):
    data=dataset()
    # ⭐ `TAIL-298`：表头由**后端列清单**现生成 ⇒ 本用例替身也必须把列清单放进去
    #   （⛔ 别在测试里另抄一份 20 列 —— 那正是本票要治的第二份口径；直接取域内核那张）。
    cols=[{k:c[k] for k in ('key','label','type')} for c in D.JC_COLUMNS]
    p=ui_page
    from app.mod03_notice.page import render_theme
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate('''arg=>{JC_COLUMNS.splice(0,JC_COLUMNS.length,...arg.cols);JC_SUM_KEYS.splice(0,JC_SUM_KEYS.length,...arg.sum_keys);JCs.splice(0,JCs.length,...arg.rows.map(adaptJc));VIEW='m11';fJc.tag='全部';fJc.arch='全部';fJc.sup='';render();}''',{'rows':data,'cols':cols,'sum_keys':list(D.SUM_KEYS)})
    print(p.evaluate('({filter:fJc,rows:jcVisible().map(j=>j.projectSeq)})'))
    assert p.locator('table[data-sort-key="m11:jc"] th').count()==20
    assert p.locator('table[data-sort-key="m11:jc"] th').nth(8).is_hidden()
    p.click('#jcTradeBtn')
    assert p.locator('table[data-sort-key="m11:jc"] th').nth(8).is_visible()
    p.evaluate("render()")
    assert p.locator('table[data-sort-key="m11:jc"] th').nth(8).is_visible()
    p.evaluate("fJc.sup='供应商2';render()")
    assert p.locator('table[data-sort-key="m11:jc"] tbody tr').first.locator('td').nth(1).inner_text()=='3'
    assert p.locator('table[data-sort-key="m11:jc"] tbody tr').first.locator('td').nth(4).inner_text()=='00CGHT前导'
    p.evaluate("SORT['m11:jc']={i:1,d:-1};render()")
    assert p.locator('table[data-sort-key="m11:jc"] tbody tr').first.locator('td').nth(1).inner_text()=='3'
    print('Browser PASS: filter/sort/redraw=3, contractNo exact; default hidden/toggle retained')
    p.evaluate("() => {fJc.sup='';SORT['m11:jc']={i:1,d:-1};render();API.m11Export=async b=>{window.exportIds=b.ids;return {ok:false,message:'隔离出口'};};}")
    expected=p.locator('table[data-sort-key="m11:jc"] [data-act="jcPick"]').evaluate_all('(els)=>els.map(x=>Number(x.dataset.id))')
    p.evaluate('ACT.jcExport()')
    assert p.evaluate('exportIds')==expected
    p.evaluate('''arg=>{
      window.contractRows=arg.rows;
      const r=arg.rows.find(x=>x.contract_no==='00CGHT前导');
      r.notice_ids=[101];
      JCs.splice(0,JCs.length,...arg.rows.map(adaptJc));
      PJs.splice(0,PJs.length,{id:'1',type:'normal',name:r.project_key,disp:'测试项目',full:'测试项目全名',status:'在建',phid:'1',kw:''});
      NO[0].sup=r.supplier;
      API.m11Detail=async()=>({ok:true,data:{}});
      API.m11List=async()=>({rows:contractRows,columns:arg.cols,sum_keys:arg.sum_keys});
      API.flows=async()=>({rows:[]});
    }''',{'rows':data,'cols':cols,'sum_keys':list(D.SUM_KEYS)})
    identity=p.evaluate("JCs.find(j=>j.contractNo==='00CGHT前导').id")
    for act in ['jcInvDlg','jcTInvDlg','jcPayDlg']:
        p.evaluate('(args)=>ACT[args.act]({dataset:{id:args.id}})',{'act':act,'id':identity})
        assert '序号 3 · 合同编号 00CGHT前导' in p.locator('#modalRoot h3').inner_text()
        p.evaluate('closeModal()')
    p.evaluate("ACT.jcLink({dataset:{id:'101'}})")
    assert '序号 3 · 合同编号 00CGHT前导' in p.locator('#jcLinkId').inner_text()
    p.evaluate('closeModal()')
    p.evaluate("ACT.ntTrace({dataset:{id:'101'}})")
    assert '项目内序号' in p.locator('.mb').inner_text() and '00CGHT前导' in p.locator('.mb').inner_text()
