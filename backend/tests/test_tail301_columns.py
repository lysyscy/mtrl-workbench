"""守TAIL-301：加列/调序后真实行格与合计仍按列id对齐，API合计身份来自域内核。"""
from copy import deepcopy
from contextlib import nullcontext
from starlette.requests import Request

from app.mod11_jc import domain as D, repository as R, service as S, api as A


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
