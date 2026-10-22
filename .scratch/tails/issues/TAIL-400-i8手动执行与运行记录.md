# TAIL-400: i8手动执行与运行记录

**What to build:** 由明确人工动作发起 i8 任务，查看配置、顶号告知、执行进度和结果记录。

**Blocked by:** TAIL-399

**Status:** claimed

- [x] 配置、手动触发、冲突/顶号告知、运行记录及成功/失败结果保持现行含义；读取记录不触发外部登录。
- [x] 组件挂载、开发重挂载、查询重试和重复点击均不隐式重复登录、抓取或投递打印。
- [x] 固定外部响应替身验证真实隔离后端的成功、失败、冲突和失效配置；结果刷新归属正确。
- [x] 报告清楚区分隔离替身与真实外部执行，实际 i8 登录/抓取和打印投递仅按另行明确授权执行。

规格：[前端独立重做规格](../../frontend-vue-rewrite/spec.md)（User Stories 11, 12, 8, 9）；业务口径：[MOD-02](../../../docs/requirements/PRD/02-功能规格/MOD-02.md)。

验证类型：浏览器可观察行为＋实际后端/隔离数据库；涉及导出时检查实际文件，涉及外部系统时使用明确替身边界。复用有效既有保障，按本票风险补缺，不重复整套检查。

---

## Comments

**2026-10-22 · 建票（agent）。** 来源：用户2026-10-22确认React前端28票及依赖｜不做会怎样：新前端该用户路径或累计交付缺少独立验收与接续依据｜落点：新前端独立副本；规格及本票验收｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①按已批准依赖解锁后续②先验收再扩大迁移③同批共享隔离与交互边界④依赖和验收见本票

**2026-10-22 · 授权与执行入口。** 已批准建票及上述依赖，后续采用 implement-solo-spec 跨批统筹；本轮仅建票，尚未授权开始实施。ready-for-agent 仅表示任务已说清，仍需实施启动授权；外部真实动作、正式切换及退役各守规格授权门。

**2026-10-22 · 正式开工。** 父任务明确授权单票400，固定基点94e91affb5faa982de72371ec546eebc75c7dfc2、worktree干净。399技术前置由父任务有限放行，398仍待完整页面人工验收。只做配置查看、手动抓取、安全确认及记录；401仅预留两个同步入口可复用的安全接合，不推进401，不push/部署。隔离测试使用合成种子和固定外部响应替身，不登录真实i8。

**2026-10-22 · 实施中检查点。** 配置只读查看、付款通知书人工抓取、冲突/强踢确认、等待状态、最近结果与执行记录已接线；401两个同步仅复用安全确认/账号校验接合。TS7与生产构建通过；真实隔离库已复现并修正设置读取漏传Session。后端定向80项中78通过、2条分层失败在94e91aff只读快照同样复现，未改其余模块。浏览器已验真实写入/操作人/耗时及无隐式执行，正在修正新筛选控件可访问名称并继续其余中断/换号场景，尚未技术交付。无授权阻塞；不push/部署/真实i8/打印，不推进401。

**2026-10-22 · 实现与本票边界。** `/preview/i8` 已提供有效地址/个人绑定只读查看、按月付款通知书人工抓取、默认不强踢与在线冲突后二次确认、等待回执/已等待秒数、明确范围的回执、六类来源最近结果与最多200条全部执行记录。POST `/fetch/preview` 未接入任何挂载/查询，实际写入复用 `/api/m03/notices/fetch`；无通用导入入口/降级文案，无完整设置或其他业务页扩展。`i8-execution.tsx` 由账号工作区持有，401可复用 `prepare` 的两个同步种类；401完整同步/建档验收仍未实施。新客户端同时提交 `expected_account`，服务端在外部取数前拒绝过期账号；重复点击同步闸、失败不自动重发、回执不明的同账号sessionStorage锁及人工读记录解除均已实现。进度如实表示“正在核实账号/等待回执”，不伪造服务端逐条百分比。

**关联缺陷与兼容。** 真实隔离库暴露既有 `core_bindings._settings_values` 漏传Session，导致库内设置被回落；`config-red.log` 退出1可复现，已最小修复并补真实库回归，原转发测试改用真实签名，未削弱断言。运行记录继续原表、无迁移，两个写记录出口记录当前操作人，读取附带真实时间差；旧 `manual` 不冒充当前账号。在线冲突用独立409码供明确确认，旧客户端不传 `expected_account` 保持兼容。看图修正窄屏动作列挤压及回执UTC误当本地时间。

**检查与证据（按影响选测）。** 基点94e91aff；项目Python3.15.1、Node24.22.1，uv锁定离线检查退出0（74包无改动），无依赖安装/锁变动。实际运行：
- `node node_modules/typescript/bin/tsc --noEmit` 与 `node node_modules/vite/bin/vite.js build`：最终均退出0。现有主题运行时URL与网格大chunk提示保留；未设独立前端lint/aggregate脚本，静态入口按仓库syntax/bytes/doc_audit执行，结果见收尾补记。
- 真实隔离后端pytest选集：`test_i8_manual_safety.py test_core_bindings.py test_acc_cfg_setup.py test_acc_i8_fetch.py test_acc_i8_src.py test_run_record_timing.py test_notice_fetch_skip.py test_i8_cookie_cache.py test_unresolved_freshness.py test_layering.py test_dup_guards.py`，`-q --tb=short`，**78通过、2失败，原始退出1**。两失败为layering B/C：mod05_flow/service.py、mod06_proc/workbench_api.py直引导出层，mod05_flow/router.py直引项目repository；94e91aff只读快照同样2失败/4通过（9未选），`layering-head.log`退出1，均非400新增，未扩大修复范围。
- 仓根 `python -X utf8 -m pytest apps/frontend/tests/test_i8.py apps/frontend/tests/test_preview.py::test_switch_account_drops_old_scope_and_late_response apps/frontend/tests/test_ledger.py::test_real_undo_redo_conflict_and_account_ownership -q --tb=short -s`：**11通过/41.36秒，退出0**，`browser-final.log`及JUnit。包含真正Vite开发态StrictMode/重新挂载、只读查询失败重试、成功写入/耗时/操作人、重复点击、切月导航、冲突强踢、失败手动重试、回执丢失后重载阻止重投、部分成功、换号迟到结果、配置缺失与既有撤销权限。
- 最后仅列宽/本地时间变化，复跑 `test_success_duplicate_click_navigation_late_month_and_real_duration`、`test_account_switch_rejects_stale_actor_and_drops_late_receipt`：**2通过/12.99秒，退出0**（`browser-visual-fixed.log`）。逐例context、模块浏览器、模块schema与pageerror断言保持；真实库assert没有public回退。1080P浅色、800px深色大字号及确认弹窗已实际看图，记录在自身容器横滚、按钮/列可读。
- 早期非零均保留：新测试引号/相对URL、筛选可访问名称及换号等待点问题分别修正；`config-red.log`为实际产品缺陷红灯。未跳过有效断言或用重试掩盖首次失败，最后两次通过绑定最终输入。

**审查与未验。** 本执行线程按本票清单自查；原模块业务与共享接合已定向验证，统一父任务承担真实独立审查，本线程不冒称独立双轴。未跑全仓、真实i8登录/抓取/强踢/同步、打印投递、正式业务库写入或正式服务检查；未push/部署/邀请人工预览。技术实现与定向结果供父审；`claimed`保持，未销号、未标人工通过，也不推进401。网络中断后不猜哪条“最近记录”属于本次任务，必须人工确认无在途任务后才允许重新准备；无服务端取消/通用任务平台。

**本机证据与收尾。** 必要日志、JUnit和合成截图选留 `.artifacts/archive/frontend-vue-rewrite/tail400-20261022/`，沿effort既有retention到2026-11-21，不延长旧期限。进程/端口由fixture的Popen持有并写owned/closed；schema按精确随机名、owner核对后finally删除。最终资源复核、静态结果及本地提交在收尾补记；不把测试进程回滚当浏览器隔离，不清理他人资源。

**2026-10-22 · 最终补检与收尾。** 自查发现名单同步/旧m02抓取在“0成功/0失败但有错误”时曾写成success；`zero-failure-red.log`退出1已证实。只改fetch_record_payload失败判定一行，正常空结果仍保持成功，未改退役降级文案或历史数据。最后选测 `test_i8_manual_safety.py test_acc_i8_fetch.py test_run_record_timing.py test_acc_setl_fetch.py test_acc_inv_fetch.py test_acc_jc_fetch_orch.py -o addopts='' -q --tb=short`：37通过/1失败，退出1（`backend-final.log`/JUnit）；新零行失败真实写记录回归通过。唯一失败为收发结存“陌生仓库自动建档扶正并逐条列出”，原始94e91aff代码与原测试在独占schema同样失败1/未选9（`setl-head.log`）；尚未进一步区分其既有测试/产品原因，不在400修复。合计保留3条已在基点复现的失败（2条分层、1条建档），不把非零选集报成全绿。

静态入口：TS7/最终build退出0；syntax_audit --staged退出0，必须修0；bytes_guard --staged最终覆盖20件、同一check规则额外覆盖5件TS/TSX，均退出0；Impeccable最终检测[]/退出0。doc_audit必须修0、疑似33、退出0，未为基线黄项扩票；首次缺基线与不支持--baseline参数各退出2，随后沿既有配方独占临时本worktree.env仅写公开PRD路径，finally核内容删除，未写D:/dev配置。最后提交运行真实语法/字节钩子。

资源复核以本机reports/resource-db.json、resource-processes.json为准：本轮精确schema均已不存在、对应连接为0；已登记服务/dev进程均已wait退出，PID与端口无残留，无临时.env或测试导出。必要日志/JUnit/合成截图选留原定30天位置，工作脚本、两份基点源码快照、Vite临时缓存和schema工作目录均由本轮释放；最终前端dist供父审保留，随现有worktree生命周期管理。run-closed与本地提交结果以本次最终回执为准；整个frontend effort仍在办，未执行effort closed。

**2026-10-22 · 独立审查后有界修补（待父复审）。** 起点1a809030861f979cc9507d9adc74bb57f8e405b3、工作区clean；父独立审查未放行，按P2修补后再交回。`current_operator` 在姓名为空时合法回退完整账号，而原 `run_record.triggered_by` 仅64字符：111字符合成账号的成功取数和外部失败两条真实HTTP路径均在flush时500，外部原错被盖住（`long-account-red.log`：2失败，退出1；服务日志确认StringDataRightTruncation）。模型改Text，新增迁移 `c400261022`（前置c391261021）保留完整值；此前“无迁移”的实施记录由此补正。降级先锁表并检查超长值，存在则明确拒绝截断。只在mtrl_workbench_test独占schema执行，正式库未迁移；以后部署本改动须先按正式授权升级schema。

**修复证据。** 固定外部替身新增专用失败月份，合成账号姓名为空、111字符，保留真实登录态→原取数解析/归属→隔离PostgreSQL→记录读取。`test_long_account_preserved_in_success_and_external_failure` 两参数分别验证HTTP200/完整成功留痕及HTTP502/原external_service消息/完整失败留痕，真实耗时、仅一次外部替身调用和数据有无均断言。随原9条浏览器流程运行 `python -X utf8 -m pytest apps/frontend/tests/test_i8.py -q --tb=short -s`：**11通过/30.68秒，退出0**（`i8-final.log`、JUnit）；模块browser/逐例context/日志按schema隔离及外发阻断保持。未改前端产品源码。

迁移专用隔离验证 `migration.log` 总退出0：在c391的varchar(64)旧表保留合成旧身份和原错误，再升级head逐值不变；写入111字符后，降级子命令按预期退出1、明确refusing to truncate，随后核Text/head/完整长短身份均未改变。该预期拒绝不算成功执行降级，不涉及生产库。

**建档夹具与零行错误复验。** 父审离线定位的建档失败是固定客户端输入缺少有效i8地址；仅在原 `test_陌生仓库自动建档扶正并逐条列出` 补 `http://fixed-i8.invalid` 缓存输入，客户端和导出仍为替身，全部原断言保留（扶正1/创建0、逐条结果、未归属及降级等）。独占schema中运行 `tests/test_i8_manual_safety.py tests/test_acc_i8_fetch.py tests/test_run_record_timing.py tests/test_acc_setl_fetch.py tests/test_acc_inv_fetch.py tests/test_acc_jc_fetch_orch.py tests/test_notice_fetch_skip.py -o addopts='' -q --tb=short`：**47通过/2.95秒，退出0**（`backend-final.log`、JUnit），含该原节点及 `test_failed_zero_row_sync_is_not_recorded_as_success`。前轮零行错误修复与红灯/最终通过证据保留，未删除断言，也未扩大退役通用导入。

**非阻塞项与页面关口。** layering B/C是真实的MOD05/06既有架构违规，按父裁定记入[422累计收口](TAIL-422-累计集成验收与切换准备.md)，本轮不改架构、不加豁免；此次未重跑分层或全仓，不能据定向通过宣称全绿。400继续只承接配置查看；地址编辑归[419先行切片](TAIL-419-规则与配置维护.md)，父将于400技术收口后另开线程完成，再开i8整页人工关口，不等419全部规则，也不把419整票标完。个人凭据420、打印406、401业务均未扩展；本轮不报整页候选，不发起人工预览、真实i8、同步、打印、push或部署。票仍claimed待父复审。

**本轮静态与证据。** TS7 `tsc --noEmit`、Vite build均实际退出0，既有主题URL/大chunk提示仍在；无独立lint/aggregate脚本，语法/字节/文档按仓库入口，最终结果及清理见收尾补记。必要日志/JUnit/合成截图在 `.artifacts/archive/frontend-vue-rewrite/tail400-review-20261022/`，沿effort既定2026-11-21保留期限，不延长；原tail400-20261022证据不动。

**2026-10-22 · 修补静态与资源补记。** syntax_audit --staged、bytes_guard --staged（10件）均退出0、必须修0；doc_audit退出0、必须修0/疑似33，独占临时worktree.env仅公开PRD路径并已finally删除。未新增架构豁免。4个精确owned schema及对应数据库连接均已不存在；3组日志登记的preview/dev PID及监听端口均不存在、fixture均closed（reports/resource-db.json、resource-processes.json）。清理解析器首次遇空日志产生非终止报错，按字符串空值修正后重新只读核对，退出0，未因此重跑业务测试。本次按P2及夹具差异自查，父复审仍另行；本地提交保留真实钩子，工作脚本/缓存释放、归档与run-closed最终结果见回执。整个effort继续在办。

**2026-10-22 · 父复审结论与地址切片接续。** 父本次委派确认b423f58修补已通过独立技术审查：长账号Text迁移、111字符成功/外部失败原错保留、建档有效假地址夹具及零行错误回归均通过，400技术阻塞解除。既有47后端+11 HTTP/browser及hooks/type/build证据仍以本票原记录为准。当前419先行地址切片已实施并完成定向检查，待父审，证据回[419原票](TAIL-419-规则与配置维护.md)。400仍claimed，完整i8页人工验收待本切片通过及整页验证；未代用户验收、未销号、未推进401。MOD05/06旧分层B/C仍归422。

**2026-10-22 · 按用户决定移除超长账号长期测试。** 用户明确“删除为此创建的测试；测试要最简化，能不要就不要”。移除 `test_long_account_preserved_in_success_and_external_failure`（成功/外部失败2个参数化用例）、LONG_ACCOUNT及专用账号种子，撤去仅为该边界增加的2026-09替身失败分支。普通账号成功/失败、金额/归属、耗时与操作人留痕检查保留，未另建同义测试。Text业务修复和c400迁移原样保留，不作回滚；原11通过等结果仅为当时历史证据，不代表当前仍保留长账号覆盖。专用迁移回退验证仅曾是一次性work脚本，已按原收尾删除，没有长期测试文件可删；归档日志不改。此清理与419一并仅作收集/静态及真实提交钩子验证，不重新运行整页、不推进401。
