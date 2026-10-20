"""守TAIL-301：加列/调序后真实行格与合计仍按列id对齐，API合计身份来自域内核。"""
from copy import deepcopy
from contextlib import nullcontext
from starlette.requests import Request

from app.mod11_jc import domain as D, repository as R, service as S, api as A
from tests.ui_helpers import ui_page  # noqa: F401


def test_sum_keys_from_domain(monkeypatch):
    for name in ('list_contracts', 'project_choices'):
        monkeypatch.setattr(R, name, lambda *a, **kw: [])
    for name in ('invoices_of_many', 'payments_of_many'):
        monkeypatch.setattr(R, name, lambda *a, **kw: {})
    monkeypatch.setattr(D, 'SUM_KEYS', (*D.SUM_KEYS, 'extra_amt'))
    assert S.build_list(None)['sum_keys'] == list(D.SUM_KEYS), 'sum_keys must follow domain.SUM_KEYS'
    monkeypatch.setattr(A, 'session_scope', lambda: nullcontext(None))
    result=A.api_list(Request({'type':'http','query_string':b''}))
    assert result.get('sum_keys') == list(D.SUM_KEYS), 'API must forward sum_keys'


def _rows():
    return [dict(id=1, project_key='测试仓库', project_seq=1, date='2026-10-01', material='甲材料',
                 contract_no='001合同', supplier='甲供应商', contract_amt='100.25', inv_sum='70.15',
                 trade_co='贸易甲', trade_contract_amt='200.55', trade_inv_sum='150.35', settle='150.35',
                 pay_sum='30.05', debt='120.30', method='转账', remark='备注甲', tag='纳入台账',
                 arch='已存档', arch_no='档001', ret_date='2026-10-02', extra_text='<新增列>', extra_amt='9.25'),
            dict(id=2, project_key='测试仓库', project_seq=None, date='2026-10-03', material='乙材料',
                 contract_no='', supplier='乙供应商', contract_amt='20.75', inv_sum='10.25',
                 trade_co='', trade_contract_amt=None, trade_inv_sum='0', settle='10.25',
                 pay_sum='40.10', debt='-29.85', method='', remark='', tag='不纳入',
                 arch='未存档', arch_no='', ret_date='', extra_text='乙新增', extra_amt='0.75')]


def _load(p, mode):
    cols=deepcopy(list(D.JC_COLUMNS))
    sums=list(D.SUM_KEYS)
    if mode == 'reorder':
        # 保留钉列连续前缀，只调后面的业务列；排序内核不参与本票。
        cols[3:]=reversed(cols[3:])
    if mode == 'insert':
        cols[4:4]=[dict(key='extra_text',label='新增文本',type='text'),
                   dict(key='extra_amt',label='新增金额',type='num')]
        sums.append('extra_amt')
    p.evaluate('''async arg => {
      API.m11List=async()=>arg;
      VIEW='m11'; fJc.tag='全部';fJc.arch='全部';fJc.sup='';fJc.proj='全部';
      delete SORT['m11:jc']; await reloadM11();
    }''', dict(rows=_rows(), columns=cols, sum_keys=sums))
    return p.locator('table[data-sort-key="m11:jc"]'), [c['key'] for c in cols]


def test_rows_follow_columns(ui_page):
    p=ui_page
    table,keys=_load(p,'base')
    cells=table.locator('tbody tr').first.locator('td')
    originals=dict(zip(keys,cells.evaluate_all('(xs)=>xs.slice(1).map(x=>x.outerHTML)')))
    assert '001合同' in originals['contract_no'] and '150.35' in originals['settle']
    assert 'jcPayDlg' in originals['pay_sum'] and 'jcMaterialOpen' in originals['material']
    for mode in ('reorder','insert'):
        table,keys=_load(p,mode)
        assert table.locator('thead th').count() == 1+len(keys)
        actual=table.locator('tbody tr').first.locator('td').evaluate_all('(xs)=>xs.slice(1).map(x=>x.outerHTML)')
        assert len(actual)==len(keys), 'row cells must follow column count'
        for key,html in zip(keys,actual):
            expected=originals.get(key, {'extra_text':'<td>&lt;新增列&gt;</td>',
                                       'extra_amt':'<td class="num">9.25</td>'}.get(key))
            assert html==expected, f'row cell must follow column id: {key}'


def test_sums_follow_column_ids(ui_page):
    totals=dict(contract_amt='121.00',inv_sum='80.40',trade_contract_amt='200.55',
                trade_inv_sum='150.35',settle='160.60',pay_sum='70.15',debt='90.45',extra_amt='10.00')
    for mode in ('base','reorder','insert'):
        table,keys=_load(ui_page,mode)
        cells=table.locator('tr.sumrow td').all_inner_texts()
        assert len(cells)==len(keys)+1 and cells[0]=='合计'
        for key,text in zip(keys,cells[1:]):
            expected=totals[key] if key in D.SUM_KEYS or key=='extra_amt' else ''
            assert text==expected, f'sum must follow column id: {key}: {text} != {expected}'
