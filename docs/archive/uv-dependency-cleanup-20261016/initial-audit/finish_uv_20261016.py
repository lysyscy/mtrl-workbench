"""Archived uv migration edits; historical evidence, not a current entry point."""
from pathlib import Path

def change(name, old, new):
    p = Path(name)
    raw = p.read_bytes()
    newline = '\r\n' if b'\r\n' in raw else '\n'
    text = raw.decode('utf-8').replace('\r\n', '\n')
    assert text.count(old) == 1, name
    p.write_bytes(text.replace(old, new).replace('\n', newline).encode('utf-8'))

change('backend/pyproject.toml', '    "uvicorn[standard]",', '    "uvicorn",\n    "httptools",')
change('backend/pyproject.toml', '    "requests",\n', '')
change('backend/pyproject.toml', '    "pycryptodomex",\n', '')
change('backend/pyproject.toml', '    "pip-audit",\n', '    "pip-audit",\n    "requests",\n    "starlette",\n')
change('backend/pyproject.toml', '# Keep the already deployed transitive versions while migrating lock formats.\nconstraint-dependencies = [\n    "filelock==4.1.1",\n    "pluggy==1.6.0",\n]\n', '')
change('tools/oneoff/_struct_scan.py', 'REPO / "backend" / "alembic.ini", REPO / "backend" / "requirements.txt",\n             REPO / "backend" / "requirements-dev.txt", REPO / "backend" / "pyproject.toml",', 'REPO / "backend" / "alembic.ini", REPO / "backend" / "uv.lock",\n             REPO / "backend" / "pyproject.toml",')
change('docs/guides/deployment.md', '开发用 `uv sync`；目标机重建 venv 用 `uv sync --locked --no-dev`。不要维护 requirements 或 venv 级 pip.ini 副本。', '命令在 `backend/` 执行，或从仓根加 `--project backend`。开发用 `uv sync --locked`；目标机重建 venv 用 `uv sync --locked --no-dev`。不要维护 requirements 或 venv 级 pip.ini 副本。')
change('docs/guides/deployment.md', '新增依赖后仍运行pip-audit并保存审计报告；', '运行依赖用 `uv add/remove` 维护，开发工具用 `uv add --dev`；提交声明与锁文件，日常用 `uv run --locked` 调用项目命令。Uvicorn 使用基础包加 `httptools`，保留 HTTP 加速；当前不启用 WebSocket、热重载及 YAML 日志配置。`pycryptodomex` 由 `gmssl` 间接安装；`requests` 仅在开发组保留旧工具用途，测试直接使用的 `starlette` 同时登记在开发组。新增依赖后仍运行pip-audit并保存审计报告；')
