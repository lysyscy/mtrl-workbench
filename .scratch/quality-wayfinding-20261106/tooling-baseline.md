# TAIL-484 · 运行、交付和开发工具基线

## 基点与证据口径

- 2026-11-06 只读取证。源码固定 `master@6d01f996dd46a86c204aeb2568aad58d82c2034d`，本机跟踪 `origin/master`。`ops`、`tools`、`backend`、`apps`、`.github` 在本次 `git status` 下无本地差异；项目状态、票务高水位、前端指南、油卡材料有工作区差异，未作为产品源码基线。`.tmp-fees-width.py`、`debug.log`、`.codex-remote-attachments`、若干设计和性能材料均只登记存在。未访问其中内容或处理他人改动。
- `7156a5ae..6d01f996` 仅两份回执文档改变。[最新发布记录](../notice-amount-deepening-20261106/implementation.md#发布) 记录 11:58 以 `7156a5ae` 加载、索引和44份公开资源、健康与监听进程归属通过。主控先在沙箱运行 `server_ctl status` 得到服务不可见/连接失败，同命令提权确认 Running、`/app` 200，实收索引与 `7156a5aef8d4` 发布目录 SHA 相同、DB 端口可达，并核 `origin/master` 同 `6d01f996`。本轮未核8000监听进程归属、全部公开资源或业务数据，历史证据保留当时效力。子分区未重复查服务、任务调度、远端 CI 或真实设备。
- 评估对应[质量参考 v1.0](quality-standard-reference.md)，重点为 Q5/Q7/Q8/Q9，性能取证能力对应 Q1–Q4。下文区分**事实**、**高可信静态风险**、**假设**、**保持现状**和**未查**。表中命名测试说明覆盖职责，历史通过仅按明确版本、范围和方法引用。本轮未运行测试、服务、迁移、数据库、i8、打印、产物清理或安装，未打开 `.env`、`ops/init_db.sql` 内容、会话材料、备份或业务原件。此分区未调用 Hindsight；项目规则记录的 bank 是 `project-3379fef93fbada35`。

## 运行与交付入口

| 工具及维护主人 | 实际入口、消费者和本轮证据 | 既有验证与边界 |
| --- | --- | --- |
| 正式运行装配 `backend/app/main.py`、`core/config.py`、`core/app_settings.py`、`web/` | FastAPI 装配 API、登录/主题、`/app` 与 `/preview`；两个目录设置、请求鉴权和机器环境各有主人。NSSM 服务用主检出 Python 单 uvicorn 监听8000，`frontend_release.WindowsService.validate` 比较进程启动模板、服务环境和机器覆盖；应用负责实际资源基址检查。配置入口与代码签发对应 [运行架构](../../docs/architecture/runtime-and-resources.md)、[部署](../../docs/guides/deployment.md)。 | `test_frontend_release.py` 深链、静态资源、空配置、旧壳404和错误基址；`7156a5ae` 历史加载通过。健康响应、源码和服务身份各自核实；真实服务身份的浏览器权限、数据库、网络和用户验收未复验。 |
| Windows 服务控制 `ops/server_ctl.ps1`、`ops/nssm_install.ps1`、`ops/nssm_uninstall.ps1` | `status/log/port/pg` 是定位入口；启停走管理员；`restart/publish` 调同一发布器。NSSM 注册/退出持有 Windows 服务并与历史计划任务避免抢占端口；消费者是正式环境管理员。 | `7156a5ae` 发布保留服务账号/进程/监听对应证据；现行安装、卸载和其他机器未执行。NSSM 二进制是本机第三方依赖。 |
| 发布器 `ops/frontend_release.py` | `require_committed_product`、`prepare`、`WindowsService`、`FrontendPointer`、`apply_release` 串起已提交输入、完整构建、UAC、指针、健康/实际索引及公开资产散列、缺失资源404、监听归属。发布锁覆盖服务变更；失败恢复原前端字段和服务，保留其他配置。发布目录有所有权记录，当前和上一完整版本保护，清理失败单列。 | `test_frontend_operations.py` 用临时配置、资源、服务替身验证，不能证明 Windows UAC 或实际启停。`797dfe36` 修复正式发布接受受管构建路径，历史记录28项发布/恢复通过；`7156a5ae` 是后续真实加载，非本轮运行。输入清单缺口见 T-3。 |
| 空库安装 `ops/deploy_restore.ps1`、`ops/selfcheck.ps1`、`ops/init_db.sql` | 安装器读明确仓根配置与 SQL 定义，检查角色/两库不存在，按 Python3.15 与 `uv --locked --no-dev` 准备环境，执行初始化、一次 Alembic upgrade、服务注册和自检。`-DryRun` 只读文件和计划。自检验证服务、HTTP、表数、两个模板和保留/退役路由；Skip 单列。 | 安装、版本迁移和数据库恢复的授权与验证独立。入口装配与边界可从源码核实，未找到同一版本从空主机全链路恢复实录。父进程环境与脚本契约见 T-5。 |
| 数据库迁移 `backend/alembic/env.py`、`versions`、`app/models_registry.py` | `get_settings().database_url` 是 Alembic 实际目标，模型注册提供 autogenerate 元数据。现有服务升级、可丢弃测试 schema、预览复制/目标升级都消费迁移链；`backend_verify` 的子进程以显式环境注入测试目标和单 schema 搜索路径。 | `apps/frontend/tests/test_preview_copy.py` 覆盖旧修订目标复制后升级及数据、序列、凭据投影；原集采/油卡迁移回执只证明各自版本。无生产/试用实例迁移或迁移图全审。 |
| 备份 `ops/backup_databases.py`、计划任务 `MtrlWorkbench-DailyBackup` | `backup_databases` 取两个本机目标，经子进程环境传凭据，先写 `.partial-*`，核归档目录、散列、字节及 manifest 后发布，`--verify`只读；保留旧档及失败现场，不按日期删除。`last-run.json` 属调度状态。[备份指南](../../docs/guides/database-backup.md) 拥有空库恢复和油卡原件/别名边界。 | `test_database_backup.py` 以替身核两档发布、坏档、第二档失败和远程/同身份拒绝；`a6fdd73a` 发布前两库备份有归档校验，未完整恢复。TAIL-458/460 的油卡原件/业务表恢复专项不能代替整库。当前调度/ACL/最近归档/真实物理连接身份未查，T-5 单列静态身份风险。 |
| 资源生成与版式出口 `report_export/resources.py`、`tpl_fill`、`report_export`、`mod03_notice/print` | 八个模板均有具名登记、文件散列闸门和消费者。机械四页、逐月欠款、过程、焊材气体、开会大表、集采打印台账走填充及域出口；库存和收发结存两模板保真实透视 ZIP/缓存。PDF/打印走 Chromium 和 i8 版式、独立的打印通道。 | [模板契约](../../docs/reference/template-export.md)、`test_tail04_export.py` 及各 `test_*_export.py`、React 下载用例是业务依据；本轮只核资产归属和装配，未读用户原件或打开 Excel/PDF。发布健康与 i8 读取不能证明真实导出/出纸。 |
| 字体 `backend/app/web/fonts`、`theme_react.py`、`tools/dev/sync_misans_web.py` | MiSans 主库4.009、三个原版 WOFF2、CSS 和分片 manifest/woff2，由 FastAPI `/static/fonts/` 与 React 消费。同步工具是明确维护入口，联网取素材并写生成文件，要求额外字体工具；仓中保版权及许可。 | `189cd6e1` 有分片采用历史，TAIL-424 正式浏览器119次字体响应的当时证据；`apps/frontend/tests/test_preview.py`、`test_font_recovery_protection.py`核主题及恢复代表。未跑浏览器、重生成或复审许可条款。README/工作流的物理路径需修正，见 T-6。 |
| 依赖工具链 | `backend/pyproject.toml` 的 Python `>=3.15`、`uv.lock`、PyPI、dev组和 `pytest.ini`；React `apps/frontend/package.json` 的 Node `>=24.22.1`、pnpm `12.15.0` 和组件锁。根 `pnpm-lock.yaml` 是发布检查保留的预期路径，HEAD 实际锁在组件。 | `test_deps_declared.py` 支持 Python 运行依赖声明检查；发布与历史 CI 对应当时锁定入口。未重装、升级、执行 pip-audit 或查上游授权。 |

## 验证、取证和治理工具

| 工具族与所有者 | 本次源码可确定的入口和消费者 | 旧证据可用范围 |
| --- | --- | --- |
| 后端业务 pytest `tools/dev/backend_verify.py`、`backend/tests/{conftest,db_guard}.py` | 明确节点及允许的 pytest 选项，复用 `frontend_preview.isolated_database` 建随机独占 schema、迁移、隔离环境与 `--basetemp`，关闭临时目录及自有 schema，记录真实退出码。业务 conftest 在注册导出及 core bindings 前核原配置、专用 `_test`、运行配置、已缓存 engine 和会话工厂。`rollback_db` 绑定 connection/savepoint；直接 engine/连接、另进程不受它约束。 | `test_guard_selftest.py`、`test_rollback_db.py`、`backend/tool_tests/test_backend_verify.py`。`1fa25415` 三域写事务用独立 PostgreSQL 连接实际探测，`7156a5ae` 通知书保值及付款流水有定向真库副本证据。未扩大到所有 DSN/environment 组合，见 T-1/T-2。 |
| 不接库的 Python 验证层 | `backend/tool_tests` 独立 pytest 装配，含 backend_verify、bytes_guard、TAIL 工具与 worktree_check。`backend/tests/test_staged_audits.py`、`test_frontend_operations.py`、`test_frontend_layout.py` 等文件可单独 unittest discover；该命令不会通过业务 conftest，layout 使用真实 Chromium 静态 DOM。`backend/pytest.ini` 默认两类收集一起，所以想只验证工具需显式目录/入口。 | `1fa25415` 的三件 P4 隔离验证明确不加载 app.main、业务及 bindings；`138f9a4b` 才增加 worktree 检查，不能套用旧报告。无需为证明已隔离而重跑所有工具。 |
| React 单元与 CI `apps/frontend/package.json`、`.github/workflows/frontend-checks.yml` | Node 原生 runner+tsx 导入真实 TS；`test:unit` 显式列测试文件。本轮文件名对照为同一集合。CI Ubuntu 24.22.1 / Corepack 0.36.0，显式 `install --frozen-lockfile`、typecheck、unit，paths 仅非 Markdown 的 `apps/frontend` 及工作流本身；CI 无浏览器、后端、正式 build 或 `apps/browser-extension` 步骤。 | `42159570276` 是最新发布回执记录的 CI 成功；未向远端复查，不能代替当前环境安装、服务或扩展验证。历史沙箱缺 Corepack 缓存时曾用已存在依赖执行同一前端脚本，正式构建仍另核 pnpm；本轮未重演。 |
| React 副本启动、运行及停止 `frontend_preview.py`、`frontend_preview_server.py`、`frontend_preview_runtime.py` | 主检出唯一排他锁，登记 owner、实际 PID+创建时间+命令、HTTP `/visual-version`、产品/构建散列、目标 schema；构建经 Corepack 固定 pnpm，`/preview` 和 `/app` 基址互斥。新实例须 `--copy-source --disposable`，既有试用仅走 `--existing`；正常退出只清自有可丢弃 schema，试用状态保留。 | `test_frontend_preview_runtime.py` 核跨进程排他、旧工厂退役、运行身份和替换、停止不受待用构建干扰；`test_frontend_run_paths.py` 核运行路径。旧报告的 PID/owner 不能给当前入口授权。T-3/T-4 为产品输入及可测条件的独立缺口。 |
| 复制及专门外部许可 `frontend_preview_copy.py`、`frontend_preview_browser_check.py` | 来源一致只读快照，目标表字段/内容/序列核对后只升目标；凭据脱敏投影及临时账户，默认阻断外部动作，另行获准的通知书模式仅在新 disposable 上放行批准站点、月份、账号与浏览器运输。现有试用实例另沿其 owner 授权。 | `apps/frontend/tests/test_preview_copy.py` 与 `backend/tests/test_frontend_preview_browser_check.py`，TAIL-476 的实际 Edge 代表另列。当前模式验证合格与许可为两件事；本轮未用任何真实外部入口。 |
| React 浏览器验证装配 `apps/frontend/tests/{conftest,test_preview,live_data,preview_select}.py` | Pytest 只附着登记真实副本；每例 browser context、实登录、身份核对，写例需重新核 disposable，DOM 选样经共享 locator 和 API 样本；失败截图绑定当前 owner。普通页面覆盖由各域及前端分区记录。 | `90720465` 的真实副本加载证据、加载结构 `b8ee0b24`、审计默认金额修复 `1fa25415` 各按所选页面、字号和场景。端点注入失败只支持相应错误反馈，不当真实数据或服务通过。 |
| 布局 `frontend_layout.py`、截图 `frontend_capture.py` | 布局命令只附着指定且最新可丢弃副本，真实导航、明确视口/字号和网格，空结果、超时、溢出各留明细；截图工具供测试失败和按需验看，绑定实例、视口和图像散列。 | `test_frontend_layout.py` 提供静态 Chromium 几何校验，`1fa25415` 与加载整改有真实副本代表。窄窗许可横滚及主动列宽裁剪依前端规则，工具报红只证明实际现象。 |
| 性能测量 `frontend_measure.py` | `check` 处理已有样本，`run` 需要冻结只读副本、同数据身份、实际构建且不含诊断插桩。ready 由标题、网络、字体、双帧代理，按冷/热和相同动作比较，先小样再按明确用途扩展。 | `test_frontend_measure.py` 核样本、噪声、输出及环境守卫；`1265c309`、`642725be` 性能记录只支持当时方案。当前只读实例供给缺口 T-4；加载完成时间不是正式 INP。 |
| 扩展协议与离线测试 `apps/browser-extension`、`tools/dev/i8_browser_session_reuse.py` | MV3 manifest、service worker 由浏览器扩展持有；工作台 relay 是消费者。`protocol.test.mjs` 检白名单/连接代号等，`browser_smoke.py` 用临时模拟站和隔离 Chromium。专项 CLI 是另一条单号精确核验入口，`--plan` 无外呼，`--execute` 从 stdin 接受当次会话材料和可选 transport，退出0只代表响应解析和单号一致。 | 固定安装包 `c44568c2997b03de` 的 TAIL-476 通知书17条真实副本读回。实际账号菜单条件后在 `09137eb0` 按用户裁定退出，`6b0bc21a` 改恢复机制；两项改变需各看当时证据，不能用固定包实测覆盖现有扩展所有能力。当前安装副本和用户授权未查。 |
| Git 暂存审计 `ops/hooks/pre-commit`、`install_hooks.ps1`、`audit/{syntax_audit,bytes_guard,git_index}.py` | 钩子先拦文件名，再用 venv Python 做 Git index 语法和字节核验。NUL 路径、stage-0 blob、删除/重命名及 Git 错误由 `git_index` 和审计工具处理；无参数的全量扫描是独立入口。本机实际 `.git/hooks/pre-commit` 存在，两处摘要文案与仓本不同，比较时忽略行尾仍有差异。二者非零均阻断，仓本语法 rc=2 单列“未完成”。 | `test_staged_audits.py` 用临时 Git 仓核部分暂存、重命名和 Git 失败，`7156a5ae` 的历史真实提交钩子通过。当前只读比对不证明本次提交已验；边界见 T-6。 |
| 产物 `tools/artifact_lifecycle.py`、`audit/workspace_paths.py`、`audit_work.py` | 入口委托已安装 setup 公共实现，`workspace_paths` 给预览/验证/布局/性能/发布及已迁移反例分配受管 run、继承身份、持租约、按结果封存或保护；兼容指定旧 run，活动预览、正式资源、原件、备份和依赖走各自生命周期。`audit_work` 提示用途和清单；未证明存在定时 sweep。 | `e296e816` 接入及 `test_workspace_lifecycle_producer.py`、历史真实运行回执证明当时登记与父子归属。已登记规范并不说明当前计划任务或所有历史工具已接入，仓外公共实现与持有现场本轮未运行。 |
| 工作树退出 `tools/audit/worktree_check.py` | `--worktree` 只读汇总提交包含、index/工作区/忽略项、链接、进程命令和预览指针，0 为扫描完成，2 为失败/未知；贡献指南持删除和保留判据。 | `138f9a4b` 与 `backend/tool_tests/test_worktree_check.py` 核脏索引、链接、假干净和无法扫描；当前其他工作树和消费者未扫。 |
| TAIL 台账 `tools/oneoff/{_tail_open,_tail_close,_list_tails,tail_common}.py` | 指定整合者串行发号，`issue-tracker`持唯一高水位，原票持状态/依赖，工具默认干跑，`done` 才满足依赖，关闭原因需证据；`status` 仅导航。 | `backend/tool_tests/test_tail_tools.py` 保护重复号/缺失高水位/非 done 依赖/故障回滚。当前共享票由主控持有；子分区未改票、高水位或索引。 |
| 工具审计 `wiring_audit.py`、`wiring_expected.txt`、`prg_form_audit.py`、`sticky_probe.py` | W2 是静态候选线索，`test_wiring_guards.py` 属现行定向保障。`prg_form_audit`/`sticky_probe` 有历史反向脚本，但旧壳退役后不能按命名认定仍适用；本次只认具名消费者，保留待核。 | `TAIL-424/450` 排除专用旧壳和 Node 语法检查；现行共享装配和金额等混合保障继续保留。旧形态审计不作为新 React 验收。 |
| 技能维护源 `skills/machinery-fee-consolidation` | 用户显式调用，`extract_reports.py` 读选定报表页，`apply_template_edits.py` 输出新文件保格式，`record_system.py` 走业务写入/回读。维护路径与中央库/运行副本由本技能 maintenance 持有，仓内源码改动与分发独立。 | `references/validation.md` 是真实格式边界，后端 `test_mechanical_skill*`/机械持有者和历史定向回读关联。未检查当前安装副本、Excel 格式全矩阵或真实录入。 |
| 技能维护源 `skills/payment-plan-audit` 与 `_build_plan_audit_runtime.py` | `remote.py` 正常系统身份，`audit.py`/`annotate.py` 对选定 Excel 注释，`methods.py` 按具体预览批准回写，当前快照 `GET /api/m03/plan-audit/snapshot`。构建器从 canonical 规则生成跟踪的 `resources/audit-runtime.zip`，再生本机 `dist/payment-plan-audit.skill`；不扫用户数据。 | `test_audit.py`、`test_remote.py` 覆盖 OOXML 保值、快照、方式冲突/批准/错误。只读比较 ZIP manifest 与当前五个源码，四件原始 SHA 相同，`mod04_plan/domain.py` SHA 不同，统一 CRLF/LF 后字节相同且 AST 相同。`edad5e5c` 生成物未发现规则语义漂移；实际部署包未查，工作区 SHA 会受行尾影响，不能据此判断分发版本。 |

## 仍在仓的历史及专项工具

以下按已读脚本头、入口片段和可见消费者划分。专项场景外无现行调用证据的具名候选保留原位。未逐个执行，也未把目录或同目录测试视为使用证据。

| 工具/具名分组 | 已核职责和保护决定 |
| --- | --- |
| `tools/probe/_shell_live.py` | 现行 `tools/README.md` 明确保留的后端 OpenAPI/GET 退役核验；旧名称不等于旧壳运行。结果仅支持指定端点及旧路径状态，不开旧 UI。 |
| `i8_contract_probe`、`i8_fetch_smoke`、`i8_flow_probe`、`_diag_fetch`、`_probe_i8_acct`、`_probe_itemname`、`_probe_unmatched_contracts`、`_probe_wh` | 真机契约、样本取数、账号字段、合同物料/未匹配和仓库；i8 规范为主人，可能登录、落盘或读取私有证据，保持专项授权门。未查当前现场需要。 |
| `print_bills`、`render_preview`、`render_smoke`、`_probe_acct_check` | 手工版式/账号和 PDF 诊断，`print_bills` 还具可选 IPP 实际出纸。渲染、真实 i8 读与出纸分开授权。用途证据来自脚本契约和打印版式维护，未查当前设备与历史样本。 |
| `_e2e_m01_archpick`、`_e2e_m01_promote`、`_e2e_m01_wired`、`_e2e_m05_ledger`、`_e2e_m05_wired`、`_e2e_m06_proc`、`_e2e_m07bal`、`_e2e_m08_wired`、`_e2e_m09_wired`、`_e2e_own_assign`、`_e2e_unresolved_freshness`、`m3_notice_smoke` | 档案、归属、台账、过程、结余、库存、费用与通知书的历史真机探针；可达例 `_e2e_m01_wired` 默认8000并具写入/回收，旧“跑完自清”不满足当前试用保护。逐个继续适用性未核，不能当默认验证入口。 |
| `_ai_map_bench`、`_probe_p1_jieyu`、`_probe_tail43`、`_probe_tail97_impact` | 历史基准/结余/透视/迁移影响工具，脚本题意可识别；仍有真实消费者与原证据新鲜度未核。 |
| `_jc_payment_terms.py`、`_tail313_contract_dates.py`、`oilcard_continuation.py` | 分别为 TAIL-432 付款方式/账期迁移、TAIL-313 日期单次修正、TAIL-463 油卡清单/演练。默认预览/正式更新和演练与真实接续应分别判定；油卡真实接续仍归 TAIL-474。未经当前授权不执行或以旧输入重放。 |
| `_m8_fix3`、`_m8_rehearse2`、`_m8_serve8001`、`_tail93_create_two_smalls`、`_verify_auto`、`_b_diag_archive_pending`、`_tail208_measure` | 旧自检修补、8001 演练/服务、指定业务补写和真实库观察。源码中8001路径读取项目配置并开端口，退出边界与现行唯一 owner 不同；保留待核，禁止当日常恢复方法。 |
| `_verify_p1_weldgas`、`_verify_tail04`、`_verify_tail43` | 专用报表/成品核对，部分用真实库、业务样本、写证据。保留对当时数据、成品及透视的历史意义，待核当前输入和实际调用方。 |
| `_prepush_sensitive`、`_ps_bom`、`_ps_parse_check.ps1`、`_theme_contrast`、`_find_phantom_test_refs`、`_oneoff_measure`、`_doc_append`、`_fakedirty`、`_skeleton`、`_struct_scan`、`_t195b2_survey`、`_tail193_measure` | 敏感路径、BOM/语法、主题和结构诊断及历史文档扫描。只有 `_ps_bom` 仍有 bytes_guard 明示修复消费者；旧 `prepush` 另保取证入口，实际 hook 配置未把它变成自动门。其他逐一当前调用、旧标准和真实用途未核。 |
| `tools/mut` | 反例家族覆盖金额/台账/报表（如 `_mut_amount`,`_mut_tail04*`,`_mut_proc*`,`_mut_ledger`,`_mut_big`,`_mut_m4*`,`_mut_p1`）、归属/项目/集采（`_mut_own*`,`_mut_arch*`,`_mut_promote`,`_mut_jc`,`_mut_tail28*–30*`）、会话/打印/保存（`_mut_auth`,`_mut_i8cookie`,`_mut_long_login`,`_mut_session_identity`,`_mut_print`,`_mut_m03pay`）、护栏（`_mut_bytesguard`,`_mut_layering`,`_mut_wiring`,`_mut_deps`,`_mut_prg_form`,`_mut_sticky`,`_mut_t14t15`）及历史接线。`_isolated.py` 用临时后端副本，但 `_mut_amount.py:24,73–81` 写固定主根源文件，`_mut_acct.py:17–20,62–69`、`_mut_jc.py:265–267` 写所在检出再还原。该还原会碰并行状态，不能以“反例”当安全入口。老测试/靶点的逐件当前可达性未证实。默认保留待核，不运行。 |

## 可核风险和维护差距

### T-1 · 明确来源验证晚于首次持久操作（Q8/Q9，目标选择已确证）

- 正常入口 `backend_verify.verify` 先用 `Settings(_env_file=source_env)` 决定 `guard`，`isolated_database` 再用同一方式读取一次。`Settings` 保留环境变量优先级。两条继承 DSN 如果都是不同的合法名称且测试名带 `_test`，`TestDatabaseGuard.from_sources` 接受；被连接的 `current_database()` 只和刚选中的 engine URL 比较。随后 `CREATE SCHEMA` 和 Alembic upgrade 先发生。只有进入子 pytest 的 `db_guard.point_tests_at_test_db` `MTRL_TEST_SOURCE_ENV` 分支，才从指定 dotenv 直接取测试身份并核运行值。[验证入口](../../tools/dev/backend_verify.py#L57) [隔离数据库](../../tools/dev/frontend_preview.py#L30) [守卫](../../backend/tests/db_guard.py#L67)
- 可达反例使用四个虚构 PostgreSQL 名，明确文件为 `business_a`/`business_a_test`，父环境同名键为 `business_b`/`business_b_test`。主控用合成 env 并在 `create_engine` 处中断，实证选中 B 测试库，未建立数据库连接。若实际具连接及 DDL 权限，迁移发生在 B 的随机 schema；子进程若正常装配守卫才拒绝不一致。涉及 `copy_source=True` 的预览同样会受父环境来源影响，且会先查来源修订和只读复制，已有试用路径另有固定库名/schema/owner/修订检查。未观察真实错误写入，也没有证据表明历史运行存在该覆盖。
- 最小后续验证用 `backend/tool_tests/test_backend_verify.py` 的临时 dotenv、明确节点、虚构 DSN，断言在 `create_engine`/`isolated_database`/迁移有任何持久动作前拒绝不一致。需要区分“读取文件声明的源库和目标”和“明确拒绝冲突”的实现选择，先固定批准的身份不变量。现有夹具清空这三项环境并 stub `isolated_database`，所以旧通过可复用给退出码/清理，不能回答父入口身份。另以既有 `test_guard_selftest.py` 保持缓存/同库拒绝。均可使用纯工具替身，无需连接 DB。

### T-2 · pytest 环境输入绕过显式节点/装配约束（Q8/Q9，高可信静态风险）

- `backend_verify.validate_pytest_options` 只审 `--` 后的显式参数，`isolated_database` 从 `os.environ.copy()` 继承原环境并交给子 pytest。已只读核本机 `_pytest/config/__init__.py:1522–1528,1575–1586`，`PYTEST_ADDOPTS` 前置，`PYTEST_PLUGINS` 在初始 conftest 前加载，发行版自动插件发现是另一个输入。静态可达反例是 `PYTEST_ADDOPTS` 增加既存测试文件、切换 `-c` 或 `--noconftest`，和 `PYTEST_PLUGINS` 提前导入任意指定模块。既有显式 `--basetemp` 仍在后方，单独的重复 `--basetemp` 最终优先级未验证，不作为已证明的越界结果。[环境投影](../../tools/dev/frontend_preview.py#L59) [子进程装配](../../tools/dev/backend_verify.py#L78)
- 现有子进程 `DATABASE_URL` 仍是测试目标、随机 schema 仍是设计保护，新增节点和丢失 conftest 意味着报告的选择与实际装配可能不符。未核当前运行环境有无这些变量，未观察正式写入。最小后续验证先用模拟 subprocess 捕获 env 和 argv，再以无业务/无库的临时 pytest 子进程验证额外节点、非默认配置和隐式插件的作用。保留显式 `-k/-m/-o addopts=`、自有 `--basetemp`、退出码及正常插件需求，只修有证据的继承输入。

### T-3 · 构建/预览指纹漏掉已采用输入（Q5/Q7/Q8/Q9，部分事实、部分高可信静态风险）

- `product_inputs(frontend_only=True)` 没列 `apps/frontend/pnpm-workspace.yaml` 或 `apps/frontend/patches`。实际 YAML 声明六个版本化 `.d.ts` 补丁，AG Grid 和 Ant Design 及 Cascader/Image/Menu/Picker 都有消费者。`require_committed_product`、构建前后比较、运行 `verify_build`、`restart` 使用同一清单。单改配置或补丁时，dirty/版本判断可绕过。锁有补丁散列，CI 会冻结安装；正式/预览 `prepare_build` 仅核 Corepack pnpm 版本后调用 typecheck/build，不独立证明已装依赖来自该锁及补丁。静态证据未证明正式当前构建用错依赖。[输入声明](../../tools/dev/frontend_preview_runtime.py#L120) [pnpm 配置](../../apps/frontend/pnpm-workspace.yaml#L5) [构建](../../tools/dev/frontend_preview_server.py#L40) [发布闸门](../../ops/frontend_release.py#L411)
- 非 frontend-only 产品清单也漏 `frontend_preview_browser_check.py`。`server.run` 无条件导入该模块来载入模式，授权模式还消费其 transport/账号保护。只改变该模块时，旧进程的 `product_sources` 可能仍与当前相同，证据可把旧门误认为当前门。与正式业务扩展安装状态是不同问题。主控已只读复核 workspace YAML、patch 和此模块三类路径均未入产品指纹。[输入声明](../../tools/dev/frontend_preview_runtime.py#L120) [实际消费者](../../tools/dev/frontend_preview_server.py#L180) [启动入口](../../tools/dev/frontend_preview_server.py#L207)
- 最小后续验证沿现有 `test_frontend_preview_runtime.py` / `test_frontend_operations.py` 的临时 checkout/文件替身，分别模拟未提交修改、删除和新增的声明输入，及运行 owner 对旧指纹的拒绝。先固定生产需要的输入和仅预览需要的输入，避免新规则无意阻断历史 `/app` 包的正常重启或误更新回退；锁/安装一致性另按可用本机缓存和明确锁定场景取证。六补丁自身是否必要沿 TAIL-450 保留，不能借此升级或移除。

### T-4 · 性能采集的只读供给路径缺口（Q1/Q5/Q8，事实及待验证假设）

- `frontend_measure.preview_identity` 只接受检出的 `.artifacts/active`，要求 ready、只读、`preview-user`、专用库及完整构建。当前统一 `frontend_preview.py` 提供的新副本固定 `read_only=False`、`preview-admin`，`--existing` 也只接受已登记可写试用，应用 checkout 保护还要求 `transaction_read_only=off`。没有在现行统一入口中找到符合采集器条件的新实例模式，也不能把受管 `files` 路径直接用于该采集器。可能有历史已冻结原 owner 或当次获准脚本供给，本轮未核，不宣称完全无法运行。[采集身份门](../../tools/dev/frontend_measure.py#L208) [创建/装配](../../tools/dev/frontend_preview_server.py#L85) [预览指南](../../docs/guides/frontend-preview.md#性能测量)
- 下一个性能票先决定需要的是可丢弃副本上只读动作的定向 trace、冻结同源比较，还是沿旧84组工具完整复做。只有选后两者才核可信旧 owner 和当前准许的供给方式。最小核验先用合成 owner/version 检受管路径和身份差异，仍禁用把在用可写用户副本重新标记为只读。旧测量只能复用历史发现或同源比较，不能拿其 readiness 当本版用户体验结论。

### T-5 · 首次安装与备份的身份核对边界（Q7/Q9，次序靠后的静态风险）

- 安装器从 `.env` 文件静态确认 SQL 角色与两库，真正 Alembic 仍读取应用 Settings 并继承当前 `DATABASE_URL`，调用只一次。脚本没有展示同机两个库都完成迁移的流程，不能将初始化建两库等同两库均可立即运行业务。`selfcheck` 取有效配置的当前 schema 表数，亦不能独立证明是刚初始化的目标。触发需实际安装，当前未查是有意只迁应用库还是要求测试库也就绪。仅在新装验收/整改时，以假配置、假子进程命令和临时目录核实际目标及退出，无需现阶段开真库。[空库安装](../../ops/deploy_restore.ps1#L43) [Alembic](../../backend/alembic/env.py#L23)
- 备份的两库检查用 `(host, port, db)` 字面元组，`localhost` 与 `127.0.0.1` 可让同名同机库通过两份“不同”检查。脚本继承父环境并只覆写列出的 PG 变量，归档验证只能证明字节和目录。后续只在需要备份边界取证时，以虚构 DSN/替身先核别名并区分归档可读、真实身份和恢复证明；不读取本机实际配置来制造反例。[备份入口](../../ops/backup_databases.py#L41)

### T-6 · 已证实文档与入口漂移，保留已有行为（Q5/Q8，事实）

- `README.md:14` 和 `docs/agents/workflow.md:19` 指向 `backend/app/resources` 作为字体位置，实际运行字体是 `backend/app/web/fonts`；模板路径正确。`report_export/resources.py:38,50` 提到不存在的 `docs/requirements/report-templates.md` 和当前参考里已经不维护的哈希表；散列主人实际为 `EXPECTED_SHA256` 和资产字节。`selfcheck.ps1:94–101` 另复制其中两项，两个值本轮从源码比对仍相同。最小动作是纠正引用及注明自检具名覆盖，代码复用只在出现实际同步成本/改变验收范围时考虑。
- `ops/install_hooks.ps1:11–12,32` 推荐提示里保留 `git commit --no-verify` 的说明，与 `CONTRIBUTING.md:53` 的当前不跳钩子不一致。实际安装版与仓源版差异仅失败提示，均阻断；由维护者合适时核安装、源码同一版本。凭据文件名模式仅匹配根 `.env`/`.env.*`，其他材料及嵌套路径不能由该门兜底，`.gitignore` 也不等于内容审计。未知附件在场不代表已暂存或含有凭据；若扩展拦截规则，只在临时 Git 仓取证具体边界和合法例外。
- `audit_work.py:55–62` 会把 tools 根的每个 Python 文件标成散件，并报非零；现行唯一产物入口 `tools/artifact_lifecycle.py` 正是该路径。由此单独 T14 黄项可误报当前合法入口，保留该入口，按现行旧运行适用边界修正提示或将旧检查标明。无须据此调整清理流程。
- `CONTRIBUTING`、开发验证指南、`pytest.ini` 当前各自拥有入口/选测/装配，无证据需要合并。`test_frontend_operations` 等文件虽位于 `backend/tests`，指南明确用 unittest discover 时不走 pytest conftest，路径未漂移。`AGENTS` 的动作导航、`CODING_STANDARDS` 的分层、`docs/architecture` 的装配主人和 `docs/requirements` 的业务主人仍各自适用。文档调整只核实际引用、当前消费者和接手步骤。

## 资源与退出边界

- **自有在用资产**包括上述8份模板、React/扩展源码及其6份上游补丁、迁移版本和规则文档、两套业务技能维护源。模板文件虽源于用户指定成品结构，仓内运行模板与真实业务原件分开。`ops/init_db.sql` 按既有裁定保留；仅核文件存在和安装消费者，未读取正文。`.env.example` 属配置示例，未核真实配置。
- **第三方与派生资产**包括 MiSans 字体及许可证、CSS/manifest 与分片、NSSM 本机二进制、PostgreSQL 和 Playwright/Chromium 本机安装、pnpm/Python 依赖缓存。旧第三方源码按 Git 追溯；本轮没有核整个依赖树许可/CVE、缓存内容或已安装组件版本。生成的 React `dist`/发布目录、扩展安装包、技能 `audit-runtime.zip`/`.skill` 和实际回执分别由构建、分发或运行 owner 持有。`tools/oneoff/_mut_m3.out` 是跟踪的旧输出，未核现行消费者或独有内容，保留待核。
- **已退役**包括旧 HTML/JS 壳及静态入口/专属测试，旧前端回退不再可用，正式回退用完整上一 React 资源。通用导入 API、旧域导入编排、机械 JSON/确认链、旧语法 Node 检查及其独用用例已退出；共享读表、历史批次/业务模型、机械报表只读解析、字体、主题、模板和混合测试的现行业务保障保持。[TAIL-424](../tails/issues/TAIL-424-旧前端退役与清理.md) [运行架构](../../docs/architecture/runtime-and-resources.md) [审计实施](../audit-remediation-20261105/implementation.md)
- **未知及受保护**包括现存本机 `.artifacts`、`var/state`、备份和私有配置、正式/回退目录、非登记历史输出、现有试用及原件、附件、他人未提交文件。未核实际内容、产权、活跃消费者、任务调度和退出条件；没有清理依据。已有发布回执能证明自己当时登记的 `17495586c2a1` 回退保留，不能证明当前本机路径。冻结性能样本保原数据和版本，不能以最新源码为由改样本。

## 复用和下一轮边界

- 复用证据先比固定产品输入和受影响调用链，再核工具/依赖版本、隔离实例、动作、数据及实际预期。`7156a5ae..6d01f996` 的两份文档差异允许复用 `7156a5ae` 同产品的通知书保值和当时发布结果，不证明当前进程。`1fa25415` 的 P4、定向 DB/真实浏览器和 staged audit 结果只回答其原场景；现存用例没有覆盖 T-1/T-2。`797dfe36` 发布路径证据支持登记路径别名，不覆盖新发现的未列输入。`642725be` 的历史性能现场可作为问题定位来源，Q1 现行结论需要可比样本。`TAIL-424/450` 的退役、保留和暂缓为当前基线，有新消费者/行为证据才重开。
- 优先送主控裁定的是父进程目标选择、继承 pytest 装配和构建/预览输入的完整性。三个检查分别可用虚构环境、临时纯工具 fixture 和临时 Git/资源替身，不必动数据库或正式服务。性能供给缺口随所选前端取证范围决定；首次安装、归档恢复、真实打印、第三方许可和当前调度保具名未验。规则/文档修复按现有主人和实际消费者最小同步。
- 本轮工作范围只到静态覆盖和候选最小取证。没有新测试成绩、现场业务或版本安全认证。专项 probes、变异逐件有效性、本机运行注册、主机原件及第三方安装副本未被整体签收。
