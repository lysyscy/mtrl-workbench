# 开发与验证

先核当前任务范围与 [workflow](../agents/workflow.md)，业务预期回 [requirements](../requirements.md)。命令从仓根运行；依赖、Python 版本及 pytest 配置以 backend/pyproject.toml/uv.lock 为准，已有 backend/.venv 可用时不为文档改动重装。

## 按影响选检查

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/backend_verify.py --source-env <明确来源.env> --test <backend内测试文件或节点> -- <pytest选项>
backend/.venv/Scripts/python.exe -X utf8 tools/audit/syntax_audit.py --staged
backend/.venv/Scripts/python.exe -X utf8 tools/audit/bytes_guard.py --staged
backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_list_tails.py
```

backend_verify从仓根调用，--test可重复，测试路径相对backend，--之后支持`-q/-v/-x/-k/-m/--maxfail/--tb/--durations/--disable-warnings`和清空默认参数的`-o addopts=`，不能追加收集路径；仅在已核专用测试库创建独占临时schema，升级后运行明确节点，成功或测试失败均退出自有schema。不启动HTTP预览，不停止现有8065，也不复制/改写正式业务数据。pytest从启动起DATABASE_URL就是测试目标，MTRL_TEST_SOURCE_ENV仅供守卫读取明确来源身份；同库、不同目标和错缓存仍拒绝。默认沿workspace_paths归档日志与JSON报告，含源提交/dirty、测试选择、退出码及清理结果，不记录DSN或凭据。

pytest 在 backend 组件运行；选文件/节点前先看 fixture。保留真实原始退出码、失败节点和未验边界，不从票终态推当前环境通过。普通局部改动复用现有定向检查，不自动全量回归/变异。文档验证看业务语义、当前引用、imports/动态读取/配置及接手路径，不再生成旧验收 JSON 或四态报告。`@acc` 在存量业务测试中仍可作历史标识，不是新开发前置。

## 隔离和写入

backend/tests/conftest.py 的守卫先保留原目标、验证专用 TEST_DATABASE_URL，再装配业务，核 Settings 与缓存 engine；缺失、同库别名或无法确认时拒绝。不能回退 SQLite 或借业务库。rollback_db 接管已核测试库的会话工厂，commit 仅释放 savepoint，结束回滚外层事务；自建 engine、原生连接和另一个进程不受它保护。真实写入必须另外核目标、身份、可废弃范围和清理所有权。

db_guard、test_guard_selftest、test_rollback_db 与有效付款/撤销/权限/模板回归保持。环境失败如实报告，不跳保护换绿灯。离线源码检查不能证明 DOM 已显示、真实数据库已写或文件实际可打开；界面诊断和回归的证据边界见下文。

## 界面和外部链路

网页探查优先内置浏览器，专用回归保留已有 Python Playwright 与原入口。需要 CLI 时读实际安装 playwright-cli；使用自己命名的会话，结束关闭。Python Playwright 浏览器路径只传子进程，服务身份与浏览器环境回 [部署](deployment.md)。i8 登录/抓取、真实打印、生产导入/付款均按当次明确授权，不能用浏览器或测试的存在推导权限。

界面改动与迁移按同来源 implement-solo-spec / `references/verification.md` 的界面分支核旧行为与实际结果，以“页面入口 + 用户动作 + 结果”复用当前规格或票。旧界面的操作、必要截图与源码/接口互补，无法运行时留具体未验项；本项目已有大型迁移验收保持。打印输出按已授权预览、PDF 或现场边界核对象集合和业务口径，不因规则验收操作真实打印机。

React 实现与交互约束回 [frontend-design](frontend-design.md)。旧 HTML/JS 壳及其源码读取、专用回归已退役；混合测试保留仍有效的后端业务检查。

## 工具与产物

工具用途及边界读 tools/README.md。syntax_audit、bytes_guard 和凭据文件名保护在真实 pre-commit 执行，不能跳钩子。票工具用临时 tracker/票目录验证高水位、依赖和失败回滚，干跑不得写入。audit_work 只提示运行产物生命周期；wiring_audit 的 W2 只是候选线索，不能当成业务缺陷或删除授权。

运行产物由 workspace_paths 分到本轮 .artifacts/active/<effort>/<run>/<kind>，父进程收尾；临时脚本放 work/系统临时目录，证据必要才有限保留。异常日志完整保留原始返回码后再读末尾。Windows 用 python -X utf8、显式文件编码与 subprocess encoding；PS1 保 UTF-8 BOM，其余保原行尾。禁止用跨壳字符串拼接处理删除/移动；按绝对路径、对象范围和原件恢复依据操作。


暂存语法/字节审计的`--staged`读取Git stage-0内容，部分暂存以index为准；删除不读工作区、重命名按目标检查，Git读取失败返回非零。无参数仍为全量检查。纯Git输入回归用`backend/.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s backend/tests -p test_staged_audits.py -v`，只创建临时Git仓、不装配应用/数据库。

## React 浏览器与预览工具验证

构建/启动/更新/退出按[预览指南](frontend-preview.md)。`apps/frontend/tests/conftest.py`只附着登记的真实副本；`test_preview.py`的server、浏览器context和login绑定同一进程/schema/产品身份，不能在测试中透明切换成用户实例。各例关闭自身context与路由；React browser_page在失败或捕获运行错误时、关闭页面前保存截图，按需验看使用preview_screenshot(label)；两者经tools/dev/frontend_capture.py写入本轮screenshots及同名JSON，记录实际预览身份、页面、视口和图像散列，身份核验失败明确标记，不冒称最新页面已验。共享下拉定位回`preview_select.py`，真实API选样回`live_data.py`；上述React自动浏览器回归不运行浏览器业务seed或自造业务回包。

只读代表可复用当前真实试用实例；写入代表须通过每例重新核验的disposable门，先停并保存用户试用归属，使用唯一可丢弃真实副本，完成后恢复原入口。真实数据缺场景时记录具名覆盖缺口，不构造模拟页面补成全过。按受影响页面选择现有节点；域金额组合、日期/归属和模板由相应后端/文件层承担，React保登录/权限、草稿/焦点、未知回执、实际写读和下载范围代表。

一次性定位界面交互时，可用隔离的简化页面或模拟接口辅助诊断；只证明模拟条件下的界面行为，不能证明真实权限、业务写入或正式运行，也不能替代本节的真实副本回归。诊断不授权真实i8、打印或业务写入；副本不可用时记录未验入口、原因和已有证据。

`backend/tests/test_frontend_preview_runtime.py`验证跨进程排他、陈旧身份、实例切换授权、HTML构建输入、旧factory退役及待用构建不阻止正常停止；不监听端口。`apps/frontend/tests/test_preview_copy.py`仅作数据库/进程内合同，显式`MTRL_PREVIEW_SOURCE_ENV`用于确认测试目标，临时数据库样例不开放HTTP。它覆盖凭据投影、内容/序列、旧结构复制后只升目标及所有既有外部动作阻断。

`backend/tests/test_frontend_measure.py`保纯计算、输出与预览身份保护，不依赖运行中的真实预览。采集器的现场验证由`tools/dev/frontend_measure.py run`在获准的真实副本上显式执行，默认后端回归不承担该验证，也不证明完整84组或本次用户实看。纯算法保护在apps/frontend运行`corepack pnpm test:unit`，由Node原生test runner配合锁定tsx直接导入真实TS模块；保存快照/未知回执、身份门、单据号匹配、合同与付款流水结构边界与浏览器pytest分开。仍运行`corepack pnpm typecheck`承担TS严格检查；单元测试不启动Vite/HTTP或数据库。具体当前运行结果与原始失败回当前任务evidence，不在指南追加通过数。
