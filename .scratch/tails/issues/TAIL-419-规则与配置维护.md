# TAIL-419: 规则与配置维护

**What to build:** 查看和修改现行规则配置，获得准确校验及历史影响说明。

**Blocked by:** TAIL-399

**Status:** claimed

- [ ] 规则读取、允许字段编辑、校验和保存回执完整可用，权限由服务端判定。
- [ ] 现有配置默认值、缺失/空值和历史保护含义保持，不暗示修改配置会自动重算历史。
- [ ] 隔离验证有效修改、非法值、无权限及冲突失败，真实重读与相关业务页面效果一致。
- [ ] 配置说明及错误提示沿现行熟手口径，技术细节按既有排障边界处理。

规格：[前端独立重做规格](../../frontend-vue-rewrite/spec.md)（User Stories 37, 5, 9, 25）；业务口径：[MOD-14](../../../docs/requirements/PRD/02-功能规格/MOD-14.md)。

验证类型：浏览器可观察行为＋实际后端/隔离数据库；涉及导出时检查实际文件，涉及外部系统时使用明确替身边界。复用有效既有保障，按本票风险补缺，不重复整套检查。

---

## Comments

**2026-10-22 · 建票（agent）。** 来源：用户2026-10-22确认React前端28票及依赖｜不做会怎样：新前端该用户路径或累计交付缺少独立验收与接续依据｜落点：新前端独立副本；规格及本票验收｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①按已批准依赖解锁后续②先验收再扩大迁移③同批共享隔离与交互边界④依赖和验收见本票

**2026-10-22 · 授权与执行入口。** 已批准建票及上述依赖，后续采用 implement-solo-spec 跨批统筹；本轮仅建票，尚未授权开始实施。ready-for-agent 仅表示任务已说清，仍需实施启动授权；外部真实动作、正式切换及退役各守规格授权门。

**2026-10-22 · 父排期：先行i8连接地址编辑小切片（本轮仅记录）。** 配置编辑自然归本票，直接依赖399已满足。400有界修补技术收口后，由父另开新执行线程提前完成本切片，再开i8整页人工关口；不等本票全部规则，不把本票整票标完，当前仍ready-for-agent、未实施。入口保留i8页，仅 `i8_base_url`，复用现有 `settings_api` 的服务端保存、留痕、缓存失效；保留清空后回落环境配置语义。打开/保存不试连、不外部登录，不连带打印配置；个人凭据420和打印406不扩。400仍仅配置查看，缺地址编辑时不能报整页候选。

**2026-10-22 · 先行地址切片实施（待父审）。** 父任务明确下达本切片，基点 `b423f58c2611ee610c08077ef899ac8e71afd151`、分支 `codex/react-frontend-rewrite`、初始clean。只承接i8页服务地址编辑、服务端校验/保存/重读、生效值及来源；清空回落环境配置。419标claimed，其他规则继续待办，未勾整票验收、未推进401；个人i8绑定420、打印406保持原范围。

`settings_api`原先给未传键补空，实际与“只保存传入键”注释相反；现只收实际传入的允许键，继续同一repository保存/逐项留痕/invalidate出口，旧全字段客户端仍兼容。新界面正文只提交 `i8_base_url`，可选 `expected_account` 查询参数由现有身份出口核对，防换号后旧表单写入。地址沿既有协议支持范围校验主机/端口，拒绝空主机、非法端口、夹带凭据/空白/查询参数；空串合法。未触碰打印配置、配置文件或历史业务数据。

**行为与证据。** 打开/保存均无试连、登录、取数、同步或打印；固定替身对外发送全部阻断。输入失败保留、取消/Escape不写入且焦点回入口；同步门防连点；已保存但重读失败与保存结果不明分开。结果不明按账号保留本页签状态，重开/刷新仍先重读，并由操作者确认无在途保存后结束核对；不会自动重投。切换账号销毁旧编辑器/草稿，服务端校验实际账号，迟到回执不覆盖新身份。

真实反例保留：`http-red.log`（1失败，退出1）证明旧账号期望原先未被拒；首轮 `browser-first.log`（3失败/3通过，退出1）暴露取消焦点及核对后隐式重投。后者是同一DOM按钮从button变为submit时触发默认提交，现分离按钮身份并阻止默认行为，最终断言核对过程仍只有1次POST且留痕不增加；`browser-focus.log`保留中间1失败/2通过及诊断，另修测试等待真实替身响应的时点，未删除业务断言。

最终仓根 `python -X utf8 -m pytest apps/frontend/tests/test_i8_settings.py apps/frontend/tests/test_i8.py apps/frontend/tests/test_preview.py::test_switch_account_drops_old_scope_and_late_response -q --tb=short -s`：**18通过/58.90秒，退出0**（`browser-final.log`及JUnit）。覆盖真实拒绝/非法/合法/清空、实际m02生效重读、改前改后/人/时间及打印两键不变；另覆盖取消/关闭、连点、403保输入、写入后丢回执、已保存但重读失败、换号和迟到响应，并复验400原11项。沿94e91aff模块browser、逐例context及模块独占schema/日志隔离，不以pytest回滚保护浏览器写入。已看浅色1080P和800px深色大字号实际截图，弹窗与按钮可读，无内部横向溢出。

后端目录显式 `DATABASE_URL='' TEST_DATABASE_URL=''`，仅 `tests/test_acc_cfg_setup.py -o addopts='' -q --tb=short`：**8通过/0.23秒，退出0**（`config-offline.log`及JUnit），覆盖原取值优先级/端点推导/打印项等离线口径。一次拟加跑cfg_setup+i8_manual_safety的组合命令被自动审批拒绝，原因是它会把正式源地址交给子进程，可能违反正式写库边界；命令未执行、脚本未创建，未重试。改用上述显式无数据库离线检查；真实写入只由已获准的HTTP/browser独占测试schema证明，不冒称该被拒组合跑过。

**审查与未验。** TS7 typecheck和Vite build均退出0；Impeccable detector `[]`/退出0；静态钩子、文档和资源收尾另补实际结果。依本票清单自查，固定范围为b423f58到本切片累计差异；父承担真实独立审查，本线程不冒称独立双轴。未跑全仓或MOD05/06既有分层B/C，后者仍归422；未访问真实i8、强踢、同步、打印投递、正式库写入/迁移、正式服务、push/部署或人工预览。400技术审查已由父确认，i8完整页人工关口仍须本切片经父审及整页验证，400/419均未标人工通过或整票done。必要原始证据选留 `.artifacts/archive/frontend-vue-rewrite/tail419-address-20261022/`，沿effort既定2026-11-21期限；资源复核/run-closed/提交结果在收尾补记。

**2026-10-22 · 静态与资源收尾。** `syntax_audit --staged`退出0、必须修0；`bytes_guard --staged`最终8件退出0、必须修0，另按同一check规则显式核2件TSX退出0。首次bytes退出1为本轮CSS追加混入CRLF，已恢复原LF并复验；无工具豁免。doc_audit退出0、必须修0/既有疑似33；本工作树独占临时.env仅公开PRD路径，finally核内容删除。typecheck/build执行现有package脚本，未安装依赖或变动包管理器/锁，原大chunk与主题资源提示保持。

资源以本轮 `reports/resource-db.json`、`resource-processes.json` 为准：7个精确owned schema均已不存在、对应连接0；8个登记PID及监听端口均不存在，fixture已closed。自身work脚本、Vite临时缓存与空目录已释放，必要日志/JUnit/合成截图已实际归档到上述本机证据位置；父审所需dist随既有worktree生命周期保留，未清其他任务资源。`workspace_check.py check --effort frontend-vue-rewrite --run tail419-address-20261022 --phase run-closed`退出0、ok=true；effort仍在办，未执行effort closed。保留真实提交钩子，本地提交号及clean状态由最终回执提供，未push/部署。

**2026-10-22 · 成功标记缺失的最终补检。** 最后自查把settings回执的 `ok === true` 纳入严格读取；有地址明细但缺明确成功标记也按结果不明处理。沿同一隔离实际写入→截去ok→浏览器核对场景新增参数，最终单跑 `apps/frontend/tests/test_i8_settings.py`：**7通过/23.10秒，退出0**（补充run `tail419-receipt-20261022` 的 `settings-final.log`/JUnit）；TS7 typecheck与Vite build再次退出0。该7项替代前述18项中的地址6项最终证据；400原11项及共享换号1项输入/预期未变，沿用58.90秒那次有效结果。未增加功能、依赖或外部动作。补充run的1个owned schema/连接及1组进程端口已只读核无残留；最小日志/报告/合成截图按同一2026-11-21期限选留，最后run-closed结果回最终回执。

**2026-10-22 · 独立审查P2有界修补（待父复审）。** 基点 `c3afdface68b4f1543c5feb2537accd50d2cf273`、初始clean；父未放行两项P2并要求补旧POST仍在途证据，本轮仅修补419地址切片。旧记录“人工勾选确认无在途保存”的恢复方式已被下述版本校验替代，400外部任务原核对方式不变。

红灯 `review-red.log`：**2失败/7未选、退出1**，真实隔离后端已保存后截断JSON，界面却按status200解除未知锁；111字符空姓名合法账号保存返回500。后者服务日志为StringDataRightTruncation，两个64字符字段均属于配置主人。现在API错误仅为解析出的ok:false附明确拒绝标记，地址保存不再把所有status200当拒绝；网络中断、缺ok及坏JSON保留未知锁。模型 `app_setting.updated_by` 与 `app_setting_log.operator` 无损Text，迁移 `c419261022` 前置c400；回归用111字符空姓名账号真实登录→版本化地址保存→配置/留痕重读，两个完整身份均一致。

**在途与恢复。** 仅地址复用现有updated_at为不透明版本，GET从同一数据库行取值/版本，POST在既有事务锁惯例下比较 `expected_version` 后复用原save/留痕/invalidate；同值或缺行空值保存也推进版本，防旧请求再次命中，不伪造值变更日志。新客户端每次都带版本及账号，旧客户端未带版本仍兼容并推进地址版本。结果不明先重读即可恢复编辑，后续保存受版本约束；无需用户判断旧POST是否结束。不增加通用任务表、后台取消或打印设置，仍只提交i8_base_url。

固定外部替身内用异步事件将真实旧POST保留在途，浏览器先丢回执再重读；分别验证新保存先提交（旧请求随后409）、旧请求先提交（新请求409且保留输入，重读后可保存）、新保存同值也阻止旧覆盖。另验证缺行/空值保存推进missing版本。所有新保存成功后重读的实际配置及m02生效地址保持新值，无人工勾选。未知态截图已看，旧值标“上次读取”，保存按钮用禁用样式，重读入口可操作。

**定向结果。** 最终选集为 `test_i8_settings.py`（13项）、`test_preview.py::test_explicit_test_dsn_rejects_other_database_and_source_copy`（2项）、原 `test_i8.py::test_invalid_address_disables_execution_and_safe_reads_never_login` 及 `test_preview.py::test_switch_account_drops_old_scope_and_late_response`（各1项）：**17通过/39.56秒、退出0**（settings-final.log/JUnit）。中间12通过/24.13秒保留作过程；第一次临时runner因缺run变量退出1、尚未启动测试，未掩盖该脚本错误。原8项配置离线断言保留，用新快照读取接缝替身继续无数据库运行：**8通过/0.34秒、退出0**（config-offline.log），与17分别记数，不同旧18/7等复验相加宣称独立33项。

迁移专项 `migration.log`总退出0：旧两表值/身份/时间逐值保留，升级后两身份列均Text，111字符可完整保存；含长身份的降级子命令预期退出1并明确refusing to truncate，随后数据及head均不变，未执行成功降级。只在独占mtrl_workbench_test schema迁移，正式schema未动。

本轮fixture新增显式测试DSN入口：仅mtrl_workbench_test，禁止copy_source；缺目标失败、无public回退，实际数据库/schema/search_path仍在seed及后端启动核验。受控runner仅提取TEST_DATABASE_URL，不把正式DSN传子进程；未重试此前被拒的后端组合。模块browser/逐例context、schema日志与finally清理保持。最终TS7/type和Vite/build均退出0，必要静态、最后2项UI复验与资源收尾另补实测结果；不跑全仓、不改既有分层B/C归422、不推401/其他设置，不真实i8/强踢/打印/正式写入/部署/人工预览。必要证据归档 `.artifacts/archive/frontend-vue-rewrite/tail419-review-20261022/`，沿2026-11-21期限，父复审仍独立进行。

**2026-10-22 · 用户纠偏后的停止点与最小收尾。** 用户明确实际大概率仅两账号，父要求立即收缩过度防御。本轮长身份Text源码/测试库迁移和地址专用版本核对在收到纠偏前已完成，保持现状供父裁减，不机械回滚；从此停止新增迁移、并发协议、边界回归或审查，不再把长账号作为页面验收阻塞。地址版本代码只复用现有updated_at及同一事务锁，无新增表/列/通用平台；用户是否保留此已完成范围由父按主体目标决定。419仍claimed、401及其他设置未推进，未宣布人工通过。

已完成：上述17项定向检查及8项离线检查分别通过；最后界面2项复验12.07秒和禁用样式单项8.59秒均退出0，属于重叠复验，不追加独立用例总数。最终type/build、syntax/bytes均退出0；按同一字节规则补查TS/TSX退出0，detector []；文档扫描必须修0/既有黄33。8个本轮精确schema均已清理、对应连接0；7组owned进程/端口已退出。一次PID23520复核短暂非空但无监听，最后只读再查已不存在，未停止任何不明或他人进程，过程保留于resource-processes.json。本机原始日志/JUnit/截图留原定期限，work释放、归档、真实本地提交钩子和run-closed在本次最小收尾完成，结果回最终回执。未重试此前被拒组合，未传正式DSN、未生产/外部动作、未push/部署或人工预览。

**2026-10-22 · 用户决定删除超长账号专用测试。** 基点da449413、工作区clean；按用户明确两账号规模与“删除为此创建的测试”执行极小清理。移除 `test_long_blank_name_account_is_preserved_in_settings_and_log`（1用例）、LONG_ACCOUNT/专用账号种子/不再使用的UserAccount导入，以及只供它使用的 `/__test__/settings-state` 快照端点和AppSettingLog/select导入。连同400移除2个测试函数、3个参数化用例；未增同义测试，正常身份留痕/保存、金额/导出、坏回执等原保障保留。已完成模型、迁移和保存修复均不改；孤立迁移回退超长场景没有Git内长期测试，原一次性work脚本已释放，不改归档历史。此前17/长身份等通过记录仅表示当时覆盖，不能冒称当前仍保留。仅进行两模块collect-only、必要静态/真实提交钩子与本轮收尾，不跑整页或扩全仓清理；419仍claimed，未push/部署、未推401。具体结果及提交回最终回执。

本次最小验证：`pytest apps/frontend/tests/test_i8.py apps/frontend/tests/test_i8_settings.py --collect-only -q` 退出0，21项收集/0.46秒；仅证明保留用例可收集，未执行用例。四件相关测试文件专用账号/函数/端点残留定向检查通过，diff空白检查通过；真实提交钩子与run-closed结果见最终回执。未启动服务/浏览器或创建schema/端口，未重跑整页套件。后续重构测试清理由父另开有界批次，当前不扩大。
