# 部署、配置与服务加载

现行服务入口为 ops/server_ctl.ps1，部署脚本与参数以 ops 中实际文件为准。先核所在工作树、目标服务、进程命令行、启动时间和资源目录，分支隔离不等于浏览器发布隔离。源码提交、服务已加载和业务验收是三个事实。

## 只读定位与有权操作

从仓根运行 `powershell -NoProfile -ExecutionPolicy Bypass -File ops/server_ctl.ps1 -Action status`，按症状选 log/port/pg。这些分支查服务/进程/日志/GET /app，不启停或写库。start/stop/restart 须当次明确授权及管理员权限，结束再核 PID、探活与受影响行为。服务没有 --reload，Python 改动可能需加载，但这不构成重启授权。

ops/nssm_install.ps1 注册 mtrl-workbench-server，nssm_uninstall.ps1 退出注册，不能同时让旧计划任务抢应用端口。脚本中的当前命令、依赖服务名、路径与端口优先于历史机器记录。NSSM 二进制按 .gitignore 不入 Git；服务操作用 NSSM/PowerShell cmdlet，计划任务用 ScheduledTask cmdlet。

## 配置主人

| 配置 | 当前出口与生效 |
|---|---|
| i8 地址、两个打印版式 ID | 页面写库，经 app_settings.effective 取值，保存清缓存 |
| 打印机 IPP 地址、PRINT_MODE/PRINTER_NAME | 页面入口写仓根 .env 并清缓存 |
| 数据库、账号口令、SESSION_SECRET、访问范围及其余启动项 | 仓根 .env，键名/默认值读 .env.example 与 core/config.py；启动时读取 |

真实 .env、账号会话和私有恢复材料不提交；不能把示例当现场配置。配置更新后是否需要新进程按实际缓存/加载入口判断，需重启时另依授权操作。

服务以 LocalSystem 等身份运行时看不到普通用户的 Playwright 缓存。机器级浏览器位置可用 C:/ProgramData/ms-playwright，PLAYWRIGHT_BROWSERS_PATH 在服务和验证子进程中都应可达；环境变量变化仅作用新进程。抓取成功不能证明浏览器导出可用，需按目标身份核实际导出。模板、MiSans 字体和授权文件属于运行资源，不能随文档删除。

## 安装、升级与恢复的不同动作

首次空库安装用 ops/deploy_restore.ps1：先准备真实仓、Python/PG/NSSM/浏览器及私有配置，确认应用角色与两个目标库不存在，必要步骤非零即停。它负责环境/建库/迁移/服务，不负责源码下载或已有数据恢复。selfcheck 的 Skip 仍未验证，退出0不能证明整机恢复。

已有库升级仅 schema 变化时走 Alembic 并核开发/测试两库结构；纯文档/模块位置变化不触发 upgrade。隔离目标和实际 engine 未核实前不执行写入检查。数据恢复另读 [数据库备份](database-backup.md)，先在隔离空库验证再考虑替换，恢复不能用全仓 hard reset。

依赖声明和唯一锁是 backend/pyproject.toml、backend/uv.lock，官方 PyPI 来源沿配置；部署 `uv sync --locked --no-dev`，开发用 `uv sync --locked`/`uv run --locked`。新增依赖同时更新声明/锁，按实际风险做已有审计，不恢复旧 requirements 或 venv 私有索引副本。ops/init_db.sql 按既有用户裁定保留，不因此扩大凭据公开。

## 预览副本升级与完整前端切换

新建真实副本先在只读一致来源下核版本，目标迁到兼容来源结构，核复制计数/内容和序列后，仅升级目标到所需版本。已有登记可写试用副本先准备必要恢复点并核目标，只迁移自身，不重拷正式库覆盖用户修改；冻结历史性能副本保原版本与指纹，不为最新产品迁移。具体操作回[预览指南](frontend-preview.md)。

前端切换先处理未保存编辑并记录数据、后端与完整构建身份，停止旧实例后切完整资源目录，再核索引/版本资源、缺失资源404、深链及真实下载。回退保留当前数据库和正常业务写入，只恢复上一套完整前端资源与入口，不能以旧数据库备份撤回正常业务。
