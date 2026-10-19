# 旧demo退出与界面整改收尾（2026-10-19）

读者：追溯旧原型退出及目录调查的维护者。回答：授权、退出范围、保留资源与验证边界。何时读：追溯此次清理或恢复其源文件时。

用户明确要求删除原有demo。实施基线为Git提交7e4dabbd8b2e7830fc705412eeb4aa57b964102b；本批只保存本轮差异，既有未提交及并行修改保留，材料工作台不推送。

## 退出范围与现行主人

- 删除delivery/demo的交互HTML、四项JS检查及四份重复Excel，删除原型导读。四份Excel与backend/app/resources/templates中的运行本体逐字节一致，正式资源不删除。
- 删除_mut_uicheck与_mut_docguide，撤销变异调度登记及doc_audit的--ui入口；正式文档检查继续独立运行，拒绝旧参数而不静默假绿。
- ui_parity保留正式壳的U2/U2b/U3/U4，只移除其旧原型路径常量；相应接口清单断言继续检查正式壳。
- 有效交互规则迁至docs/requirements/interaction-rules.md，模板工作簿与列映射迁至docs/requirements/report-templates.md，同批修活引用与相对链接。旧原型自检配方退出，不把原型专属断言视为生产覆盖；当前工程规则仍由前端设计指南持有。
- 界面整改旧设计最后的§5退出范围至此完成；原件从.scratch/legacy-active/设计-界面整改与欠款口径-20261009.md逐字节移至本目录ui-debt-design-20261009.md，原SHA见本目录manifest.json。旧活动目录退出；已关闭票和旧ADR保持来源语境。

## 本机目录调查与整理方案

调查快照：artifacts有7624件、约117MB；.artifacts有15501件、约878MB；.scratch/local有7754件、约1.68GB。数字是当次盘点，运行和验证会继续产生文件，不作为容量阈值。

artifacts仍是程序工作目录：core/preview_store.py读写import_preview，mod02_i8的cookie_store、wh_cache与source_cache分别管理登录凭证、仓库与i8源文件缓存；core/config.py与导出入口使用运行产物位置，acc_plugin与acc_report使用验收JSON。其根层也混有历史开发日志，但不能整体迁走或删除。

.artifacts按任务保存截图、隔离数据库、验证输出、依赖及恢复材料；recovery/backups中的壳单文件基线仍由shell_verify和_gatescope读取。它不是全无消费者的临时目录。两个artifacts目录都存过开发日志和测试输出，这是重复职责；运行缓存、原始业务资料与比较基线各有独立用途。

.scratch/local由旧00-scratch现场整体迁入，历史单次脚本、日志、改前快照和源码副本因保留恢复依据一起留下；其根层约1.58GB，主要大文件是整轮输入快照JSON。未来仍可用：_impactscope默认在此建立basis/tmp-entry、寻找及保存浏览器自检日志，其他隔离检查也用其临时目录；_gatescope和bytes_guard明确排除普通local产物，避免它们使核验回执反复失效。目录不自动加载为产品规则，也不被生产业务读取；旧回执或脚本是否仍有价值须按具体任务核实。

最小整理方案：保留artifacts的运行契约与原始业务文件；新增任务验证产物继续按.artifacts/<effort>归组；local保留现有工具默认落点，对大快照按任务完成、Git可恢复范围、未提交原件及现行引用逐件复核，去掉已无恢复作用的重复副本。未来若统一工具临时目录，应另以_impactscope等真实消费者为范围切换并验证，不先移动目录。这次仅调查这些目录，没有批量清理。

## 验证与边界

检查输出与目录消费者清单保存在本机.artifacts/old-demo-retirement-20261019；最终实际结果在本节追加。局部pytest不覆盖权威四态结果；未重启服务、未操作生产数据库、未开展付款计划现场验收。机械费近期原型资料属于另一项已确认工作的独立来源，保持原位。

最终核验：隔离SQLite复跑95项全部通过；最初PostgreSQL尝试为87项通过、8项因沙箱连接权限阻断。doc_audit必须修0（既有疑似118），ui_parity通过，变异覆盖登记与调度隔离自测通过；移除--ui后旧参数明确返回2。字节检查、运行模块AST守恒及四份模板SHA对照通过。保存时使用正常提交钩子，结果以实际Git记录为准。
