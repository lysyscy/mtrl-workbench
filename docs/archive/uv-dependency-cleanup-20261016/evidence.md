# uv 依赖精简与迁移收尾

2026-10-16；来源为本对话依赖审计及用户要求接续收尾。只负责依赖配置、安装入口、相关检查和说明，不改业务代码。

## 已完成

- 原有 pyproject.toml、uv.lock 迁移继续使用；uvicorn[standard] 改为 uvicorn + httptools，保留实际 HTTP 解析加速。
- requests 移入 dev，保留旧一次性工具用途；starlette 为测试直接使用，登记在 dev。
- pycryptodomex 移除重复直接声明，仍由 gmssl 间接安装。
- 移除 filelock、pluggy 的迁移临时约束；重新解析未升级任何保留包。锁文件从79条降为75条，移除 pyyaml、watchfiles、websockets，以及本机不安装的 uvloop。
- 部署指南明确 backend 工作目录、uv add/remove/run/sync 及开发/运行分组；结构量测工具切换到 pyproject.toml、uv.lock。

## 验证

- 候选环境由 uv sync --locked 从官方 PyPI 创建：74包，日志 candidate-sync.log。
- 隔离环境7个相关测试文件45项通过，见 pytest-final.log、pytest-results.json。覆盖依赖声明/索引、Excel读取、打印通道分流与模板、文件导出、pandas模板显示。
- 首次测试的11个错误均为沙箱默认临时目录无法创建；指定本任务 --basetemp 后同一选集通过。原始失败保留 pytest.log。
- 候选环境 uv sync --locked --no-dev 后仅45个运行包。runtime_smoke.py 在该环境验证合成 multipart 上传、httptools自动选择、无WebSocket实现、Excel/pandas、离线PDF，以及数据库/加密/打印驱动导入通过；见 runtime-smoke.log。无业务登录、数据库连接、真实报表或打印。第一次沙箱渲染进程超时，正常权限离线复验通过；TestClient出现既有httpx弃用提示，本轮不新增httpx2。
- PowerShell部署脚本语法和仓内路径全部通过，见 powershell-check.log。默认Windows PowerShell首次受执行策略限制，改用pwsh执行同一检查通过。
- uv lock --check --offline 通过；git diff --check 通过。

## 本机环境同步与加载

uv sync --locked 已尝试，但运行中的项目Python进程8128占用watchfiles和websockets原生模块，退出2；部分卸载已发生。日志 project-check-0.log、project-sync-final.log。随后从本机 uv archive 缓存中核对原版本及 cp315 wheel，仅补回72个缺失原文件，不覆盖已有或占用文件；本机恢复77包，uv pip check退出0，见 project-restored-check.log。不存在以部分卸载状态交付的问题，但本机环境仍保留待移除的三个旧包。

用户随后明确授权“允许停服同步并启动”。按既有 server_ctl.ps1 停止服务，独立确认 Stopped 后执行 uv sync --locked --offline，成功卸载 pyyaml、watchfiles、websockets，立即启动服务。最终服务 Running，GET /app=200；74包 uv pip check 通过，uv sync --locked --offline --dry-run 显示 Would make no changes，见 service-*.log、project-sync-complete.log、project-pip-check-final.log、project-sync-dry-run-final.log。重启同时加载工作区既有后端改动，不把本次健康检查说成这些业务改动已重新验收。

当前更改保存于工作区，尚未提交或推送，避免混入大量其他活动改动。隔离候选环境、pytest临时文件及本轮临时uv缓存按精确绝对路径普通删除，清理回执见 cleanup.log；检查脚本和日志保留用于复现与追溯。

未做完整业务回归、漏洞数据库扫描或真实业务写入；现有其他修改保留，未提交或推送。已完成配置、隔离验证、本机环境同步和授权服务加载，实体打印和实际业务操作仍未验证。
