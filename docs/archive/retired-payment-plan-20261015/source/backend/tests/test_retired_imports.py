"""退役的是导入入口；付款、集采正常路由及两项现行导入继续存在。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.import_kit.api import domains_router
from app.mod04_plan.router import router as plan
from app.mod05_flow.router import router as flow
from app.mod06_proc.router import router as process
from app.mod11_jc.router import router as jc
from tests.acc_plugin import acc


@acc()
def test_retired_imports_have_no_catalog_or_http_write_entry():
    app = FastAPI()
    for router in (plan, flow, process, jc, domains_router()):
        app.include_router(router)
    with TestClient(app) as client:
        domains = {d['domain'] for d in client.get('/api/imp/domains').json()['domains']}
        assert {'m04_plan', 'm06_proc', 'm06_mech_report'} <= domains
        assert not domains & {'m05_flow', 'm11_jc'}
        for domain in ('m05_flow', 'm11_jc'):
            for endpoint in ('schema', 'options', 'batches'):
                assert client.get(f'/api/imp/{domain}/{endpoint}').status_code == 404
            for endpoint in ('parse', 'preview', 'commit', 'rollback'):
                assert client.post(f'/api/imp/{domain}/{endpoint}', json={}).status_code == 404
        for domain in ('m04_plan', 'm06_proc', 'm06_mech_report'):
            assert client.get(f'/api/imp/{domain}/schema').status_code == 200
        paths = set(client.get('/openapi.json').json()['paths'])
    assert '/api/m05/flows' in paths
    assert any(path.startswith('/api/m11/') for path in paths)
