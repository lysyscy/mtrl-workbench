# TAIL-408: 机械报表文件导入

**What to build:** 接收Agent整理的机械费明细JSON，经预览和修订冲突确认后写入，月值另行确认采用并回看结果。

**Blocked by:** TAIL-399

**Status:** ready-for-human

- [x] 仅接收现行机械费明细JSON，保留解析、明细/来源预览、拒绝、修订冲突确认及回执，原始指纹与人工来源保护保持。
- [x] 缺失明细结构、异常金额、重复来源、冲突和减少情形可判定，错误文件及过期预览不能误采纳；明细保存与有效月值确认分开。
- [x] 隔离真实后端核确认后公司汇总/四页报表，失败整批拒绝、不留半成品，原文件不覆盖。
- [x] 不迁移独立通用导入页、旧机械费Excel月值入口或过程资料旧导入；不恢复历史付款、集采或库存手动导入。

规格：[前端独立重做规格](../../frontend-vue-rewrite/spec.md)（User Stories 31, 33, 34, 36, 43）；业务口径：[machinery-fees](../../../docs/requirements/machinery-fees.md)。

验证类型：浏览器可观察行为＋实际后端/隔离数据库；涉及导出时检查实际文件，涉及外部系统时使用明确替身边界。复用有效既有保障，按本票风险补缺，不重复整套检查。

---

## Comments

**2026-10-22 · 建票（agent）。** 来源：用户2026-10-22确认React前端28票及依赖｜不做会怎样：新前端该用户路径或累计交付缺少独立验收与接续依据｜落点：新前端独立副本；规格及本票验收｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①按已批准依赖解锁后续②先验收再扩大迁移③同批共享隔离与交互边界④依赖和验收见本票

**2026-10-22 · 授权与执行入口。** 已批准建票及上述依赖，后续采用 implement-solo-spec 跨批统筹；本轮仅建票，尚未授权开始实施。ready-for-agent 仅表示任务已说清，仍需实施启动授权；外部真实动作、正式切换及退役各守规格授权门。

**2026-10-22 · 用户裁定收窄为JSON（未开工）。** 来源Sentinel_5e6d9b461e9c8191a5a49009a7e0643b：旧机械费Excel已被JSON路线完全替代，允许退役，不再要求用户复核该业务决定。本票只承接现行workbench明细JSON流程，不调用/api/imp/m06_mech_report/*，不恢复通用页或旧Excel直接更新月值能力。旧后端与专属测试清理放工程末尾另票，不能因本票实施提前删除；共用解析、金额/事务/来源保护按实际调用保留。统一边界回[退役裁定](../../frontend-vue-rewrite/spec.md#通用导入退役裁定)。

**2026-10-23 · 串行开工。** 用户明确授权408，399已done；起点26567ddfafdd75b487977612e4c5187b963e0eac、codex/react-frontend-rewrite clean。只承接现行JSON明细录入；旧可见入口/事件已核，月值独立确认复用407。保护8037/PID19956及原schema/构建，独立8038与自有schema验证；不推进409、不push/部署。


**2026-10-23 · JSON技术交付，待人工验收。** 只迁移旧机械页“录入预览／录入原报明细”及mechanical-integration.js的JSON事件；已在自有8038实际打开旧/app与选择弹窗并目视，再核新构建。沿用407机械工作区、弹窗、金额/待补判定及独立月值确认；新增文件选择（兼容归集包detail_import）、解析拒绝、明细/来源指纹/原有效值→原报建议额预览、逐项冲突选择、只写明细的确认及回执“查看明细”。同组未保存草稿阻止导入确认，预览换范围/离页退出；回执可跳对应月份和类别，写后刷新既有查询。整行/拆合行冲突显示实际行字段，空单元格不误称移除整行。仅新前端3件，后端/旧前端/通用导入均未改，没有409能力或新增依赖/持久测试。

**逐条技术证据。** 原始结果保存在本机`.artifacts/archive/frontend-vue-rewrite/tail408-20261023/`，沿effort既有2026-11-21期限；各项退出0才计通过。

1. 最终`corepack pnpm --dir apps/frontend typecheck`与`build --outDir ../../.artifacts/active/frontend-vue-rewrite/tail408-20261023/work/dist --emptyOutDir`退出0；build-final.log仅既有chunk体积提示。独立产物由真实FastAPI提供、浏览器实际加载。impeccable context/detect已运行，检测空发现；按既有Operate工作台风格，实际看1440px预览及1000px整行冲突截图，来源坐标收紧、指纹换行、长表自己横滚，无页面横溢；未做主题/尺度矩阵。
2. `python -X utf8 .../work/check408.py --pytest`（一次性入口，结束删除）复用6个现有节点、参数化后9项通过、原始退出0：`test_mechanical_workbench`的three_way_conflicts_and_idempotent_confirmation、invalid_amount_never_saved、source_precision_cached_net_and_invoice_text、revision_and_manual_effective_changes_block_stale_confirm；`test_mechanical_api`的route_failure_rolls_back_already_flushed_changes；`test_mechanical_source_protection`的gross_and_net_have_independent_confirmation_and_validation。准确节点/隔离身份见reports/pytest.json。pytest禁读.env，唯一真实DSN指向专用测试库，原目标用虚构unreachable_source_408；不向pytest传业务源DSN，实际engine/search_path均核mtrl_workbench_test及本票schema，无public。
3. 临时`browser408.py`真实浏览器/后端代表路径退出0，14项检查见reports/browser-check.json：非法JSON、缺明细结构、负金额、同批重复组均拒绝且不产生明细；含detail_import包装的JSON预览103/100、减少提示及原报指纹，确认后明细103/100而原有效值206/200不变；单独只采用含税后有效值103/200。修订选择原报309，同时保留单方人工普票；来源坐标/原精度/原备注真实回读，重复来源稳定ID不重复加行。过期浏览器预览拒绝并保留另一会话备注；含八月新组的整批预览因九月变化而全部拒绝，八月无半成品。原始JSON文件SHA前后相同。
4. 实际四页预览及下载按现有后端生成；openpyxl检查4页、公司汇总J6=103，零租明细包含保存额309，证明采用值与已存明细各归正确版本；文件字节数/SHA及页名回reports/export.json。模板与版式复用399/407有效证据，未冒称实体Excel/打印验收。
5. 临时`more408.py`最终退出0，reports/browser-more.json：整行移除/空单元格修订可辨、未选冲突不能确认；1000px实际截图已目视。真实确认成功后仅阻断GET回读，仍保留“明细已写入”回执；关闭并恢复读取成功，确认POST始终只有1次。`monthly408.py`最终退出0，reports/monthly-check.json核十月包月JSON206/200、原备注/原数量文字、回执跳十月包月页，有效包月两额仍为null、未自动采用。

**首次非零与修正。** 初始内置浏览器在8038尚未就绪时连接拒绝；读取其错误页data URL被浏览器策略阻止，没有重试或绕读该URL，服务就绪后只打开真实本机URL。一次性检查初次在预览响应到达前制造并发修改，未形成旧预览；改为等预览就绪后拒绝通过。重置自有合成schema时缺Project模型注册，事务回滚后补注册通过。包月检查先误找AG Grid未渲染的屏外备注列，后又从所有月份的返回列表误取九月有效值；分别改为可见计划月数＋真实回读备注、仓库/月/类别精确定位后通过。原始非零logs/browser-check-first.log、browser-setup.log、monthly-first.log、monthly-scope.log保留，不将其计为通过。目视发现原报行内完整来源JSON撑高表格，改为行内坐标、来源区保留文件和指纹后复看；自查修正空值/整行冲突的显示歧义并针对复验。父任务提示的待审批动作不推定获准；本票只计明确完成回执/退出码，未通过替代路线执行受阻动作。

**自查及未验。** 按execution选择有界自查，固定起点26567ddfafdd75b487977612e4c5187b963e0eac后的全部408差异，核MechanicalPage直接调用、草稿/范围、JSON预览确认及回执、已有来源/月值保护和四页出口。业务金额、三方合并、事务及来源保护仍由未改后端持有，既有9项保障与本票真实代表路径足够，不增加机械多轮审查；不冒称独立评审，422最终累计独立审查保持。票面勾选仅表示技术覆盖，完整页面仍ready-for-human；人工业务验收、主题/字号组合和实体Excel/纸面效果未验。409未开工，通用Excel入口退役裁定和425后端清理仍保持；8037不提前开放407/408。


**2026-10-23 · 收尾实测。** 8038/PID14052通过本票stop-request优雅退出，原执行会话退出0；唯一schema`frontend_rewrite_397_8d976f2cb284462884471254e8198f53`及其应用连接均为0，8038端口已释放。8037健康200、原PID19956启动时点07:57:55保持，原schema仍存在、共享dist的13件SHA256逐项一致（reports/resource-check.json）；未操作其数据或开放新页面。本票浏览器上下文已关闭，临时脚本/JSON/构建/导出和自有active run已实际删除，必要logs/reports/screenshots已归上述archive，既有retention不续期；workspace_check.py run-closed退出0。整个frontend effort及8037仍活动，未执行closed或清理他人内容。本轮只本地提交、不push/部署/正式切换；无真实i8/强踢/同步/物理打印、持久凭据或权限变更。停在408，交父统筹后票。


**2026-10-23 · 本地保存与浏览器收尾限制。** 实现/记录已本地提交b1f7fa8，真实pre-commit语法、字节及凭据文件检查均通过，无push/部署。成功探查页2与所有Python Playwright上下文已关闭；最初8038未就绪产生的临时错误页标签1，在取得关闭句柄时被浏览器data URL策略拒绝，关闭未执行、当前未确认已关闭；停止该动作，不换工具绕过。该页未标记deliverable/handoff，按宿主默认于本轮结束回收，不能把宿主未来回收冒称已完成。本限制只涉及无业务状态的临时错误标签，8038/schema/work与run-closed已实际完成，8037仍按原owner保留。
