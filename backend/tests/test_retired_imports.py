"""通用导入不可用；付款、集采与过程资料现行路由继续存在。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mod05_flow.router import router as flow
from app.mod06_proc.router import router as process
from app.mod11_jc.router import router as jc


def test_retired_imports_have_no_catalog_or_http_write_entry(rollback_db):
    from app.core.db import get_session_factory
    from app.mod15_user.models import UserAccount
    with get_session_factory()() as session:
        session.add(UserAccount(account="retirement-guard", name="退役守卫", role="admin", password=""))
        session.commit()
    from app.main import create_app
    app = create_app()
    paths = set(app.openapi()['paths'])
    assert not any(path.startswith('/api/imp/') for path in paths)
    assert {'/api/m06/matrix', '/api/m06/export', '/api/m06/mech',
            '/api/m06/workbench', '/api/m06/workbench/{name}'} <= paths
    from app.core import session as SESS
    with TestClient(app) as client:
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('retirement-guard'))
        assert client.get('/api/imp/domains').status_code == 404
        for domain in ('m04_plan', 'm05_flow', 'm11_jc', 'm06_proc', 'm06_mech_report'):
            for endpoint in ('schema', 'options', 'batches'):
                assert client.get(f'/api/imp/{domain}/{endpoint}').status_code == 404
            for endpoint in ('parse', 'preview', 'commit', 'rollback'):
                assert client.post(f'/api/imp/{domain}/{endpoint}', json={}).status_code == 404
    assert '/api/m05/flows' in paths
    assert any(path.startswith('/api/m11/') for path in paths)


def test_selfcheck_current_routes_and_retired_imports_run_in_powershell(tmp_path):
    """执行自检原块；缺JSON/读取出口或残留旧HTTP入口均须失败。"""
    import json
    from pathlib import Path
    import shutil
    import subprocess
    root = Path(__file__).resolve().parents[2]
    source = (root / 'ops/selfcheck.ps1').read_text(encoding='utf-8-sig')
    block = source.split('# ---- ⑤ 初始化入口的端点 ----', 1)[1].split('if ($script:fail -eq 0)', 1)[0]
    app = FastAPI()
    from app.mod08_inv.router import router as inventory
    for router in (flow, process, jc, inventory):
        app.include_router(router)
    paths = app.openapi()['paths']
    script = tmp_path / 'selfcheck-imports.ps1'
    script.write_text("""param([string]$Fixture)
$Base='http://fixture'
$script:fail=0
function Ok($m) { Write-Output $m }
function Bad($m) { $script:fail++; Write-Output $m }
function Skip($m) { Write-Output $m }
function Invoke-WebRequest {
    param($Uri)
    $raw=[IO.File]::ReadAllText($Fixture)
    if ($Uri -eq ($Base + '/openapi.json')) { return @{Content=$raw} }
    $data=$raw | ConvertFrom-Json
    return @{StatusCode=[int]$data.retired_status}
}
""" + block + '\nexit $script:fail\n', encoding='utf-8-sig')
    shell = shutil.which('powershell')
    assert shell, 'PowerShell未找到，无法验证自检逻辑'
    cases = [(None, None, 404), ('/api/m06/matrix', None, 404),
             ('/api/m06/workbench/{name}', None, 404),
             (None, '/api/imp/m06_proc/parse', 404), (None, None, 405)]
    for missing, legacy, status in cases:
        current = {k: v for k, v in paths.items() if k != missing}
        if legacy:
            current[legacy] = {'post': {}}
        fixture = tmp_path / 'openapi.json'
        fixture.write_text(json.dumps({'paths': current, 'retired_status': status}), encoding='utf-8')
        result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(script), str(fixture)], capture_output=True, timeout=30)
        expected = 0 if missing is None and legacy is None and status == 404 else 1
        assert (result.returncode == 0) == (expected == 0), result.stdout.decode('utf-8', errors='replace')
