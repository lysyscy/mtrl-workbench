# TAIL-434: Excel核对合同付款方式

**What to build:** 付款计划核对技能在用户原Excel标出与关联合同不一致的付款方式，跳过问题行而继续正常行；经用户确认的特殊方式仍可由Excel写入计划。

**Blocked by:** TAIL-432

**Status:** done

- [x] 复用核对快照和现有方法预览／确认接口，补足合同关联及约定方式上下文；普通未关联集采的计划行保持既有行为。
- [x] 对关联集采合同的计划方式作比较；不一致时在用户原Excel按现有问题单元格和说明列机制标记，暂不回写该行方式；合同未填方式则标待核实并跳过。
- [x] 同批正常行继续处理，问题行不会阻断整个批次；不把系统默认现汇当作i8原值或合同约定。
- [x] 用户修正Excel或明确确认有意例外后，可通过既有确认流程回写计划方式；该已确认计划优先于合同默认方式，不增加异常审批子系统。
- [x] 以脱敏Excel及隔离数据验证冲突跳过、正常行继续、确认例外和防过期校验；保留备份、原业务值、公式、人工批注及打印布局。
- [x] 在项目维护源修改技能，核对现有分发绑定；源码保存、发布及实际安装状态分别报告，不直接改Agent安装副本。
- [x] 同步现行核对规则及共享接口说明，记录验证、提交和技能分发结果，供已有Mini App核对入口复用，不另造网页核对流程。

---

## Comments

**2026-10-23 · 输入及边界。** 共同规格见[集采账期提醒与付款方式](../../jc-payment-terms/spec.md)。本票只被TAIL-432阻塞，不依赖TAIL-433；核对对象是Excel计划填报方式，i8付款单抓取数据没有该项。正常计划回写能力保持，未经明确确认的冲突行不回写。沿独立功能分支和独立测试库接续，不操作重构工作树、8037或其他Agent测试schema；使用脱敏Excel进行隔离验证，真实用户Excel和正式业务写入仅按对应操作授权执行。

**2026-10-23 · 建票（agent）。** 来源：用户2026-10-23确认集采方案及三票拆分｜不做会怎样：项目误填的付款方式会继续回写，Excel主操作流程缺少核对｜落点：.scratch/jc-payment-terms/spec.md及对应票｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①用户已确认需求②按可独立验收路径切片③后续只依赖合同字段④验收与隔离见规格

**2026-10-23 · 实施与验收。** 快照由MOD11 service提供合同关联/约定方式，沿原只读连接取得；技能在原付款方式格及M列标冲突/未填写，问题行跳过、正常行继续。明确确认的原Excel行可生成例外候选，原预览SHA/源文件/账号/金额/状态守卫保留；确认回写同事务锁定重读合同及关联，过期整批拒绝。旧快照缺少合同上下文时不生成方式候选，本月已付继续保留蓝色状态。没有操作真实Excel或写入正式业务数据。

**2026-10-23 · 验证。** 独立测试库mtrl_workbench_test、任务schema jc_payment_terms_20261023；最终命令：run_isolated.py test tests/test_jc_payment_terms.py tests/test_jc_payment_context.py tests/test_plan_contract_method.py tests/test_plan_audit_api.py tests/test_jc_payment_terms_ui.py tests/test_layering.py ../skills/payment-plan-audit/scripts/test_audit.py ../skills/payment-plan-audit/scripts/test_remote.py -o addopts= -q --tb=short，退出0，101 passed（run-144826.log）。覆盖三票字段/迁移工具、金额及默认/提醒、Excel冲突/正常/确认例外/旧快照/已付、原值及公式/批注/打印布局/备份、防过期、分层和浏览器兼容/错误提示。此前新增浏览器夹具直接返回函数导致1 failed/100 passed，已修正并复验；首次失败日志保留。runtime及分发包已重建，未新增依赖。

**2026-10-23 · 累计独立审查。** 固定基点ef19454，覆盖三票所有提交及434未提交/新增文件；Spec无实质发现。Standards发现两项：跨包合同SQL/锁边界、付款入口吞人话错误；均已修正并由原审查者定向复核关闭。合同SQL/锁由MOD11仓储持有，service可打桩且沿原事务；错误转义展示并保留请求序列/日期保护。未以浏览器模拟接口冒充正式数据库或现场付款验证。

**2026-10-23 · 技能实际发布。** 经manage-skills核维护源/原ID/标签/手动preset后执行既有sync_business_skills.py payment-plan-audit。中央库及Codex、CodeBuddy、WorkBuddy、OpenCode的13个非缓存源文件逐项SHA一致，ID/preset/标签和原五Agent范围保持。发布入口最终退出1：豆包目录与登记部署不一致，TARGET_CONFLICT，未覆盖；只读dry-run复现并保留原目录，已向用户请求决定是否备份移开再受管部署。不是全部五份发布成功。回执在本轮skill-distribution.json；源码保存与安装状态分开报告。新技能遇尚未加载的旧后端会标合同上下文缺失，不生成方式回写候选。

**2026-10-23 · 交付边界。** 三票源码/隔离验收完成；正式Alembic、265条实际合同中29条备注建议的确认写入、后端部署/重启未执行，一次性i8日期补正未写入。真实报障FKTZS2026060313另在433记录：新端点404导致旧窗口打不开；8881fc0已兼容，仅404降级，实际窗口已打开核对但未确认付款。后续接入复用docs/reference/jc-payment-contract.md，不触碰重构工作树或8037。

**2026-10-23 · 收尾。** doc_audit.py退出0，必须修0；任务专属测试schema jc_payment_terms_20261023已在核实mtrl_workbench_test后删除，未操作public/其他Agent schema。最终源码将按本仓授权提交并推送功能分支；票据的提交/远端SHA由后续回执追加。

**2026-10-23 · 豆包恢复及最终分发。** 用户确认豆包自行将软链接展开为实体副本，并明确授权直接删除、不备份；本次及以后同类受管目标不再逐次询问。维护源references/maintenance.md记录该授权，本机发布入口D:/dev/业务流程/tools/sync_business_skills.py已实施唯一冲突/登记目标/固定豆包路径/实体无链接的保护，其他冲突不删除。test_sync_business_skills.py的六种情形验证通过；真实发布退出0，回执明确backup=false。中央库及原五Agent（含豆包）13个非缓存文件逐项SHA全部一致，原ID/preset/标签/范围保持。该本机公共发布工具不属于本仓Git；其SHA及实际结果保留在分发回执，未改中央库/Agent副本正文。技能可下载包补入维护说明并重建，客户端/包8项复验退出0；首次在沙箱回环HTTP连接失败，授予夹具网络权限后通过。此前豆包待决定状态已解除。
