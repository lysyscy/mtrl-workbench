# TAIL-484 后端覆盖与旧证据基线

2026-11-06；调查者 `/root/backend_baseline`；父任务 TAIL-483/484。本记录只登记当前入口、责任、证据和后续取证缺口，不实施修复、不宣布工程质量达标。路径均相对仓根，行号对应本次源码。

## 取证身份与结论等级

- 实测 `git rev-parse HEAD` 为 `6d01f996dd46a86c204aeb2568aad58d82c2034d`。`git status --short` 未见 `backend/app`、`backend/tests`、`backend/alembic` 源码 dirty；主检出有其他任务文档与未跟踪材料，全部保持。本调查只写本文件。
- `git diff 7156a5ae HEAD -- backend/app backend/tests` 为空；最新通知书深化的后端源码/测试可作为当前版本的直接历史证据。`17495586..7156a5ae` 后端差异仅通知书金额入口、共用金额校验及相应测试。`67111c60..17495586` 则包含浏览器 broker 与三项深化，不能整体复用前一版本所有 i8/油卡结论。
- 正式加载身份仅引用 `notice-amount-deepening-20261106/implementation.md` 的 `7156a5ae` 发布回执，本子任务未访问服务、进程、数据库或正式浏览器；实时加载身份由主控另核。
- 本轮执行的是只读文件、Git差异/历史及调用搜索；没有运行 pytest、创建引擎、迁移、浏览器、i8、打印或业务写入。测试文件存在/具名断言只表明保护意图，不能写成本轮通过。
- 未调用 Hindsight；父任务提供的知识页只涉及工作树退出。本轮依据为当前项目正文、源码及具名任务回执，不声称自动注入过后端项目记忆。
- 采用 writing-for-agents 整理任务记录；本文件属于 workflow 允许的活动 Markdown，不产生可清理运行组。没有创建工作树、预览、证据副本或需退出进程。

等级：**静态事实**＝已读实现/挂载/测试断言；**历史有效**＝明确版本和输入的已完成回执，尚未复核原始运行日志；**高可信静态风险**＝路径可推导但未注入故障；**假设**＝仍缺场景/预期/运行证据；**保持现状**＝有明确既定边界且无新反证；**未检查**＝本轮没有深入验证。一个模块可同时有这几种结论。

九维适用：全部后台业务以 Q5/Q6/Q7/Q8/Q9 为核心；Q1需实际规模与端到端读写数据，不能由函数长短推断。Q2/Q3/Q4在后台主要对应回执、错误、状态/字段契约，由前端分区核真实呈现。本记录不会为纯后台代码虚填动画/视觉分数。

## 在用业务模块及兼容边界

实际挂载以 `backend/app/main.py:278–308` 为准；通用模型登记为 `models_registry.py:11–29`，各模块的 domain/service/repository 是责任角色，不是人员所有权。规格入口为 `docs/requirements.md` 的六个主题及 `docs/architecture/writes-and-history.md`。

| 具名分区 | 当前入口及权威所有者 | 已核消费者、保护意图与证据 | 当前结论/最小未验范围 |
| --- | --- | --- | --- |
| 首页/执行记录兼容 `home` | `home/router.py` 根跳转和 run-counts；`home/service.py:30` 查 RunRecord，独立失败保 errors | `test_acc_home_todo.py`；实际业务待办由通知书同源集合提供（payments.md:41），run_counts 不等于新首页待办 | 静态事实：兼容入口仍挂载，旧运行状态面板已退出。未检查当前GUI是否仍消费 run-counts；不能以文件名当活跃主功能 |
| 项目档案与排序/归档 `mod01_projects` | `/api/m01`；router→domain/repository；archive、archive_pending、pending、recovery、sync_service 持有建档/扶正 | 全业务项目ID/仓库桥；`core_bindings.py:48` 注入项目；`test_acc_prj_*`、`test_archive_pending`、`test_promote_pending`、`test_warehouse_sync_promotion` | 静态事实：归属不唯一不猜；后者具名断言保原ID/关联、二次幂等、失败整批回滚。历史通过版本未逐票追到日志；待代表隔离事务证据 |
| 项目删除与跨域引用 | `mod01_projects/deletion.py:9–55`；各域 service.project_references 提供事实 | 显式列出 notice/plan/flow/proc/setl/inv/fee/jc/oilcard；有表锁/超时/当前重读；`test_project_delete.py:21–140` 含各表引用、文本键竞争、确认 | 静态事实：历史停用计划和油卡仍阻止误删；不按“模块退役”删关联保护。全新模型/引用覆盖应由后续变更触发复核 |
| i8 HTTP传输与认证 `mod02_i8` | client/login/sm2_crypto/cookie_store；`router.py:58` `/api/m02`；来源封装 notice_source、sources、contract_source、payable_source、report_export | 通知书/项目/库存/结存/集采/机械/PDF；本人绑定由 identity 注入；`test_i8_contract*`、`test_i8_cookie_cache`、`test_i8_ui_policy`、`test_i8_manual_safety` | 保持现状：HTTP缓存、至多一次会话恢复和强踢默认边界；本轮未真实调用。当前外部可用性、权限和分页完整性不能由旧契约代签 |
| i8浏览器会话通道 | browser_broker/browser_relay/browser_session；connect/pending/complete/disconnect；`router.py:197–311` | 工作台页面与MV3扩展搬运；白名单双检、代号、连接owner、超时；`test_i8_browser_relay`、`test_i8_browser_session_reuse`、`test_i8_strict_propagation` | 历史代表仅通知书2026-11的17行回读；合同/库存二进制/机械等现场未验（i8-contract.md:92–96）。broker之后有 `6b0bc21a` 保连接变更，必须绑定对应回执，不能用首次代表覆盖全部模式 |
| i8抓取计划/执行记录/缓存 | fetch_task、repository/models、wh_cache/source_cache；`router.py:312–534` | 项目待人工、首页兼容计数、各域抓取回执；`test_acc_i8_fetch/src/time`、`test_run_record_timing`、`test_unresolved_freshness` | 静态事实：配置就绪≠认证成功，源文件缓存≠新抓取。缓存失效/容量及当前日期范围未运行 |
| 通知书读取/分类/剔除/归属 `mod03_notice` | notice_api_router:478列表/514预览；list_data/list_view；merge/classify；notice_executors | 首页待办、付款/欠款/集采/导出/打印；`test_notice_list*`、`test_notice_fetch_skip`、`test_merge`、`test_classify`、`test_notice_association`、`test_excluded_ownership` | 静态事实：源事实、人工覆盖及归属是独立责任。TAIL-467/471读取范围优化保持；本轮不复做历史性能任务 |
| 通知书单格金额/手动整行 | `notice_amounts.py:8–32`；actions/amount；统计走 notice_actions，审批锁定重读后 manual_amounts | 实际付款不随统计改写；旧actions/stat及manual-save兼容；`test_notice_action_api`、`test_notice_actions`、`test_manual_settlement_ledger` | 历史有效 `7156a5ae`：81项定向覆盖与真实PG逐列保值回读；源码/测试至HEAD无差异。无新GUI/独立审查的旧边界保持，不能声称已独审 |
| 批量付款 | `notice_pay_actions.py:44–138`；actions/batch-pay；repository按ID锁，flow service记流水 | 付款状态、统计默认及合同引用；`test_batch_pay_concurrency.py:91/145/178` 真并发/锁后重读/异常回滚；`test_acc_pay_verify`、`test_tail310_selected_pay` | 静态事实：稳定对象ID、整批校验与request_id；未重新运行两账号竞争。注意代码先过滤撤单/剔除的targets，沿既有行为；没有新反例不擅改为另一种批次语义 |
| 原Excel付款计划核对/拟方式 | `mod03_notice/plan_audit_api/data/methods`，`mod04_plan/domain.py` 由 skill/audit.py 消费 | `skills/payment-plan-audit`；`test_acc_plan_audit`、`test_plan_audit_api`、`test_plan_contract_method`、`test_audit_payment_contract` | 保持现状：系统旧付款计划页/写入口退役，不代表纯审计规则退出。原表指纹/合同方式过期核对本轮未运行 |
| PDF/打印 | `mod03_notice/router.py:297` batch；service + print/design/fields/signatures/template/render/dispatch/ipp；pdf_cache | 真i8版式、签名和打印机；`test_print_dispatch/receipt_semantics/template/fields/signatures`、`test_acc_pay_pdf/print` | 静态事实：dispatch已投递未知则停，明确失败才换通道（dispatch.py:12–16）。服务账户Chromium/字体、实际签名槽位、IPP/驱动/纸面完成本轮均未验；需要独立授权才现场验证 |
| 付款流水/撤销 `mod05_flow` | router→service/repository；history.py为历史余额业务，不等于core操作历史 | 通知书、集采引用、统计、欠款；`test_acc_flow_led/list/pst`、`test_tail291_revoke`、`test_acc_jc_pay_link` | 静态事实：真实流水/统计覆盖分开；撤销是按流水而非删除通知书。最新具名运行版本未逐票追溯，待覆盖缺口裁定 |
| 欠款/历史余额/逐月台账 | `mod05_flow/service.py:213/270/469`，domain.DebtFacts、history.py | 机械有效月额、通知书统计、集采欠款；总欠款与逐月导出；`test_tail467_debt_facts`、`test_historical_balances`、`test_ledger_opening_range`、`test_manual_settlement_ledger` | 历史有效TAIL-467：同源等值及SQL32→14，不能推广其他端点性能；零/负/未知、2025-11断点及未填日期仍须保有代表保护 |
| 过程资料/历史材料 `mod06_proc` | router、service.build_matrices:178；repository、domain | mod08投影/调整和机械有效值；过程表/差异/导出；`test_proc_report_data`、`test_process_material_manual`、`test_process_value_projection`、`test_inventory_projection` | 静态事实：材料按库存同月优先、手填独立；历史原件及批次不退出。未执行跨页金额对账/历史单格恢复 |
| 机械明细与月值 | workbench_api/workbench/workbench_models/repository；`workbench_api.py:69–108`通用action | 过程资料六列、欠款和大表；本地技能直接录入；`test_mechanical_autosave/workbench/source_protection`、`test_process_mechanical_confirmation`、`test_mechanical_skill_recording/extraction/template_edits` | 静态事实：金额来源/有效签名是关键，不用金额相等替代源版本。普通读模型与四表导出分开；未运行完整源→明细→月值→下游及修订三方比较 |
| 机械当前累计/i8核对 | workbench_i8/mech_matching/workbench；read_preview外部取数在两段DB事务之间 | 固定i6、年度参考、当前月额、三类i8来源；`test_mechanical_i8`、`test_mechanical_empty_month_remove`、`test_tail271_matching/report` | 静态事实：采用/忽略/跟进与源事实分开；不能把已有月额当完整累计。外部真实三类完整性、未知周期和共享ID现场范围未验 |
| 收发结存 `mod07_setl` | api.py:349→fetch_service.run_fetch:81；repository.upsert_month/importer | 当前结存页/成品ZIP；`test_acc_setl_001/ext_001/fetch`、`test_fetch_transaction_ownership` | 历史有效TAIL-450：外部阶段无连接、应用事务/回执一致、同键手工行保护；未做同表多进程争用。源码run_fetch:116–169互斥跨应用提交可见 |
| 焊材/气体提取及历史结余 | mod07 inventory_extract/extract/service:105/186/213，repository余额 | 原库存入库金额和报表；`test_m07_balance`、`test_historical_balances`、`test_path1_weldgas` | 静态事实：不消费调整后金额或价税合计，历史空与0独立。未运行材料名排除反例/年度导出对账 |
| 月度会议大表 | mod07 big_domain/big_repository/big_service、api:208/294/333；oil_linkage | 项目、集采、机械、提取、油卡；`test_acc_rpt_big`、`test_tail470_big_reads`、`test_big_export`、operation_history中的名单/导出案例 | 历史有效TAIL-482空产值与0修复及TAIL-470事实复用（需主控汇总原票）；名单固定/继承和只读GET导出在测试具名保护。当前规模Q1未测 |
| 库存单据/调整 `mod08_inv` | router:86/131/162；repository、adjustment_values；fetch_service/importer | 过程资料/安文费/提取/库存导出；`test_inventory_adjustment_values.py:81–142`、`test_inventory_projection`、`test_acc_inv/fetch` | 静态事实：原单与调整分离，多字段token与行锁；旧amount-only兼容。TAIL-450短事务证据可复用；全量读取实际行数与响应成本留Q1取证 |
| 特殊费用 `mod09_fee` | api、service:89/293/307、repository/domain；oil_linkage | 年度费用、逐月台账导出、油卡联动；`test_acc_fee_mon`、`test_fee_item_history`、`test_oilcard_fee_linkage` | 静态事实：统一项与唯一月金额、空/0/负独立，旧FeeManualItem数据保留；`17495586`接续保存点反例可复用。普通项跨年改名/删除恢复尚未本轮运行 |
| 集采合同主表/同步 `mod11_jc` | api.py:49/89/179/268/290；service/domain/repository/fetch_service | 通知书项目内关联、付款上下文、大表及欠款；`test_acc_jc_fetch_orch/party/write/list`、`test_jc_contract_date_lock/payment_terms` | 历史有效TAIL-450剔除范围过期拒绝与保存点；合同日期保护/源字段白名单保持。供应商名非ID，未新跑实际多命中/日期锁场景 |
| 集采关联/子表/可靠回执 | service.py:319–517和act_link_notice；api:379–434 | 发票供应商/贸易双侧、通知书付款引用、浏览器恢复；`test_acc_jc_subtable_idempotency`、`test_jc_auto_link/link_recommendations/payment_context` | 静态事实：锁后核账号+动作参数hash；回执与业务同事务，not_found不证明原提交失败。`17495586`前端恢复深化运行证据可复用；兼容未带request_id调用保持，不扩成全局协议 |
| 油卡档案/换卡 `mod13_oilcard` | api:71–126；service.save_card/save_account/replace_card | 充值/发票快照、当前候选、总台账；`test_oilcard_archives/associations/archive_delete` | 静态事实：实体卡/当前关联/历史核算独立，归档不改旧账；有版本/ID保护。真实首次接续仍归TAIL-474，不由开发完成代签 |
| 油卡充值/调拨/退款历史 | ledger.py、transfers.py，api:155/240–283 | 对账与报表统一充值发生额；`test_oilcard_ledger/transfers` | 静态事实：转出/入成对金额、版本、撤销；内部调拨净额为0。退款UI退役而旧事实/服务保留；未执行正式账务 |
| 油卡发票接收/原件/更正/分配/删除 | invoices/invoice_pdf/invoice_adjustments；api:289–419 | 原件hash、号码/别名身份、金额分配及总导出；`test_oilcard_invoices/invoice_adjustments/archive_delete/export` | `17495586`统一receive_pdf与receipt_outcome历史有效；整票删除保原件身份、红票依赖保护。真实扫描质量/新PDF版式不被现有合成PDF测试覆盖 |
| 油卡交付下载/持久批次 | delivery.py:19–79；invoice_batches.py:95–145 | 中石化只读下载→receive_pdf；lease/attempt防旧执行者；`test_oilcard_delivery` | 静态事实：指定host、禁重定向、有字节/时间边界；下载不持DB。当前真实交付协议可用性需对原现场回执核验，不把MockTransport测试当实链成功 |
| 用油联动/首次接续 | linkage/reporting/continuation；service出口回两报表 | 费用月值、大表截止累计、source_id清单及目标快照；`test_oilcard_big_linkage/fee_linkage/continuation` | `17495586`保存点、失败不遗留绑定及不回滚调用者已做事实证据有效；首次真实业务接续未授权/未执行，不能因本地演练具名通过认定生产完成 |
| 规则/系统设置 `mod14_config` | router聚合settings/rules/jc_ignore/mech_rules API；app_settings+repository；剔除事实归mod03 | i8地址、打印配置、后续新通知书规则、集采剔除、机械匹配；`test_acc_cfg_setup`、`test_rules_store`、`test_jc_ignore`、`test_print_channel_settings` | 静态事实：地址有版本围栏，规则新增无请求幂等，见风险B1。规则初始化GET会写默认行（rules_api.py:41–46），这是现存显式设计，不作为本轮“只读现场探查”入口 |
| 账号/登录/偏好 `mod15_user` | api.py/login/domain/repository/models；main认证门 | 全站账号、本人i8绑定、history/偏好；`test_acc_usr_login/admin/mgmt/i8`、`test_session_identity/long_login`、`test_audit_session_secret` | 静态事实：唯一账号v2票，列表白名单不出密码，管理员能力服务端核。同请求重复status/restore为显式赋值非toggle；见B2。长登录/本地HTTP/密码现有裁定不凭通用Q9擅改 |

## 公共底座、装配与数据结构

| 具名分区 | 已读的责任/实际入口 | 现存保护与本轮边界 |
| --- | --- | --- |
| `main.py`装配/全局安全门/静态资源 | IP只认TCP对端，生产空白名单拒启动；POST/PUT/PATCH/DELETE核签名，登录/登出特例；读访问沿“未登录只能看”既定契约 | `test_acc_init`、`test_router_refs`、`test_static_conditional`、`test_session_identity`。静态挂载已核；未做当前服务访问或认证格式替换 |
| `core/config.py`/`app_settings.py` | 环境、数据库配置、受控effective链；`core_bindings.py`装配mod14取值 | `test_config_env_example`、`test_acc_cfg_setup`、`test_core_bindings`；未读任何真实.env/凭据，不确认当前配置值 |
| `core/session.py`/`identity.py` | HMAC账号票/ContextVar；显示操作人、本人i8绑定、expected_account分开 | 已读v2、密钥处理、绑定缺失拒绝；`test_session_identity`、`test_session_long_login`。停用旧会话的既有策略不在本轮改；真正auth与历史active_account边界不得混同 |
| `core/db.py` | 懒加载engine、Numeric(18,2)、session_scope提交/异常回滚与Tracker | `test_rollback_db`、`test_fetch_transaction_ownership`；本轮没有实例化或连接。根事务锁寿命只能由真实隔离连接证明，外层保存点夹具不替代 |
| `core/history.py`/`history_api.py`/`history_bindings.py` | 同账号advisory锁、完整值/xmin/父依赖、白名单及barrier；撤销API另核active_account | `test_operation_history.py`有冲突整批拒绝、ABA、跨账号、父子、真实handler、导出名单等断言；`test_fee_item_history`/油卡测试消费。全量策略表逐条重放未在本轮执行 |
| `core/money.py` | Decimal/HALF_UP、布尔/非有限拒绝、空必须显式处理；正/负准入归各域 | `test_core_money`、`test_amount_text_parity`、库存联算测试。旧JSON数字出口和Excel float输入边界存在，不据此直接称金额错误；真实大额往返需要消费证据 |
| `core/timing.py`/`period.py` | 北京时间默认月/日期闭区间、按域period能力 | `test_core_timing`、`test_report_query`、`test_acc_i8_time`；本轮核定义未跑跨年/边界输入 |
| `core/projects.py`/`references.py` | 共享归并键/展示名/索引与按模型查关联；数据主人注入 | `test_core_projects/core_bindings/project_delete`；无新全局项目缓存，身份桥保持 |
| `core/query.py` | 查询文本纯读取，不决定业务默认值/多选语义 | `test_report_query`；TAIL-450查询抽取候选已明确不采用，保持现状 |
| `core/errors.py`/`logging.py` | 业务错误与人类原因、日志脱敏、UTF-8 | 错误消费各域测试、`test_ux_text/feedback`。本轮未对实际日志做泄密扫描；不读取含凭据运行日志 |
| `core/frontend.py` | 完整React发布与隔离preview挂载 | `test_frontend_release/preview_runtime/static_conditional`；部署/构建在工具分区，本子任务不启停 |
| `core/nav.py`/mod03 `page.py/list_page.py/theme_react.py` | theme仍被main及用户偏好使用；nav/list_page由page再导出，历史SSR消费者大部退出 | 不能删除整个page包；nav/渲染部分当前真实运行消费者本轮未证实，列待核消费者而非质量缺陷。测试自用不自动构成生产保留理由 |
| `core/preview_store.py` | token受控预览暂存；搜索仅见预览服务器重定向目录、旧变异工具及读表注释 | 未找到应用活跃写/读消费者；用途未核清，保留，不将“旧导入退出”推成删除授权 |
| models_registry/各域models/workbench_models | 主模型均在registry；core OperationHistory及机械额外models也明确登记 | `test_schema_drift.py:54`只自动扫mod*/models.py，额外模型靠显式登记/真实metadata比较；当前未发现漏登记。后续新增非标准文件名模型要核该覆盖边界 |
| Alembic迁移 | `alembic/env.py:14–56`统一metadata，compare_type/server_default；versions保历史与油卡/集采merge | 本轮已盘点迁移集合但未逐条upgrade/downgrade审查、未核实际revision/漂移/回退。最小下一步是在经保护的可丢弃目标验证当前head及metadata；不在正式库运行autogenerate/迁移 |

## 导入、导出与运行资产分区

这部分以实际绑定表 `backend/app/export_bindings.py:29–38` 和各域路由为入口；不将xlsx文件存在等同成品可用。所有输出范围、顺序、公式/缓存和模板语义从 `docs/reference/template-export.md` 消费。

| 具名能力 | 责任和消费者 | 证据/待核 |
| --- | --- | --- |
| `import_kit/parse.py/readers.py/workbook.py` | 通用金额/日期/合并单元格/Excel格式读取底座 | `test_import_kit`、`test_excel_reading`。应用源码搜索未见当前直接消费者；业务技能/独立工具可能复用，需工具分区补核，先保留。不恢复通用导入向导 |
| 收发结存/库存导入器 | `mod07_setl/importer.py`、`mod08_inv/importer.py`仍被fetch_service调用，解析i8报表字节 | 与已退役人工历史导入不同；`test_acc_setl_fetch`、`test_acc_inv_fetch`。输入表头/单据身份按i8契约，未新读真实原件 |
| 项目档案导出 | `pj_export.py`←mod01 EXP.get('pj') | 具名入口已核；`test_approved_report_exports`等保护，当前筛选/顺序成品未新生成 |
| 通知书导出 | `nt_export.py`←notice_api_router:569；page-only keys剔除 | `test_notice_action_api`、`test_approved_report_exports`；未知金额不补零、筛选完整ID未新跑 |
| 流水导出 | `fl_export.py`←mod05 | `test_naive_export_parity`、`test_acc_flow_list`；按有效/撤销状态及日期输出，未新成品QA |
| 欠款/逐月台账 | `mod05_flow/debt_export.py` + `report_export/ledger_export.py`、service.export_ledger | `test_debt_export/ledger_export`、`test_ledger_opening_range`；费用跨年、历史起点/空0需同范围回读 |
| 过程资料 | process_export.py、tpl_fill/tpl_engine；三表同列映射 | `test_process_export`、`test_path1_templates`；公式缓存/合并/脚注/零值留空为已定例外，未新打开Excel |
| 焊材/气体 | weldgas_export.py←mod07提取 | `test_path1_weldgas`；历史列、年度总计与原单金额保持，未新成品对账 |
| 会议大表 | big_export.py←big_service同源事实 | `test_big_export`、`test_operation_history`相关export案例；GET只读，POST固定名单/并发重核；未新渲染 |
| 机械四页 | mechanical_export.py←workbench_api.report_snapshot；mech_report只读回验 | `test_mechanical_export`、`test_mechanical_workbench`；当前月轻量页不得生成Excel。模板公式/缓存及年度展开需独立成品证据 |
| 收发结存成品ZIP | setl_export.py + pivot_cache.py←service.setl_rows | `test_tail04_export`、`test_acc_setl_ext_001`；数据库明细来源，与库存源xlsx不同 |
| 库存成品xlsx | kcdj_export.py + pivot_cache.py←source_cache | `test_tail04_export`、`test_inventory_projection`；只读对应月真实缓存，无缓存明确拒绝，不能借导出联网补取 |
| 集采普通导出 | jc_export.py←mod11当前筛选排序完整ID | `test_jc_exports`；动态序号非对象主键，空范围保持空 |
| 集采打印版Excel | jc_print_export.py +指定模板 | `test_tail336_jc_print`、`test_jc_exports`；两种有/无贸易公司版式，不等于物理打印，也不混普通导出列 |
| 油卡总台账/发票/充值 | oilcard_export.py←service.total_export_snapshot及api导出入口 | `test_oilcard_export`含完整历史、期初、状态、分配不重复；总台账不随页筛选，旧分出口仍挂载兼容 |
| 通用导出基础 | naive_export/save/schema_cols/xl_common/sheet_display/tpl_engine/tpl_fill/pivot_cache | `test_export_save`、`test_naive_export_parity`、`test_path1_templates`；不把openpyxl可打开等同公式/透视缓存正确 |
| 模板/字体 | resources.py:26–66声明8份模板与SHA；web/fonts经main白名单输出 | `test_approved_report_exports`、`test_web_fonts`；运行资产不是废弃生成物。未新核8份字节/字体许可（工具/前端分区可覆盖），不重写模板 |

退役与历史明确分开：mod04旧计划页面/导入写入口退役，但domain审计、PlanRow及删除关联仍在用；mod12已取消且模型/路由退出，差异事实在mod08调整/过程资料；mod13_cross仅空包，无可达入口证据；旧SSR/旧通用导入及历史付款/集采Excel导入入口退役，批次模型、原始历史和引用保护保持。`test_retired_imports`、`test_retired_payment_plan`验证的是边界，不是恢复旧功能的理由。

## 已完成证据的有效边界

| 证据身份 | 当前可复用部分 | 明确不能推出的结论 |
| --- | --- | --- |
| TAIL-450 done；实现`1fa25415`；发布产品`67111c60`；`.scratch/audit-remediation-20261105/implementation.md:26–48` | 三域短事务/严格停止/集采剔除变化/收发结存手工行；后端组`001450-779111-29276`、`001811-943956-46100`、`003231-309645-37184`记退出0；根事务锁寿命真实独立PG连接，外部取数为模拟 | 没做同表多进程争用、真实i8、全库/全站验收；不能把失败夹具首轮抹掉；没有重开其保留/暂缓项 |
| TAIL-467/471；450票:49 | 欠款事实同源等值SQL32→14、所选付款预览保空/全量/撤销/行序；历史发布8e4512ce | 此处只核原票索引，尚未读642725be历史completion原日志；不等于当前所有SQL性能指标 |
| 三项深化`17495586`；`.scratch/architecture-deepening-20261106/implementation.md:15–23` | 油卡原件接收、用油接续编排；后端69项首轮68通过，夹具补project_id后失败单例通过；相关副本/前端恢复与独审结论具名 | 没有真实旧台账接续；完整合同编辑器并非全部GUI已验；历史日志存在性/完整性本子任务未重新打开 |
| 通知书金额`7156a5ae`；`.scratch/notice-amount-deepening-20261106/implementation.md:13–17` | 原失值反例及四文件81项、真实PG保非目标列/流水；本次比对后端源码/测试至HEAD相同 | 旧回执明确无新独立审查/副本浏览器验收，不得反写成全部完成；不是付款并发全矩阵证据 |
| i8契约:92–96与TAIL-476代表回执指针 | 浏览器HttpOnly会话、白名单/代号/超时离线保护；真实通知书17行代表 | 其他端点/超大xlsx/其他站点未现场验；保连接后新broker逻辑须对应新证据，不自动继承旧扩展包加载结论 |

旧裁定继续保持：OpenAPI生成暂缓；六声明patch保留；ReactRouter/Query、保存队列/unknown、业务撤销、身份格式、字体测量、i8协议和模板透视缓存不因“九维标准”自动更换；旧jslex/壳工具已退出。原三个后续候选和已实施三项深化必须按实际报告范围区分，不把名称类似当同一工作。本轮没有新证据要求推翻上述裁定。

## 新线索、风险与最小验证

### B1 剔除规则新增：丢回执后再次新增可重复落行（高可信静态风险）

前端分区提供 `rules.tsx:90–100`：新增POST失败保留表单、未识别uncertainWrite或稳定request_id。后端交叉核：`mod14_config/rules_api.py:53–79`请求只有kind/values/meaning；`mod03_notice/rules_repository.py:111–119`每次合法调用无条件新增；`mod03_notice/models.py:126–149`只有自增ID，无内容/请求身份唯一约束；唯一命中该表的迁移`11b991b4e7bf_m14_exclude_rule_table.py:31–41`也仅建主键和非唯一kind索引（本轮未查实际数据库漂移）。真实可达顺序是服务端提交成功但响应丢失→用户按保留表单再次保存→另一条同值配置行。账号事务串行只防同时写，不防顺序重试。

这尚未通过故障注入确证，也未观察真实重复数据。相同kind允许多行是现行契约，不应粗加kind唯一约束；完全相同规则的重复不必改变匹配结果，但会制造不明确的保存状态/多余行及后续删除维护成本。关联Q6/Q7/Q8/Q9，优先级由全库缺口裁定与真实频率决定。

最小验证：在已核隔离目标，对当前新增入口做一次“成功提交后丢响应”注入，读回规则行数、ID及同内容规则，再按现有UI重试一次；另保明确拒绝不落行和合法同kind多行。先证实用户结果再选择局部可靠回读/幂等方案，不建设全局保存框架。

### B2 账号状态/恢复：后端未见重复切换缺陷（保持现状，前端反馈假设）

前端分区指出UsersPage run缺同步在途锁。后端`api.py:499–539`每次核在用管理员；`repository.py:214–230`把status设成请求指定状态，`252–264`只清deleted标志且保原status，均不是toggle或新增；同账号请求由core/history Tracker在session_scope创建时取锁（history.py:128–137）。所以双点同一停用/恢复不应推成两次反转、增加账号或越权。

未证实的部分是乱序UI反馈、第一次成功但读回失败后的提示和跨身份切换意图。最小可选验证仅覆盖重复点击/延迟回执后的最终状态与反馈，不为两个确定赋值端点建立通用request_id表。停用已有会话策略有既定边界（main.py:152–153、repository.py:172），此线索不授权收紧它。

### B3 低成本可维护性线索：注释与现行主人漂移（静态事实，非业务缺陷）

`report_export/service.py:8–9`仍写库存导出“HTTP现导”，同文件84–99实际读取source_cache，当前架构/需求也明确导出不联网；`resources.py:38/50`仍指已迁移的模板文档/哈希表，而当前template-export.md:3明确源码resources和字节是主人。`mod15_user/api.py:417`注释说解绑后回落.env，与同文件448–449和identity.py:131–140实际拒绝矛盾。此类旧注释容易误导下次改动，但本轮未修改；可并入后续相关模块维护的小批，不作为阻塞全库路线的单独重构。

### B4 未找到当前业务消费者的保留件（用途未核清）

`core.preview_store`、`core.nav`/list_page的旧渲染分支、import_kit通用底座需要工具/技能分区补充消费者；本子任务只能确认局部搜索结果。mod04.domain则已有付款原表技能实际消费者，应明确保留。用途未知不删，不把测试自引用当必然活跃，也不以无HTTP路由当无消费者。

## 后续取证缺口（供TAIL-486/488裁定，不预建实施批）

1. **金额/保存/恢复代表链**：优先复用上述有效版本的原始运行证据；欠缺部分分别归“通知书→流水→合同→欠款”“库存调整→过程资料/费用→导出”“机械源/有效月值→累计/大表”“油卡收票/调拨/联动/接续”。每条核输入、对象ID、空/0/负/精度、冲突及失败原子性，不能每模块只打一个200便签达标。
2. **认证与对象身份**：现行只读/普通业务同权/账号管理差异须先按已批准语义列矩阵；复用同名账号碰撞和跨账号恢复测试，待核真实请求退出/切换及被拒回执。既定长会话/HTTP/明文裁定不作为未经授权的“自动安全整改”。
3. **导出**：八类模板及非模板导出应按各自数据源和选集契约核代表成品，金额读回/公式缓存/透视/行序与页面同源分别登记；物理打印单独授权。当前没有本轮成品证据。
4. **迁移/模型/恢复**：登记覆盖已静态核，实际schema revision/metadata一致性、迁移链和可恢复性仍未知。先审查隔离runner目标保护，再考虑一次可丢弃schema代表检查；不触碰正式库。
5. **性能**：库存全量、机械轻量页、欠款facts、月度大表、合同列表是具名取证对象；必须取实际行数/响应和用户动作，不按文件长度、查询数或历史32→14推当前体验。此处不指定首批业务痛点。
6. **实链/物理环境**：i8浏览器非通知书端点、真实下载协议、当前打印服务账户和纸面输出继续标未验；未获得对应授权时推进隔离模拟和源码证据，不能用一次旧成功消除这些边界。

本子任务完成的是全后端具名覆盖登记和有限高后果链静态检查。未逐行审计所有函数、未验证所有历史日志、未做全库运行验收；其余分区和证据缺口由主控汇总后裁定。
