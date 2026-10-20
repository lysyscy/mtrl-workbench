"""Plan application routes retire while skill audit and normal payment remain."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.mod03_notice.notice_pay_actions import default_pay_method
from tests.shell_src import SHELL


def test_plan_page_import_and_write_routes_retire_audit_api_stays():
    app=create_app()
    paths=set(app.openapi()['paths'])
    assert not any(p.startswith(('/api/m04','/m04','/api/imp/m04_plan')) for p in paths)
    assert '/api/m03/plan-audit/snapshot' in paths
    assert '/api/m03/plan-audit/methods' in paths
    client=TestClient(app)
    domains={x['domain'] for x in client.get('/api/imp/domains').json()['domains']}
    assert domains=={'m06_proc','m06_mech_report'}
    assert 'V.m04=' not in SHELL and 'data-act="planPick"' not in SHELL
    assert "['m04','付款计划','MOD-04']" not in SHELL
    assert 'API.plans(' not in SHELL and 'PLs.find(' not in SHELL
    assert default_pay_method('供应链')=='供应链'
    assert default_pay_method('')=='现汇'
    source=Path(__file__).parents[1]/'app/mod03_notice/notice_pay_actions.py'
    assert 'app.mod04_plan' not in source.read_text(encoding='utf-8')
