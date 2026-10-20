# 测试减负 · 实施记录

授权：用户确认“开工吧”；本轮实施两份方案经版本复核后的修订范围。本地提交可明确归属的改动；不推送、安装部署、重启、生产迁移或真实业务操作。

起点：工作台 master 74c3b67be9f5a4b4c54cc1d981ccde1961e5f010；调查基线4047b464416d8d76a76f97faf47fe5390c979201。My-Skills main aab574c26cae00fe2c5d1f6c114e41edb929792d。工作台原44个状态条目的原字节及散列快照仅在本轮recovery保护，原修改不作为本轮提交内容。

依据：Library MTRL-Testing-Cleanup-Plan(1).md（libfile_b5e34339436c81919f19c07a6baa2ae1）、My-Skills-Testing-Design(1).md（libfile_ac3eed49bcf08191840ac7d3d14793b6）及本轮只读复核；五个新增回归与目录消费者已纳入。个人执行/验证方法固定读取起点源版本；writing-for-agents用于正文、条件指针与完成判据。本轮不替换其他在途任务的固定规则。

## 实施与边界

- My-Skills仅五份规则文件，现有包检查及有限独立场景。
- 数据库guard仅测试层：假配置拒绝反例、覆盖前目标、实际缓存目标及无凭据错误；保留外层事务与savepoint。真实PG目标尚未确认，相关写入测试未运行。
- 退役scope、跨运行回执、变异登记和四态常态义务；保留需求基线读取及按需历史报表，修非零/缺失/未知运行状态。
- acc注解机械退出有AST等价证据；UI公共夹具迁移18消费者。保留新机械业务回归、workspace_paths隔离/收尾保护、开销票失败回滚。
- check_design_rules和check_jc_contract_date_transaction同目录显式按需；layering/dup、无等价wired/UX、未知oneoff、浏览器复用暂缓。

## 实际验证与未验

| 核验 | 结果与边界 |
|---|---|
| 假配置数据库guard | 42 passed，rc0；包括6个conftest/假app子进程及真实隔离recipe接线；旧宽松守卫、旧recipe分别先得到失败反馈 |
| 按需历史报表 | Temp隔离17 passed，rc0；退回旧退出判断时未绑定失败反例红，恢复后通过 |
| 离线相关回归 | 源副本100项通过；同次另1项因副本缺PRD位置配置失败，补合成配置后随下行复验；19项按明确选集未执行，不冒称整套通过 |
| 文档/票工具 | 11 passed，rc0，含关票归档失败回滚、现行引用与宿主入口；副本补齐只读probe/ops/mut输入和无数据库的合成PRD指针 |
| 浏览器/Node | 52 passed，rc0；假接口、独立页面，无真实业务服务/账号；受限启动先失败/停滞，诊断后获准重试通过 |
| 测试收集 | 默认完整收集与两个check文件显式7项收集rc0；默认不含check文件。后续新增recipe反例单独通过 |
| 机械注解迁移 | 224文件去acc后AST等价；对起点再次比较所有保留函数/类（含参数化）无意外变化，夹具函数移至ui_helpers保持内容 |
| My-Skills | 既有包检查171项，rc0，4项专用环境演练跳过；五文件差异/本地引用检查通过 |
| Skills有限行为 | 旧/新各接入与重复接入、复用Node回归、独立SQLite保留任务均正确，保留验收两臂8/8；无稳定相对收益。先候选后旧版实跑且非完全盲评，不作为严格accept或成本结论 |
| 结构验证器 | 环境阻断：现有解释器缺PyYAML，未安装；不报通过 |

独立定向审查发现隔离recipe提前把两个URL都改成test，与新guard冲突；保留原URL让子进程guard切换，新增纯假接线回归后42项通过，原审查者定向复核关闭该P2。未发现其余已审范围阻断；不据此宣称全面审计或绝无遗漏。

真实PG目的库未确认：相关API/事务/rollback_db数据库写入验证未执行，隔离不明时守卫仍拒绝。未运行真实i8、账户、打印、系统39段、迁移、重启或部署；没有实测速度/Token收益。

## 来源、保存与规则生效

My-Skills本地源提交046b968cbb147384b98a3594662e272319926fcf；工作台安全底座本地提交b1970f1eb3e4069158a3e623b114de8947b32a13，其余本轮改动由后续本地提交保存。源码与工作区原修改分离；原44项中的独有资料不清理、不纳入本轮提交。未推送。

个人规则源已修改并保存，但未安装/分发，不替换其他在途任务。已核当前Codex的setup入口链接到Skills Manager中央库，正文仍匹配固定旧源aab574c，与新源不同；本轮implement参考直接读取已核源仓固定版本，不假称宿主已加载候选。工作台轻量选测通过本仓workflow、指南和pytest配置生效。本轮实施沿预先读取的固定执行方法，候选不改写旧实验或旧验收。

结项资料由活动目录归本文件；必要短期原始日志在本机.artifacts/archive/testing-cleanup，保留到2026-11-19或完成复核后提前删除；无用源码副本/恢复点释放。原判据结果、壳基线、真实数据和他人活动证据保留。暂缓项按本文件边界保留，不强行清零。

## 2026-10-20 收尾补验与新增授权

用户追加“那就收尾吧，准备做什么先汇报”，方案汇报后确认“可以做，然后可以推送重启”。据此补齐隔离测试、Skills结构验证与同步，并正常推送两源仓、按既有入口重启；原44项修改不提交，业务迁移、账号及安全设置不在授权范围。前文“不推送/未重启”等为实施初段边界，后续结果以本节为准。

根配置与应用Settings一致：应用库和测试库均在本机127.0.0.1:5432，库名分别为mtrl_workbench和mtrl_workbench_test。先由guard核隔离，再只连接测试库，以default_transaction_read_only=on确认实际目的库；已有37张public表，无需新建环境或修改凭据。初次受限连接失败，正常权限只读连接成功。

补跑test_rollback_db.py三项，正常返回/显式commit/模拟断言失败均不遗留随机Project样例，rc0。相关test_mechanical_workbench、test_mechanical_api、test_mechanical_skill_import、test_mechanical_empty_month_remove及source_protection中的PostgreSQL接口节点共59项，rc0；沿用外层事务与保存点，假接口和随机测试数据，不访问业务库或真实i8账号。不重跑测试总量基准或全套。

重启前核注册配置：mtrl-workbench-server从本仓backend启动uvicorn；backend/app、backend/pyproject.toml、backend/uv.lock和ops无未提交差异。按ops/server_ctl.ps1 -Action restart执行成功；服务PID12452→18500，Python服务进程亦更新。/healthz和/app均200；/app及mechanical-workbench.js响应SHA256与运行源一致。重启时源码HEAD为dffd83877e9df67b4bcf54ced857f96842120d30，后续收尾文档提交不改变运行代码。未清理或混入原dirty。

工作台推送前核远端及待推范围；原领先10个提交与本轮2个提交一并检查，按master正常快进发布，实际远端SHA随交付输出核对。新增diff凭据形态命中0、禁止跟踪的运行目录命中0；.env和init_db.sql在待推范围无变更。既有_prepush_sensitive脚本rc1：其扫描包含未变上下文，命中test_acc_usr_login的password=raw参数及import_kit/page_m06的preview token赋值，均为既存变量/临时保存操作；逐条定位后新增与删除行均无命中。原始rc1保留，不冒称脚本通过。

测试删减直接由本轮差异确认：删除pytestscope_cli及acc_plugin_teardown两份工具专属测试；在document_migration、pending_tools、workspace_paths、wiring_guards、ux_brief、shell_segments等仅删退役契约或文本/固定清单自检。design_rules的4项与jc_contract_date_transaction的3项改为同目录check文件，仍可显式运行。224文件主要去掉acc注解，业务函数与参数化保留；没有把旧业务测试整体删掉。今后减少默认发现和机械记账义务，不据此声称实测时长或Token收益。

本节原始日志见本机.artifacts/archive/testing-cleanup/closure-followup，与初段日志同保留到2026-11-19。

My-Skills复用检查后确认现有解释器无PyYAML，按新增授权仅在Temp虚拟环境从官方PyPI安装PyYAML6.0.3；未改全局或两仓依赖。4项自有技能结构验证均rc0/verified。源main正常推送至046b968cbb147384b98a3594662e272319926fcf，精确提交CI run39348005608成功；confirm-source rc0/source_verified。

Manager中央两项完整目录更新前匹配旧源aab574c，无独有修改；preflight rc0。仅implement-solo-spec及setup-solo-workflow各自update rc0/refreshed:true，check --force rc0/up_to_date，confirm-install rc0/installation_verified，同一046b968及计划。两项的source_revision和remote_revision均为046b968；原有两项×6个Agent的12个链接归属及内容正确，作用于codex/codebuddy/doubao/opencode/workbuddy/zcode。ID、标签、Preset与部署集合不变，其余52项683文件摘要未变。源main本地/远端一致且clean。实际安装已生效，不替换其他在途任务的固定规则。

第三个Manager备份仓不属于本次“两源仓推送”范围：HEAD与远端仍为839fb03baccd9befee5d43636c1a52559ba92b06，其工作区仅本次五文件改动，未提交未推送；不冒称confirm-distribution完整分发完成。这不影响上述两项在六个Agent入口实际生效。结构及安装回执随本节报告归档；临时验证环境验证后释放。
