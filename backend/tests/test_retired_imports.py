"""退役的是导入入口；付款、集采正常路由及两项现行导入继续存在。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.import_kit.api import domains_router
from app.mod05_flow.router import router as flow
from app.mod06_proc.router import router as process
from app.mod11_jc.router import router as jc


def test_retired_imports_have_no_catalog_or_http_write_entry():
    app = FastAPI()
    for router in (flow, process, jc, domains_router()):
        app.include_router(router)
    with TestClient(app) as client:
        domains = {d['domain'] for d in client.get('/api/imp/domains').json()['domains']}
        assert {'m06_proc', 'm06_mech_report'} <= domains
        assert not domains & {'m04_plan', 'm05_flow', 'm11_jc'}
        for domain in ('m04_plan', 'm05_flow', 'm11_jc'):
            for endpoint in ('schema', 'options', 'batches'):
                assert client.get(f'/api/imp/{domain}/{endpoint}').status_code == 404
            for endpoint in ('parse', 'preview', 'commit', 'rollback'):
                assert client.post(f'/api/imp/{domain}/{endpoint}', json={}).status_code == 404
        for domain in ('m06_proc', 'm06_mech_report'):
            assert client.get(f'/api/imp/{domain}/schema').status_code == 200
        paths = set(client.get('/openapi.json').json()['paths'])
    assert '/api/m05/flows' in paths
    assert any(path.startswith('/api/m11/') for path in paths)


def test_selfcheck_current_import_domains_run_in_powershell(tmp_path):
    """执行自检⑤原代码；任一现行域缺失必须计失败。"""
    import json
    from pathlib import Path
    import shutil
    import subprocess
    root=Path(__file__).resolve().parents[2]
    source=(root/'ops/selfcheck.ps1').read_text(encoding='utf-8-sig')
    block=source.split('# ---- ⑤ 初始化入口的端点 ----',1)[1].split("if ($script:fail -eq 0)",1)[0]
    app=FastAPI()
    from app.mod08_inv.router import router as inventory
    for router in (flow,process,jc,inventory):app.include_router(router)
    paths=app.openapi()['paths']
    script=tmp_path/'selfcheck-imports.ps1'
    script.write_text("""param([string]$Fixture)
$script:fail=0
function Ok($m) { Write-Output $m }
function Bad($m) { $script:fail++; Write-Output $m }
function Skip($m) { Write-Output $m }
function Invoke-WebRequest { return @{Content=[IO.File]::ReadAllText($Fixture)} }
"""+block+"\nexit $script:fail\n",encoding='utf-8-sig')
    shell=shutil.which('powershell')
    assert shell, 'PowerShell未找到，无法验证自检逻辑'
    for missing in (None,'m06_proc','m06_mech_report'):
        fixture=tmp_path/'openapi.json'
        fixture.write_text(json.dumps({'paths':{k:v for k,v in paths.items()
            if missing is None or not k.startswith('/api/imp/'+missing+'/')}}),encoding='utf-8')
        result=subprocess.run([shell,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
            '-File',str(script),str(fixture)],capture_output=True,timeout=30)
        assert result.returncode==(0 if missing is None else 1),result.stdout.decode('utf-8',errors='replace')
