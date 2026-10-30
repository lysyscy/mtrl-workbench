# 部署、配置与服务加载

现行服务入口为 ops/server_ctl.ps1，部署脚本与参数以 ops 中实际文件为准。先核所在工作树、目标服务、进程命令行、启动时间和资源目录，分支隔离不等于浏览器发布隔离。源码提交、服务已加载和业务验收是三个事实。

## 只读定位与有权操作

从仓根运行 `powershell -NoProfile -ExecutionPolicy Bypass -File ops/server_ctl.ps1 -Action status`，按症状选 log/port/pg。这些分支查服务/进程/日志/GET /app，不启停或写库；系统未提供监听进程信息时保留未知，结合HTTP结果判断。start/stop/restart/publish须当次明确授权；start/stop要求管理员令牌，restart/publish由统一编排调用标准UAC。失败返回非零，结束再核实际服务、资源与受影响行为。服务没有 --reload，Python改动可能需加载，但这不构成重启授权。

ops/nssm_install.ps1 注册 mtrl-workbench-server，nssm_uninstall.ps1 退出注册，不能同时让旧计划任务抢应用端口。脚本中的当前命令、依赖服务名、路径与端口优先于历史机器记录。NSSM 二进制按 .gitignore 不入 Git；服务操作用 NSSM/PowerShell cmdlet，计划任务用 ScheduledTask cmdlet。

正式发布与重启继续从同一入口调用，编排实现在`ops/frontend_release.py`：

```text
powershell -NoProfile -ExecutionPolicy Bypass -File ops/server_ctl.ps1 -Action publish -CheckOnly
powershell -NoProfile -ExecutionPolicy Bypass -File ops/server_ctl.ps1 -Action publish
powershell -NoProfile -ExecutionPolicy Bypass -File ops/server_ctl.ps1 -Action restart
```

publish沿预览运行时的同一输入声明检查已跟踪增删改及实际未跟踪输入，包含根锁文件和构建工具；全部提交后用锁定Corepack/pnpm生成完整`/app/`构建，核源码与文件散列后按提交存到稳定发布目录，再停止原服务、只切换根`.env`的FRONTEND_APP_DIR、启动并核实际索引/公开资源、缺资源404及8000监听进程归属。restart核当前完整资源与前端源码一致后重启；前端输入已变则提示使用publish。两者校验服务注册模板、账号及相关环境覆盖，发布锁只覆盖实际切换与重启；NSSM管道按真实UTF-16解码。`-CheckOnly`执行只读核对，publish还构建核候选，随后释放临时构建；不进入服务操作。报告、日志和失败退出沿workspace_paths，运行结束后给出实际证据路径；失败现场暂缓删除。

切换或探活失败会返回非零，并尝试恢复上一前端字段和原服务，重新核旧资源；其他配置的并发修改保留，前端字段已被他人改动则明确报告恢复失败，保留现场。私有配置仅在内存保留必要旧值，不复制到证据；在用发布与上一套完整资源按回退用途保留。

成功发布并核实际服务后，发布器在原发布锁内清理自己登记的旧资源，保留当前与上一套完整版本。归属记录在var/state/frontend-release/retention.json，绑定版本目录与完整清单散列；未知、未发布、内容变化或无法核实的目录保留并报告。重复发布当前版本不丢上一回退版本；清理失败单独报告，不回滚已经验证的发布。历史未登记目录须专项核实，不能按目录名批删。

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

依赖声明和唯一锁是 backend/pyproject.toml、backend/uv.lock，官方 PyPI 来源沿配置。本机主检出的 backend/.venv 同时承担服务运行与开发验证；按用户2026-10-28确认，发布及开发统一用 `uv sync --locked` 保留开发组，验证可用 `uv run --locked`。首次空库安装工具的独立运行环境仍按其参数处理。新增依赖同时更新声明/锁，按实际风险做已有审计，不恢复旧 requirements 或 venv 私有索引副本。ops/init_db.sql 按既有用户裁定保留，不因此扩大凭据公开。

## 预览副本升级与完整前端切换

新建真实副本先在只读一致来源下核版本，目标迁到兼容来源结构，核复制计数/内容和序列后，仅升级目标到所需版本。已有登记可写试用副本先准备必要恢复点并核目标，只迁移自身，不重拷正式库覆盖用户修改；冻结历史性能副本保原版本与指纹，不为最新产品迁移。具体操作回[预览指南](frontend-preview.md)。

前端切换先处理未保存编辑并记录数据、后端与完整构建身份，停止旧实例后切完整资源目录，再核索引/版本资源、缺失资源404、深链及真实下载。回退保留当前数据库和正常业务写入，只恢复上一套完整前端资源与入口，不能以旧数据库备份撤回正常业务。


## React正式入口与界面回退

`FRONTEND_APP_DIR`指向完整的`/app/`生产构建目录时，FastAPI在`/app`及其深链提供React，`/api`、登录、主题与字体出口保持。旧壳已退役：该配置为空时只提供API及可选的隔离预览，`/app`返回404。配置在新进程加载，不在运行实例上改指针试切。`FRONTEND_PREVIEW_DIR`只管理`/preview`，不构成正式切换。完整候选的构建用`MTRL_FRONTEND_BASE=/app/`；预览构建保持默认`/preview/`，两种构建不可混用，启动检查入口基址及首页引用资源。

发布前记录全部构建文件散列，使用正式检出内稳定的`var/frontend/releases/<版本>`目录，一次交付完整目录。界面回退切换到上一套完整React发布资源，保持已核后端、当前数据库和正常业务写入。清空`FRONTEND_APP_DIR`不再提供旧版界面；不能回退旧后端或恢复旧库快照覆盖正常新写入。

切换前处理未保存/未知结果，按实际数据影响固定恢复点；迁移、服务操作和入口切换按当次具体授权。2026-10-28用户已验收React重写并批准旧版退役，过程依据回TAIL-423/424；实际正式版本以当前运行来源为准，源码退役与服务加载分别记录。
