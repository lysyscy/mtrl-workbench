"""Authorized stop/sync/start, with restart in finally and read-only health check."""
from pathlib import Path
import subprocess
import time
import urllib.request

root = Path('D:/dev/mtrl-workbench')
logs = root / '.scratch/uv-dependency-cleanup'
cache = root / '.scratch/local/uv-audit-cache'

def run(args, name):
    result = subprocess.run(args, cwd=root, capture_output=True, encoding='utf-8', timeout=40)
    (logs / name).write_text(result.stdout + result.stderr, encoding='utf-8')
    print(result.stdout, result.stderr, flush=True)
    result.check_returncode()
    return result.stdout

service = ['pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', 'ops/server_ctl.ps1']
try:
    run(service + ['-Action', 'stop'], 'service-stop.log')
    state = run(['pwsh', '-NoProfile', '-Command', "(Get-Service -Name mtrl-workbench-server).Status.ToString()"], 'service-stopped-check.log')
    assert state.strip() == 'Stopped'
    run(['uv', 'sync', '--locked', '--offline', '--project', 'backend', '--cache-dir', str(cache)], 'project-sync-complete.log')
finally:
    run(service + ['-Action', 'start'], 'service-start.log')

for attempt in range(20):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/app', timeout=3) as response:
            assert response.status == 200 and len(response.read()) > 100
        break
    except (OSError, AssertionError):
        if attempt == 19:
            raise
        time.sleep(1)
run(service + ['-Action', 'status'], 'service-status-final.log')
run(['uv', 'pip', 'check', '--python', 'backend/.venv/Scripts/python.exe', '--cache-dir', str(cache)], 'project-pip-check-final.log')
run(['uv', 'sync', '--locked', '--offline', '--dry-run', '--project', 'backend', '--cache-dir', str(cache)], 'project-sync-dry-run-final.log')
print('PASS: service restarted, /app 200, dependency check and synchronization passed')
