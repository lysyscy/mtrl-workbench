"""报告 C 的等价收口：读取 interface 与真实入口的结果，业务差异仍在各页。"""
from contextlib import nullcontext

from starlette.datastructures import QueryParams
from starlette.requests import Request

from app.core.query import flatten_query, query_one
from app.mod06_proc import router as proc_router, service as proc
from app.mod07_setl import api as setl_api, service as setl
from app.mod08_inv import service as inv
from app.mod09_fee import api as fee_api, service as fee
from app.mod11_jc import api as jc_api


def request(query):
    return Request({'type': 'http', 'query_string': query.encode()})


def test_single_value_contract():
    assert query_one(None, 'x', 'default') == 'default'
    for raw, expected in [(0, '0'), (False, 'False'), (None, ''), ('  ', ''),
                          ([], ''), ((), ''), ([None, 'second'], ''),
                          ([0, 'second'], '0'), ((' first ', 'second'), 'first')]:
        assert query_one({'x': raw}, 'x', 'default') == expected


def test_flatten_keeps_empty_order_and_duplicates():
    p = flatten_query(QueryParams('x=&x=0&x=0&x=%20a%20&single=%20a%20&empty='))
    assert p == {'x': ['', '0', '0', ' a '], 'single': ' a ', 'empty': ''}
    assert flatten_query(QueryParams('')) == {}


def test_page_defaults_validation_and_explicit_empty(monkeypatch):
    monkeypatch.setattr(setl.D, 'default_month', lambda: '2026-09')
    monkeypatch.setattr(fee.D, 'default_ym', lambda: '2026-09')
    monkeypatch.setattr(inv, 'default_period', lambda table: '2026-09')
    assert setl.parse_state() == {'period': '2026-09', 'explicit': False}
    assert setl.parse_state({'period': ['0', '2026-09']}) == {'period': '0', 'explicit': True}
    assert setl.parse_extract_state()['period'] == '2026'
    assert setl.parse_extract_state({'ext_period': None})['period'] == ''
    assert setl.parse_extract_state({'status': 'invalid'})['status'] == setl.X.STATUS_DEFAULT
    assert fee.parse_state({'ym': '2026-13', 'pj': [0, 'other']}) == {'ym': '2026-09', 'project': '0'}
    assert fee.parse_state({'ym': '', 'pj': None}) == {'ym': '2026-09', 'project': ''}
    assert inv.parse_state({'period': 'invalid', 'dir': 'invalid', 'only_adj': 0})['period'] == 'invalid'
    assert inv.parse_state()['period'] == '2026-09'
    st = proc.parse_state({'pj': [0, 'other'], 'tab': 0, 'expopen': 0})
    assert st['warehouse'] == '0' and st['exp_open'] and st['exp_touched']


def test_multivalue_business_differences():
    raw = [' a ', 'a', '', None, 0]
    assert proc.parse_state({'exppj': raw})['exp_selected'] == ['a']
    assert inv.parse_state({'pj': raw})['projects'] == ('a', 'a', 'None', '0')
    st = inv.parse_state({'f_amount_min': 0, 'f_amount_max': [0, 9]})
    assert st['col_filters']['amount'] == {'min': '0', 'max': '0'}
    assert proc_router._one({'x': 0}, 'x') == ''
    assert jc_api._tags(['invalid', *jc_api.D.TAGS]) == list(jc_api.D.TAGS)


def test_actual_settlement_and_fee_entries(monkeypatch):
    monkeypatch.setattr(setl_api, 'session_scope', lambda: nullcontext(None))
    def page(s, st):
        assert st == {'period': '2026-02', 'explicit': True}
        return {'ym': st['period'], 'rows': [], 'counts': {}, 'balance_ok': False}
    monkeypatch.setattr(setl, 'build_page_data', page)
    assert setl_api.api_settlement(request('period=2026-02&period=2026-03'))['ym'] == '2026-02'
    monkeypatch.setattr(fee_api, 'session_scope', lambda: nullcontext(None))
    monkeypatch.setattr(fee_api, '_payload', lambda s, **kw: kw)
    assert fee_api.api_fee(request('ym=2026-02&pj=a&pj=b')) == {'ym': '2026-02', 'pj': "['a', 'b']"}


def test_actual_proc_export_and_jc_entries(monkeypatch):
    from app import export_registry
    from app.core.errors import MustReportError
    monkeypatch.setattr(proc_router, 'session_scope', lambda: nullcontext(None))
    class Export:
        def export_proc(self, s, keys, tab, ym):
            assert keys == ['a', 'b'] and ym == '2026-02'
            raise MustReportError('隔离导出测试')
    monkeypatch.setattr(export_registry, 'get', lambda key: Export())
    result = proc_router.api_proc_export(request('projects=a,b&projects=c&ym=2026-02'))
    assert result.status_code == 200 and '隔离导出测试' in result.body.decode()
    monkeypatch.setattr(jc_api, 'session_scope', lambda: nullcontext(None))
    def build(s, **kw):
        assert kw == {'tags': [], 'arch': "['a', 'b']", 'supplier': ' x ', 'project_key': '0'}
        return {'rows': [], 'count': 0, 'totals': {}, 'columns': [], 'sum_keys': [], 'projects': []}
    monkeypatch.setattr(jc_api.SV, 'build_list', build)
    assert jc_api.api_list(request('tag=invalid&arch=a&arch=b&supplier=%20x%20&project=0'))['count'] == 0


def test_actual_big_and_extract_export_entries(monkeypatch):
    from app import export_registry
    from app.core.errors import MustReportError
    monkeypatch.setattr(setl_api, 'session_scope', lambda: nullcontext(None))
    def big(s, st):
        assert st['month'] == '2026-02' and st['explicit']
        return {'month': st['month'], 'selected': [], 'candidates': [], 'rows': [], 'totals': {}, 'mat_available': False}
    monkeypatch.setattr(setl_api.BS, 'build_big_data', big)
    monkeypatch.setattr(setl_api, 'load_manual', lambda s: {})
    assert setl_api.api_big(request('period=2026-02&period=2026-03'))['month'] == '2026-02'
    calls = []
    class Export:
        def export_extract(self, s, period, status):
            calls.append((period, status))
            raise MustReportError('隔离导出测试')
    monkeypatch.setattr(export_registry, 'get', lambda key: Export())
    for query in ['', 'period=', 'period=2026-02&period=2026-03']:
        assert setl_api.api_export_extract(request(query)).status_code == 200
    assert calls == [(None, ''), ('', ''), ('2026-02', '')]
