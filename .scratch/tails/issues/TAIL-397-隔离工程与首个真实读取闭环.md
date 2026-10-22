# TAIL-397: 隔离工程与首个真实读取闭环

**What to build:** 在独立预览中登录、识别当前账号并读取真实隔离后端的项目列表，旧前端继续正常使用。

**Blocked by:** None (can start immediately)

**Status:** claimed

- [x] 同仓独立 worktree 与分支、组件源码位置和 pnpm 单包布局落实；报告实际绝对路径，依赖及构建不覆盖在用文件。
- [x] 固定 React/React DOM 19.3.1、TypeScript 7.0.2、pnpm 12.14.0；实测兼容后固定 Vite、React 插件及类型声明，冻结锁文件安装、严格类型检查和生产构建分别通过。
- [x] 确认隔离后端、专用测试库及测试身份后，登录与项目读取真实可用；空、错、无权限和会话过期有准确回执。
- [x] 账号切换清理前账号数据、草稿和历史摘要；主题、导航、身份及必要键盘操作符合现行基线。
- [x] FastAPI 实际提供生产构建，验证登录/Cookie、页面刷新、资源版本及读取；固定实际实施基点和起点未提交范围，记录旧版后续差异处理方式。

规格：[前端独立重做规格](../../frontend-vue-rewrite/spec.md)（User Stories 1, 2, 3, 4, 5, 6, 7, 8, 9, 44, 45）；业务口径：[MOD-01](../../../docs/requirements/PRD/02-功能规格/MOD-01.md)、[MOD-15](../../../docs/requirements/PRD/02-功能规格/MOD-15.md)。

验证类型：浏览器可观察行为＋实际后端/隔离数据库；涉及导出时检查实际文件，涉及外部系统时使用明确替身边界。复用有效既有保障，按本票风险补缺，不重复整套检查。

---

## Comments

**2026-10-22 · 建票（agent）。** 来源：用户2026-10-22确认React前端28票及依赖｜不做会怎样：新前端该用户路径或累计交付缺少独立验收与接续依据｜落点：新前端独立副本；规格及本票验收｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①按已批准依赖解锁后续②先验收再扩大迁移③同批共享隔离与交互边界④依赖和验收见本票

**2026-10-22 · 授权与执行入口。** 已批准建票及上述依赖，后续采用 implement-solo-spec 跨批统筹；本轮仅建票，尚未授权开始实施。ready-for-agent 仅表示任务已说清，仍需实施启动授权；外部真实动作、正式切换及退役各守规格授权门。

**2026-10-22 · 建票核验（非实施）。** 已核28个独立票文件与批准依赖逐项一致、依赖无环、48条用户故事有承接、规格及业务引用有效，原User Stories与Testing Decisions章节摘要保持。doc_audit退出0，必须修0（疑似33、已豁免15）；git diff --check通过。票仓及主计划同步完成，尚未实施或运行应用测试，正式切换和退役各待授权。

**2026-10-22 · 开工。** 本批仅TAIL-397；用户“开始吧”及父任务委派授权实施、本地提交，禁止推送和正式服务操作。工作树为`D:/UserData/Documents/Codex/2026-10-22/task/mtrl-workbench`，分支`codex/react-frontend-rewrite`；工作树与原仓HEAD均`290d1e54064bf21641af0f5f2f193cc29f2cb46d`且clean。累计调查基点仍为共同规格的`33a9bb4`，本批实施基点单列不重置。测试库只读确认`mtrl_workbench_test`、角色`mtrl`有CREATE schema权限；使用随机独占schema，禁止public回退；迁移和浏览器写入均限定该schema。

**2026-10-22 · 实施与逐条证据（待父任务验收/销号，不启动398）。**

| 验收 | 实际结果与边界 |
|---|---|
| 工程隔离 | 指定worktree/分支复用，实施基点`290d1e54064bf21641af0f5f2f193cc29f2cb46d`，两处起点clean；原仓无源码修改。apps/frontend单包src/tests/dist，唯一pnpm-lock.yaml，dist忽略；没有网格、业务编辑或398以后页面。操作主人为docs/guides/frontend-preview.md。 |
| 依赖/类型/构建 | Node24.21.0、pnpm12.14.0；React/DOM19.3.1、TS7.0.2、Vite8.3.5、plugin-react6.1.2、React/DOM类型19.3.0、Router8.5.0、Query5.104.5均精确固定。组件中分别执行corepack pnpm@12.14.0 install --frozen-lockfile、typecheck、build，退出均0。冻结安装校验73条并跳过重新解析；主类型检查strict，未关闭库检查。最终构建JS index-BjB70CqV.js约299.32kB（gzip94.38kB），CSS index-DA1EDhNF.css约3.69kB。主题CSS由运行期FastAPI提供，构建期提示非错误。pnpm生成的最低发布时间例外仅vite@8.3.5，未放宽全局策略。 |
| 真实闭环 | MTRL_PREVIEW_SOURCE_ENV指获准原仓配置；在仓根执行backend/.venv/Scripts/python.exe -X utf8 -m pytest apps/frontend/tests/test_preview.py -q --tb=short，最终5 passed，退出0（14.36s）。真实Alembic、PostgreSQL、隔离FastAPI、实际构建与Chromium；验证登录/HttpOnly/Lax独立Cookie、身份、active/archived筛选、重载、空结果、真实普通用户管理动作被拒且账号数不变、失效Cookie的无身份及401。加载/403/500和迟到错误的UI分支为定向回包替身，未将其当真实权限证明。 |
| 身份/主题/键盘 | 账号key重建页面与QueryClient，退出取消请求并清缓存，身份重新取数时丢弃过期响应；测试切账号后筛选清空，前账号迟到错误不显示。当前没有实际编辑草稿或历史摘要，后续须放同一账号子树内；本票验证其所有权边界，未声称已实现398的编辑或历史功能。主题复用现行CSS和本地MiSans，用户倍率来自ui_scale_css；普通用户深色1.12、800×900以及默认1920×1080实际看图。Tab到查询并Enter执行通过；窄屏仅表格内部横滚，无整页溢出。 |
| FastAPI生产形态 | 默认FRONTEND_PREVIEW_DIR为空时无/preview路由；显式配置dist才提供/preview/projects、带hash资源；HTML no-cache、缺失assets404，/app字节与现有index.html一致。固定8037实例实际由内置浏览器登录和刷新，1280视口无整页溢出，computed font为MiSans；会话重启后随机密钥不复用。调查基点继续33a9bb4，后续旧版差异由父任务按本批SHA及共同调查点核迁移面，不重置累计起点。 |

**验证选择与失败关闭。** 本批包含新身份/缓存/静态出口，做累计自查与定向真实回归；父任务承担独立验收和整体双轴，本执行批未冒充独立审查。既有定向命令：pytest backend/tests/test_static_conditional.py backend/tests/test_session_long_login.py backend/tests/test_layering.py -q --tb=short，46项，退出0；保护旧缓存/会话/分层。初次TS检查退出1（CSS副作用导入缺声明）已补assets.d.ts；首轮浏览器3失败/1通过，状态label的可访问名称不明确已修，权限测试误用表单改真实JSON接口后通过，保留原始失败结论。后两轮5项均通过。唯一pytest warning为已有Starlette/httpx弃用提示，未为该提示扩依赖。

**环境审计边界。** doc_audit最初无.env缺基线，报缺配置；其CLI不支持--baseline且不读进程环境，最终在确认根.env不存在后临时写入仅公开PRD路径的配置，运行原工具并finally删除。完整审计退出1：必须修1/疑似33/豁免15，唯一T3为docs/guides/operations.md引用的ops/nssm/nssm.exe不存在。对应文档与HEAD无差异，二进制未跟踪且按既有规则忽略；不为预览安装NSSM、不造假文件、不改断言。新增apps目录及引用已接ROOT_ALLOW/TOP_DIRS，未产生本批新红项。impeccable机械检测返回[]；workspace_check active退出0。文档采用writing-for-agents的唯一主人和按动作入口，不复制业务口径。

**隔离、访问与生命周期。** 已确认mtrl_workbench_test/mtrl有CREATE schema权，原库/测试库经TestDatabaseGuard区分，随机frontend_rewrite_397_<uuid>为本批自建且搜索路径不含public。迁移和数据仅该schema，未操作共享public或真实业务库；未复制原仓.env，密钥只在进程内。preview-admin/preview-user空密码只用于构造数据，Cookie名mw_preview_397避免跨端口覆盖现用mw_session。启动命令为backend/.venv/Scripts/python.exe -X utf8 tools/dev/frontend_preview.py --source-env <已授权配置> --port 8037；入口http://127.0.0.1:8037/preview/projects。验收实例均已停止；Ctrl+C时应用停止并输出ISOLATION cleaned，宿主PTY取消返回1，清理完成后没有残留监听；启动器已捕获正常KeyboardInterrupt避免打印堆栈。自动回归每轮在服务退出后drop自有schema。硬杀/掉电仍需按准确schema名核所有权，禁止前缀批删。

**证据选留与下一批。** 本机原始截图/日志在.artifacts/archive/frontend-vue-rewrite，最终键盘/窄屏轮为121611-985967-26044，retention.json到2026-11-21；首次失败轮120632-430324-13500保留用于归因，无活动run。后端var/log/frontend-397为隔离实例运行日志，依赖/缓存和dist留工作树供验收/398接续；整体effort仍活动不做closed。398只需复用账号子树、api.ts、React Query、/preview和该隔离启动器，在其中加历史台账路径与草稿/历史接线，不复建全局缓存，不提前触碰399复杂网格。没有推送、正式部署/重启、真实写入或i8/打印动作。

**保存与验收归属。** 本执行者只提交本批源码/必要文档和原票；Status保持claimed，父任务验收后按既有销号工具更新公共状态/历史索引。本地提交SHA由最终回执提供，不为自指SHA再造提交。未跑后端全量、398编辑/金额/导出/网格、正式现场或跨设备；这些不能由本批51项定向结果推导。


**2026-10-22 · 父任务验收修复：临时身份核验失败保留上下文。** 父任务指出02a29b2的窗口焦点检查在网络失败/500时setMe(undefined)，并通过error早退卸载账号树，清QueryClient和筛选。先在原实际构建上执行pytest apps/frontend/tests/test_preview.py -k 'temporary_identity and network' -q --tb=short，退出1：恢复同账号后状态实际active，预期archived；失败轮123325-173524-1320的独占schema已清理。该反馈直接证明本次症状，不扩展成全仓诊断。

修复分三态：初次身份读取失败只提供重试；已有身份核验中/暂时失败保留已挂载账号树，隐藏数据并inert阻止操作，取消/暂停查询；确认同账号恢复原上下文并重新读取，确认换号/会话失效才重建树并清缓存，后续重新确认有效身份清除失效提示。未提前实现398草稿。已更新唯一预览指南：398编辑中必须覆盖焦点身份网络失败/500后恢复同账号保草稿，暂停期间不得发起保存，确认换号/失效不得串用旧状态。

修复后原命令pytest apps/frontend/tests/test_preview.py -q --tb=short为10 passed、退出0（28.75s），包含原5项、网络/500同账号恢复、失败后确认换号/失效清上下文、初次身份失败无数据；暂停时可见table和切账号入口数均0。末次补齐失效后重新确认有效账号的提示复位，定向-k 'temporary_identity and expired'为1 passed/9 deselected、退出0（7.25s），未重复其余有效保障。最终Vite build退出0，JS index-D8lQHLy-.js约299.76kB，CSS index-CxJbAjDx.css约3.72kB；严格类型检查通过，无依赖变化。实际看图：暂停只见错误/重试，恢复后仍为归档、未提交关键词及归档样例。绿色轮123521-372697-32032和末次123731-131328-23260的日志/截图按既有30天期限归档；未触碰正式服务或398。

**2026-10-22 · 按用户新证据复核临时文件清理。** 用户明确要求去掉-Force；上次首个删除拒绝后14项均未删除。已按14个精确绝对路径核对存在、普通文件且无链接，创建/修改时间均对应本批，脚本源码已在本轮创建记录中核对；无需保留的独有结果，实际源码/验收证据另有Git与归档。仅通过正常工具一次执行Remove-Item -LiteralPath <精确文件> -ErrorAction Stop，不带-Force、不用通配、不改ACL/所有权。仍在首项C:/Users/Administrator/AppData/Local/Temp/tail397-preflight.py报Access denied，操作状态为拒绝；随即停止，逐项复核结果为14存在、0删除。工具未给自动审批策略拒绝说明，不把系统Access denied伪称不可覆盖策略。未换工具/权限/路径重试，需父任务或用户在有实际删除权限的正常环境处理。

14项均在C:/Users/Administrator/AppData/Local/Temp/，精确文件名：tail397-preflight.py、tail397-write.py、tail397-backend.py、tail397-fix.py、tail397-tests.py、tail397-testfix.py、tail397-fix2.py、tail397-docs.py、tail397-finalfix.py、tail397-audit.py、tail397-exitfix.py、tail397-evidence.py、tail397-final-db.py、tail397-commit.py。本次修复使用短脚本stdin，没有再创建Temp辅助脚本。

**2026-10-22 · NSSM红项根因查清（只读）。** 原仓D:/dev/mtrl-workbench/ops/nssm/nssm.exe存在（331264字节）；正式mtrl-workbench-server状态Running、LocalSystem，PathName正为该文件，Application为原仓backend/.venv/Scripts/python.exe，AppDirectory为原仓backend，参数为uvicorn监听8000。工作树对应文件不存在，因为该工具按既有.gitignore不提交，Git worktree不复制它。属于工作树未共享本机运维运行资源，不是过时路径或正式部署缺件；文档引用与真实部署一致，无纯文档误指向可修。最小处理建议：保留正确引用与本工作树审计环境差异，不为397隔离预览下载/安装/复制正式服务工具，不放宽T3；如父任务另要求该工作树完整运维审计归零，应单独决定运行资源准备方式。本次仅查询服务信息和三项非秘密注册参数，没有启停/执行NSSM或读取服务环境凭据。
